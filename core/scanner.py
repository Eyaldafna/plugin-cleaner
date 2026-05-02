from __future__ import annotations
import os
import plistlib
import re
import unicodedata
from pathlib import Path
from typing import Iterator

from .models import PluginFormat, PluginRecord, UsageStatus

AU_DIR   = Path("/Library/Audio/Plug-Ins/Components")
VST3_DIR = Path("/Library/Audio/Plug-Ins/VST3")
VST2_DIR = Path("/Library/Audio/Plug-Ins/VST")

REAPER_VST_CACHE = Path.home() / "Library/Application Support/REAPER/reaper-vstplugins_arm64.ini"
REAPER_AU_CACHE  = Path.home() / "Library/Application Support/REAPER/reaper-auplugins_arm64.ini"

# Reaper VST cache line: "Plugin_Name.vst3=HEX,ID{GUID,Human Name (Vendor)"
_VST_CACHE_RE = re.compile(
    r'^(.+?\.vst3?)=[^,]+,\d+[\{<][^,]+,(.+?)\s+\((.+?)\)\s*$'
)


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
            elif entry.is_dir(follow_symlinks=False):
                total += _dir_size(Path(entry.path))
    except PermissionError:
        pass
    return total


def _normalize_family(vendor: str, name: str) -> str:
    raw = f"{vendor}:{name}".lower()
    # strip accents and non-alphanumeric
    nfd = unicodedata.normalize("NFD", raw)
    return re.sub(r"[^a-z0-9:]", "", nfd)


