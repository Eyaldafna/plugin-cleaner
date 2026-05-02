from __future__ import annotations
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .models import PluginFormat, PluginRecord, QuarantineEntry

QUARANTINE_DIR = Path.home() / "PluginQuarantine"

_AU_CACHE_PLIST    = Path.home() / "Library/Preferences/com.apple.audio.AudioComponentCache.plist"
_AU_HOSTING_CACHES = [
    Path.home() / "Library/Caches/com.apple.audio.AUHostingService.arm64e",
    Path.home() / "Library/Caches/com.apple.audio.AUHostingService.x86-64",
]
_REAPER_VST_INI    = Path.home() / "Library/Application Support/REAPER/reaper-vstplugins_arm64.ini"
_REAPER_AU_INI     = Path.home() / "Library/Application Support/REAPER/reaper-auplugins_arm64.ini"
_REAPER_AU_BC_INI  = Path.home() / "Library/Application Support/REAPER/reaper-auplugins_arm64-bc.ini"
_WL_REGISTRY       = Path.home() / "Library/Preferences/WaveLab Pro 13/Cache/plugin-registry-arm.txt"
MANIFEST_FILE  = QUARANTINE_DIR / "manifest.json"


def _load_manifest() -> list[dict]:
    if not MANIFEST_FILE.exists():
        return []
    try:
        data = json.loads(MANIFEST_FILE.read_text())
        return data.get("entries", [])
    except Exception:
        return []


def _save_manifest(entries: list[dict]) -> None:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "entries": entries}
    tmp = MANIFEST_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, MANIFEST_FILE)


def load_quarantine_entries() -> list[QuarantineEntry]:
    return [QuarantineEntry(**e) for e in _load_manifest()]


def daws_running() -> list[str]:
    """Return list of running DAW names."""
    running = []
    for name in ("REAPER", "Logic Pro"):
        result = subprocess.run(
            ["pgrep", "-x", name], capture_output=True, text=True
        )
        if result.stdout.strip():
            running.append(name)
    return running


def _prepare_dest(record: PluginRecord) -> Path:
    dest_dir = QUARANTINE_DIR / record.format.value
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / record.bundle_name
    if dest.exists():
        dest = dest_dir / f"{record.bundle_path.stem}_dup{record.bundle_path.suffix}"
    return dest


def _make_entry(record: PluginRecord, dest: Path) -> QuarantineEntry:
    return QuarantineEntry(
        bundle_name=record.bundle_name,
        format=record.format.value,
        original_path=str(record.bundle_path),
        quarantine_path=str(dest),
        quarantined_at=datetime.now().isoformat(timespec="seconds"),
        display_name=record.display_name,
        vendor=record.vendor,
        version=record.version,
        was_status=record.status.value,
        size_bytes=record.size_bytes,
    )


def quarantine_plugin(record: PluginRecord) -> QuarantineEntry:
    """Move plugin bundle to quarantine folder. Raises PermissionError if root-owned."""
    dest = _prepare_dest(record)
    os.rename(str(record.bundle_path), str(dest))
    entry = _make_entry(record, dest)
    entries = _load_manifest()
    entries.append(entry.__dict__)
    _save_manifest(entries)
    record.is_quarantined = True
    return entry


