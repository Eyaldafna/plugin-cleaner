from __future__ import annotations
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .models import PluginFormat, PluginRecord, QuarantineEntry

QUARANTINE_DIR = Path("/Library/Audio/Plug-Ins/Quarantine")

_MANIFEST_DIR  = Path.home() / "Library/Application Support/PluginCleaner"
MANIFEST_FILE  = _MANIFEST_DIR / "manifest.json"
_LEGACY_QUARANTINE_DIR = Path.home() / "PluginQuarantine"
_OLD_MANIFEST          = _LEGACY_QUARANTINE_DIR / "manifest.json"

_AU_CACHE_PLIST    = Path.home() / "Library/Preferences/com.apple.audio.AudioComponentCache.plist"
_AU_HOSTING_CACHES = [
    Path.home() / "Library/Caches/com.apple.audio.AUHostingService.arm64e",
    Path.home() / "Library/Caches/com.apple.audio.AUHostingService.x86-64",
]
_REAPER_VST_INI    = Path.home() / "Library/Application Support/REAPER/reaper-vstplugins_arm64.ini"
_REAPER_AU_INI     = Path.home() / "Library/Application Support/REAPER/reaper-auplugins_arm64.ini"
_REAPER_AU_BC_INI  = Path.home() / "Library/Application Support/REAPER/reaper-auplugins_arm64-bc.ini"
_WL_REGISTRY       = Path.home() / "Library/Preferences/WaveLab Pro 13/Cache/plugin-registry-arm.txt"


def _load_manifest() -> list[dict]:
    if not MANIFEST_FILE.exists():
        if _OLD_MANIFEST.exists():
            _MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_OLD_MANIFEST, MANIFEST_FILE)
        else:
            return []
    try:
        data = json.loads(MANIFEST_FILE.read_text())
        return data.get("entries", [])
    except Exception:
        return []


def _save_manifest(entries: list[dict]) -> None:
    _MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "entries": entries}
    tmp = MANIFEST_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, MANIFEST_FILE)


def load_quarantine_entries() -> list[QuarantineEntry]:
    return [QuarantineEntry(**e) for e in _load_manifest()]


