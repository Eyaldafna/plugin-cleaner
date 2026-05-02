from __future__ import annotations
import plistlib
import re
import struct
from collections import defaultdict
from pathlib import Path

SESSIONS_ROOT = Path.home() / "Library/CloudStorage/Dropbox/Work"

WAVELAB_REGISTRY = Path.home() / "Library/Preferences/WaveLab Pro 13/Cache/plugin-registry-arm.txt"
WAVELAB_LRU      = Path.home() / "Library/Preferences/WaveLab Pro 13/Cache/lru_plugins.txt"

# Matches built-in Cockos dylib references we want to skip
_COCKOS_RE = re.compile(r'\.dylib$', re.IGNORECASE)
# Matches plugin lines in RPP
_AU_LINE   = re.compile(r'^\s*<AU\s+"AU:\s*.+?\s+\(.+?\)"\s+"([^"]+)"')
_VST3_LINE = re.compile(r'^\s*<VST\s+"VST3:\s*.+?"\s+"(.+?\.vst3)"')
_VST2_LINE = re.compile(r'^\s*<VST\s+"VST:\s*.+?"\s+"?(\S+?\.(?:vst|dll))"?')

_GUID_RE   = re.compile(r'id\d*=\{([0-9A-Fa-f\-]+)\}')
_UID_RE    = re.compile(r'UID\d*=\{([0-9A-Fa-f\-]+)\}')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _latest_per_dir(root: Path, suffix: str) -> list[Path]:
    """For each directory, return only the most recently modified file with suffix."""
    by_dir: dict[Path, list[tuple[float, Path]]] = defaultdict(list)
    for f in root.rglob(f"*{suffix}"):
        parts = set(f.parts)
        if "Backups" in parts or "Undo Data" in parts or "backups" in parts:
            continue
        by_dir[f.parent].append((f.stat().st_mtime, f))
    return [max(entries)[1] for entries in by_dir.values()]


# ---------------------------------------------------------------------------
# Reaper parser
# ---------------------------------------------------------------------------

class SessionRef:
    __slots__ = ("kind", "key", "source")

    def __init__(self, kind: str, key: str, source: str):
        self.kind   = kind    # "au_cache_key" | "vst3_basename" | "vst2_basename"
        self.key    = key
        self.source = source  # session file path (for display)


def parse_reaper_sessions(
    root: Path = SESSIONS_ROOT,
    progress_cb=None,
) -> list[SessionRef]:
    rpp_files = _latest_per_dir(root, ".RPP") + _latest_per_dir(root, ".rpp")
    # Deduplicate (case-insensitive paths)
    seen: set[str] = set()
    unique = []
    for f in rpp_files:
        k = str(f).lower()
        if k not in seen:
            seen.add(k)
            unique.append(f)

    refs: list[SessionRef] = []
    for i, path in enumerate(unique):
        if progress_cb:
            progress_cb(i, len(unique), f"Reaper: {path.name}")
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = _AU_LINE.match(line)
                    if m:
                        refs.append(SessionRef("au_cache_key", m.group(1), str(path)))
                        continue
                    m = _VST3_LINE.match(line)
                    if m:
                        refs.append(SessionRef("vst3_basename", m.group(1), str(path)))
                        continue
                    m = _VST2_LINE.match(line)
                    if m and not _COCKOS_RE.search(m.group(1)):
                        refs.append(SessionRef("vst2_basename", m.group(1), str(path)))
        except Exception:
            pass
    return refs


# ---------------------------------------------------------------------------
# Logic parser
# ---------------------------------------------------------------------------

def _to_4cc(n: int) -> str:
    return struct.pack(">I", n & 0xFFFFFFFF).decode("ascii", errors="replace")


def _parse_logic_project_data(path: Path) -> set[tuple[str, str, str]]:
    refs: set[tuple[str, str, str]] = set()
    try:
        data = path.read_bytes()
    except Exception:
        return refs

    pos = 0
    while True:
        start = data.find(b"<plist", pos)
        if start == -1:
            break
        end = data.find(b"</plist>", start)
        if end == -1:
            break
        try:
            pl = plistlib.loads(data[start:end + 8])
            if "manufacturer" in pl and "subtype" in pl:
                refs.add((
                    _to_4cc(pl.get("type", 0)),
                    _to_4cc(pl["subtype"]),
                    _to_4cc(pl["manufacturer"]),
                ))
        except Exception:
            pass
        pos = end + 8
    return refs


def parse_logic_sessions(
    root: Path = SESSIONS_ROOT,
    progress_cb=None,
) -> list[SessionRef]:
    logicx_dirs = _latest_per_dir(root, ".logicx")
    refs: list[SessionRef] = []

    for i, logicx in enumerate(logicx_dirs):
        if progress_cb:
            progress_cb(i, len(logicx_dirs), f"Logic: {logicx.name}")
        # Scan all non-backup ProjectData files inside the package
        for pd in logicx.rglob("ProjectData"):
            parts = set(pd.parts)
            if "Project File Backups" in parts or "Backups" in parts:
                continue
            for (typ, sub, mfr) in _parse_logic_project_data(pd):
                refs.append(SessionRef("au_4cc", f"{typ}|{sub}|{mfr}", str(logicx)))
    return refs


# ---------------------------------------------------------------------------
# WaveLab parser (registry + LRU cache — no binary .mon parsing needed)
# ---------------------------------------------------------------------------

def _parse_wavelab_registry(path: Path) -> dict[str, str]:
    """Returns {GUID_UPPER: bundle_path_str}."""
    result: dict[str, str] = {}
    if not path.exists():
        return result

    current_bundle = ""
    inside_plugins = False
    depth = 0
    uid_buffer: list[str] = []

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if stripped == "{":
                depth += 1
                if depth == 2 and current_bundle:
                    inside_plugins = False
            elif stripped == "}":
                if inside_plugins:
                    for uid in uid_buffer:
                        result[uid] = current_bundle
                    uid_buffer.clear()
                    inside_plugins = False
                depth -= 1
                if depth == 0:
                    current_bundle = ""
            elif depth == 1 and stripped.startswith("/") and stripped.endswith(".vst3"):
                current_bundle = stripped
            elif stripped == "PlugIns":
                inside_plugins = True
                uid_buffer.clear()
            elif inside_plugins:
                m = _UID_RE.search(stripped)
                if m:
                    uid_buffer.append(m.group(1).upper())

    return result


def _parse_wavelab_lru(path: Path) -> set[str]:
    """Returns set of GUIDs (uppercase) that WaveLab has recently used."""
    guids: set[str] = set()
    if not path.exists():
        return guids
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _GUID_RE.search(line)
            if m:
                guids.add(m.group(1).upper())
    return guids


def parse_wavelab_usage(progress_cb=None) -> list[SessionRef]:
    if progress_cb:
        progress_cb(0, 1, "WaveLab: reading plugin registry")

    registry = _parse_wavelab_registry(WAVELAB_REGISTRY)
    used_guids = _parse_wavelab_lru(WAVELAB_LRU)

    refs: list[SessionRef] = []
    for guid in used_guids:
        bundle_path = registry.get(guid)
        if bundle_path:
            refs.append(SessionRef("vst3_bundle_path", bundle_path, "WaveLab (recently used)"))

    if progress_cb:
        progress_cb(1, 1, "WaveLab: done")
    return refs