def _load_vst_cache() -> dict[str, tuple[str, str]]:
    """Returns {cache_key_filename: (human_name, vendor)}."""
    result: dict[str, tuple[str, str]] = {}
    if not REAPER_VST_CACHE.exists():
        return result
    with open(REAPER_VST_CACHE, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _VST_CACHE_RE.match(line.rstrip())
            if m:
                result[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    return result


def _vst_cache_key(bundle_name: str) -> str:
    # Reaper cache normalises spaces→underscores and hyphens→underscores
    return re.sub(r"[ \-]", "_", bundle_name)


def _load_au_cache() -> dict[str, str]:
    """Returns {au_cache_key: '<inst>'|'<!inst>'}  e.g. {"FabFilter: Pro-L 2": "<!inst>"}."""
    result: dict[str, str] = {}
    if not REAPER_AU_CACHE.exists():
        return result
    with open(REAPER_AU_CACHE, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if "=" in line and not line.startswith("["):
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    return result


def _read_info_plist(bundle_path: Path) -> dict:
    plist_path = bundle_path / "Contents" / "Info.plist"
    if not plist_path.exists():
        return {}
    try:
        with open(plist_path, "rb") as f:
            return plistlib.load(f)
    except Exception:
        return {}


def _scan_au_bundle(path: Path, vst_cache: dict, au_cache: dict) -> list[PluginRecord]:
    info = _read_info_plist(path)
    components = info.get("AudioComponents", [])
    if not components:
        # Fallback: create one record from bundle metadata
        name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or path.stem
        components = [{"name": f"Unknown: {name}", "type": "", "subtype": "", "manufacturer": ""}]

    size = _dir_size(path)
    records = []
    for ac in components:
        raw_name = ac.get("name", "")
        if ": " in raw_name:
            vendor, display = raw_name.split(": ", 1)
        else:
            vendor, display = "", raw_name

        cache_key = raw_name  # "FabFilter: Pro-L 2"

        records.append(PluginRecord(
            bundle_path  = path,
            bundle_name  = path.name,
            format       = PluginFormat.AU,
            display_name = display,
            vendor       = vendor,
            version      = info.get("CFBundleShortVersionString", ""),
            bundle_id    = info.get("CFBundleIdentifier", ""),
            size_bytes   = size,
            au_cache_key    = cache_key,
            au_type         = ac.get("type", ""),
            au_subtype      = ac.get("subtype", ""),
            au_manufacturer = ac.get("manufacturer", ""),
            status       = UsageStatus.SCANNING,
            family_key   = _normalize_family(vendor, display),
        ))
    return records


def _scan_vst3_bundle(path: Path, vst_cache: dict) -> PluginRecord:
    info = _read_info_plist(path)
    name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or path.stem
    version = info.get("CFBundleShortVersionString", "")
    bundle_id = info.get("CFBundleIdentifier", "")

    # Vendor enrichment from Reaper VST cache
    cache_key = _vst_cache_key(path.name)           # "FabFilter_Pro-Q_3.vst3"
    human_name, vendor = vst_cache.get(cache_key, (name, ""))
    if not vendor:
        # Try without extension
        cache_key2 = _vst_cache_key(path.stem)
        human_name2, vendor2 = vst_cache.get(cache_key2 + ".vst3", (name, ""))
        if vendor2:
            vendor = vendor2

    return PluginRecord(
        bundle_path  = path,
        bundle_name  = path.name,
        format       = PluginFormat.VST3,
        display_name = name,
        vendor       = vendor,
        version      = version,
        bundle_id    = bundle_id,
        size_bytes   = _dir_size(path),
        status       = UsageStatus.SCANNING,
        family_key   = _normalize_family(vendor, name),
    )


def _scan_vst2_bundle(path: Path, vst_cache: dict) -> PluginRecord:
    info = _read_info_plist(path)
    name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or path.stem
    version = info.get("CFBundleShortVersionString", "")
    bundle_id = info.get("CFBundleIdentifier", "")

    cache_key = _vst_cache_key(path.name)
    human_name, vendor = vst_cache.get(cache_key, (name, ""))

    return PluginRecord(
        bundle_path  = path,
        bundle_name  = path.name,
        format       = PluginFormat.VST2,
        display_name = name,
        vendor       = vendor,
        version      = version,
        bundle_id    = bundle_id,
        size_bytes   = _dir_size(path),
        status       = UsageStatus.SCANNING,
        family_key   = _normalize_family(vendor, name),
    )


def _is_vendor_subfolder(d: Path) -> bool:
    try:
        return any(f.endswith(".vst3") for f in os.listdir(d))
    except PermissionError:
        return False


def _collect_vst3_bundles(vst3_root: Path) -> Iterator[Path]:
    if not vst3_root.exists():
        return
    for item in vst3_root.iterdir():
        if item.suffix == ".vst3":
            yield item
        elif item.suffix == ".component":
            # Misinstalled AU component in VST3 dir
            yield item
        elif item.is_dir() and not item.name.startswith(".") and _is_vendor_subfolder(item):
            for sub in item.iterdir():
                if sub.suffix == ".vst3":
                    yield sub


def scan_all(progress_cb=None) -> list[PluginRecord]:
    """Scan all plugin directories and return PluginRecord list."""
    vst_cache = _load_vst_cache()
    au_cache  = _load_au_cache()
    records: list[PluginRecord] = []

    # --- AU bundles ---
    if AU_DIR.exists():
        au_bundles = [p for p in AU_DIR.iterdir() if p.suffix == ".component"]
        for i, path in enumerate(au_bundles):
            if progress_cb:
                progress_cb(f"Scanning AU ({i+1}/{len(au_bundles)}): {path.name}")
            records.extend(_scan_au_bundle(path, vst_cache, au_cache))

    # --- VST3 bundles (including stray .component in VST3 dir) ---
    vst3_bundles = list(_collect_vst3_bundles(VST3_DIR))
    for i, path in enumerate(vst3_bundles):
        if progress_cb:
            progress_cb(f"Scanning VST3 ({i+1}/{len(vst3_bundles)}): {path.name}")
        if path.suffix == ".component":
            records.extend(_scan_au_bundle(path, vst_cache, au_cache))
        else:
            records.append(_scan_vst3_bundle(path, vst_cache))

    # --- VST2 bundles ---
    if VST2_DIR.exists():
        vst2_bundles = [p for p in VST2_DIR.iterdir() if p.suffix == ".vst"]
        for i, path in enumerate(vst2_bundles):
            if progress_cb:
                progress_cb(f"Scanning VST2 ({i+1}/{len(vst2_bundles)}): {path.name}")
            records.append(_scan_vst2_bundle(path, vst_cache))

    return records