def migrate_quarantine_dir() -> bool:
    """Move existing ~/PluginQuarantine/ files to /Library/Audio/Plug-Ins/Quarantine/.

    Returns True if migration ran (caller should refresh UI), False if nothing to migrate.
    Silent on failure — old paths remain valid in the manifest.
    """
    if not _LEGACY_QUARANTINE_DIR.exists():
        return False
    entries = _load_manifest()
    legacy_prefix = str(_LEGACY_QUARANTINE_DIR)
    old_entries = [(i, e) for i, e in enumerate(entries)
                   if e.get("quarantine_path", "").startswith(legacy_prefix)]
    if not old_entries:
        return False

    dest_dirs: set[str] = set()
    moves: list[tuple[str, str]] = []
    new_path_by_idx: dict[int, str] = {}
    for i, e in old_entries:
        old_path = e["quarantine_path"]
        rel = Path(old_path).relative_to(_LEGACY_QUARANTINE_DIR)
        new_path = str(QUARANTINE_DIR / rel)
        dest_dirs.add(str(Path(new_path).parent))
        moves.append((old_path, new_path))
        new_path_by_idx[i] = new_path

    mkdir_part = " && ".join(f"mkdir -p {shlex.quote(d)}" for d in sorted(dest_dirs))
    mv_part    = " && ".join(f"mv -f {shlex.quote(s)} {shlex.quote(d)}" for s, d in moves)
    result = subprocess.run(
        ["osascript", "-e",
         f'do shell script "{mkdir_part} && {mv_part}" with administrator privileges'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False  # keep old paths intact

    for i, new_path in new_path_by_idx.items():
        entries[i] = dict(entries[i])
        entries[i]["quarantine_path"] = new_path
    _save_manifest(entries)
    return True


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
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass  # privileged path will create the directory
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
    """Move plugin bundle to quarantine folder. Raises PermissionError if privileged move needed."""
    dest = _prepare_dest(record)
    os.rename(str(record.bundle_path), str(dest))
    entry = _make_entry(record, dest)
    entries = _load_manifest()
    entries.append(entry.__dict__)
    _save_manifest(entries)
    record.is_quarantined = True
    return entry


def quarantine_plugins_privileged(records: list[PluginRecord]) -> list[QuarantineEntry]:
    """Move plugins via a single osascript admin-auth dialog."""
    moves: list[tuple[str, str]] = []
    pairs: list[tuple[PluginRecord, Path]] = []
    dest_dirs: set[str] = set()
    for rec in records:
        dest = _prepare_dest(rec)
        moves.append((str(rec.bundle_path), str(dest)))
        pairs.append((rec, dest))
        dest_dirs.add(str(dest.parent))

    mkdir_part = " && ".join(f"mkdir -p {shlex.quote(d)}" for d in sorted(dest_dirs))
    mv_part = " && ".join(
        f"mv -f {shlex.quote(src)} {shlex.quote(dst)}" for src, dst in moves
    )
    shell_cmd = f"{mkdir_part} && {mv_part}"

    result = subprocess.run(
        ["osascript", "-e", f'do shell script "{shell_cmd}" with administrator privileges'],
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


def _delete_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _do_clear_caches(has_au: bool,
                     vst_bundle_keys: set[str], vst_orig_paths: set[str]) -> None:
    """Shared cache-clearing logic used by both clear_daw_caches variants."""
    if has_au:
        _delete_file(_AU_CACHE_PLIST)
        for cache_dir in _AU_HOSTING_CACHES:
            for name in ("Cache.db", "Cache.db-shm", "Cache.db-wal"):
                _delete_file(cache_dir / name)
        _delete_file(_REAPER_AU_INI)
        _delete_file(_REAPER_AU_BC_INI)

    if vst_bundle_keys:
        _delete_file(_REAPER_VST_INI)
        _remove_wavelab_blocks(vst_orig_paths)


def clear_daw_caches(records: list[PluginRecord]) -> None:
    """Remove newly quarantined plugins from DAW caches."""
    au_records  = [r for r in records if r.format == PluginFormat.AU]
    vst_records = [r for r in records if r.format in (PluginFormat.VST3, PluginFormat.VST2)]
    _do_clear_caches(
        has_au          = bool(au_records),
        vst_bundle_keys = {r.bundle_name.replace(" ", "_") for r in vst_records},
        vst_orig_paths  = {str(r.bundle_path) for r in vst_records},
    )


def clear_daw_caches_for_entries(entries: list[QuarantineEntry]) -> None:
    """Clear DAW caches for already-quarantined entries (reads from manifest)."""
    au_entries  = [e for e in entries if e.format == "AU"]
    vst_entries = [e for e in entries if e.format in ("VST3", "VST2")]
    _do_clear_caches(
        has_au          = bool(au_entries),
        vst_bundle_keys = {e.bundle_name.replace(" ", "_") for e in vst_entries},
        vst_orig_paths  = {e.original_path for e in vst_entries},
    )


def restore_plugins(entries: list[QuarantineEntry]) -> tuple[list[QuarantineEntry], list[str]]:
    """Restore plugins with at most one admin auth dialog for all root-owned files.

    Returns (restored_entries, error_strings).
    """
    needs_admin: list[QuarantineEntry] = []
    restored: list[QuarantineEntry] = []
    errors: list[str] = []

    for entry in entries:
        original = Path(entry.original_path)
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            os.rename(entry.quarantine_path, str(original))
            restored.append(entry)
        except PermissionError:
            needs_admin.append(entry)
        except Exception as e:
            errors.append(f"{entry.display_name}: {e}")

    if needs_admin:
        moves = [(e.quarantine_path, e.original_path) for e in needs_admin]
        dest_dirs = {str(Path(dst).parent) for _, dst in moves}
        mkdir_part = " && ".join(f"mkdir -p {shlex.quote(d)}" for d in sorted(dest_dirs))
        mv_part    = " && ".join(f"mv -f {shlex.quote(s)} {shlex.quote(d)}" for s, d in moves)
        result = subprocess.run(
            ["osascript", "-e",
             f'do shell script "{mkdir_part} && {mv_part}" with administrator privileges'],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "Administrator authentication failed or was cancelled."
            errors.extend(f"{e.display_name}: {err}" for e in needs_admin)
        else:
            restored.extend(needs_admin)

    if restored:
        done_paths = {e.quarantine_path for e in restored}
        _save_manifest([m for m in _load_manifest() if m.get("quarantine_path") not in done_paths])

    return restored, errors


def delete_plugins_permanently(entries: list[QuarantineEntry]) -> tuple[list[QuarantineEntry], list[str]]:
    """Delete plugins permanently with at most one admin auth dialog.

    Returns (deleted_entries, error_strings).
    """
    needs_admin: list[QuarantineEntry] = []
    deleted: list[QuarantineEntry] = []
    errors: list[str] = []

    for entry in entries:
        path = Path(entry.quarantine_path)
        try:
            shutil.rmtree(str(path)) if path.is_dir() else path.unlink()
            deleted.append(entry)
        except FileNotFoundError:
            deleted.append(entry)  # already gone — still remove from manifest
        except PermissionError:
            needs_admin.append(entry)
        except Exception as e:
            errors.append(f"{entry.display_name}: {e}")

    if needs_admin:
        rm_part = " && ".join(
            f"rm -rf {shlex.quote(entry.quarantine_path)}" for entry in needs_admin
        )
        result = subprocess.run(
            ["osascript", "-e",
             f'do shell script "{rm_part}" with administrator privileges'],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "Administrator authentication failed or was cancelled."
            errors.extend(f"{e.display_name}: {err}" for e in needs_admin)
        else:
            deleted.extend(needs_admin)

    if deleted:
        done_paths = {e.quarantine_path for e in deleted}
        _save_manifest([m for m in _load_manifest() if m.get("quarantine_path") not in done_paths])

    return deleted, errors