def quarantine_plugins_privileged(records: list[PluginRecord]) -> list[QuarantineEntry]:
    """Move root-owned plugins via a single osascript admin-auth dialog."""
    moves: list[tuple[str, str]] = []
    pairs: list[tuple[PluginRecord, Path]] = []
    for rec in records:
        dest = _prepare_dest(rec)
        moves.append((str(rec.bundle_path), str(dest)))
        pairs.append((rec, dest))

    mv_cmd = " && ".join(
        f"mv -f {shlex.quote(src)} {shlex.quote(dst)}" for src, dst in moves
    )
    result = subprocess.run(
        ["osascript", "-e", f'do shell script "{mv_cmd}" with administrator privileges'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or "Administrator authentication failed or was cancelled."
        raise PermissionError(err)

    new_entries: list[QuarantineEntry] = []
    existing = _load_manifest()
    for rec, dest in pairs:
        entry = _make_entry(rec, dest)
        existing.append(entry.__dict__)
        rec.is_quarantined = True
        new_entries.append(entry)
    _save_manifest(existing)
    return new_entries


def _remove_ini_lines(path: Path, keys: set[str]) -> None:
    """Remove lines whose key (text before '=') is in keys."""
    if not path.exists() or not keys:
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    kept = [l for l in lines if not any(l.startswith(k + "=") for k in keys)]
    if len(kept) < len(lines):
        path.write_text("".join(kept), encoding="utf-8")


def _remove_bc_ini_lines(path: Path, keys: set[str]) -> None:
    """Remove lines from Reaper's -bc.ini FX browser cache.
    Format: AU "Vendor: Name" "Vendor: Name" timestamp ...
    """
    if not path.exists() or not keys:
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    kept = [l for l in lines if not any(l.startswith(f'AU "{k}"') for k in keys)]
    if len(kept) < len(lines):
        path.write_text("".join(kept), encoding="utf-8")


def _remove_wavelab_blocks(bundle_paths: set[str]) -> None:
    """Remove plugin blocks from WaveLab's registry for the given bundle paths."""
    if not _WL_REGISTRY.exists() or not bundle_paths:
        return
    lines = _WL_REGISTRY.read_text(encoding="utf-8", errors="replace").splitlines()
    result: list[str] = []
    skip_depth = 0
    for line in lines:
        s = line.strip()
        if skip_depth == 0 and s in bundle_paths:
            skip_depth = 1
            continue
        if skip_depth > 0:
            if s == "{":
                skip_depth += 1
            elif s == "}":
                skip_depth -= 1
            continue
        result.append(line)
    if len(result) < len(lines):
        _WL_REGISTRY.write_text("\n".join(result) + "\n", encoding="utf-8")


def _do_clear_caches(has_au: bool, au_cache_keys: set[str],
                     vst_bundle_keys: set[str], vst_orig_paths: set[str]) -> None:
    """Shared cache-clearing logic used by both clear_daw_caches variants."""
    if has_au:
        try:
            _AU_CACHE_PLIST.unlink()
        except FileNotFoundError:
            pass
        for cache_dir in _AU_HOSTING_CACHES:
            for name in ("Cache.db", "Cache.db-shm", "Cache.db-wal"):
                try:
                    (cache_dir / name).unlink()
                except FileNotFoundError:
                    pass
        _remove_ini_lines(_REAPER_AU_INI, au_cache_keys)
        _remove_bc_ini_lines(_REAPER_AU_BC_INI, au_cache_keys)

    if vst_bundle_keys:
        _remove_ini_lines(_REAPER_VST_INI, vst_bundle_keys)
        _remove_wavelab_blocks(vst_orig_paths)


def clear_daw_caches(records: list[PluginRecord]) -> None:
    """Remove newly quarantined plugins from DAW caches."""
    au_records  = [r for r in records if r.format == PluginFormat.AU]
    vst_records = [r for r in records if r.format in (PluginFormat.VST3, PluginFormat.VST2)]
    _do_clear_caches(
        has_au        = bool(au_records),
        au_cache_keys = {r.au_cache_key for r in au_records if r.au_cache_key},
        vst_bundle_keys = {r.bundle_name.replace(" ", "_") for r in vst_records},
        vst_orig_paths  = {str(r.bundle_path) for r in vst_records},
    )


def clear_daw_caches_for_entries(entries: list[QuarantineEntry]) -> None:
    """Clear DAW caches for already-quarantined entries (reads from manifest)."""
    au_entries  = [e for e in entries if e.format == "AU"]
    vst_entries = [e for e in entries if e.format in ("VST3", "VST2")]
    _do_clear_caches(
        has_au          = bool(au_entries),
        au_cache_keys   = {f"{e.vendor}: {e.display_name}" for e in au_entries if e.vendor},
        vst_bundle_keys = {e.bundle_name.replace(" ", "_") for e in vst_entries},
        vst_orig_paths  = {e.original_path for e in vst_entries},
    )


def restore_plugin(entry: QuarantineEntry) -> None:
    original = Path(entry.original_path)
    original.parent.mkdir(parents=True, exist_ok=True)
    os.rename(entry.quarantine_path, str(original))
    _save_manifest([e for e in _load_manifest() if e.get("quarantine_path") != entry.quarantine_path])


def delete_permanently(entry: QuarantineEntry) -> None:
    path = Path(entry.quarantine_path)
    try:
        shutil.rmtree(str(path)) if path.is_dir() else path.unlink()
    except FileNotFoundError:
        pass
    _save_manifest([e for e in _load_manifest() if e.get("quarantine_path") != entry.quarantine_path])
