from __future__ import annotations
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .models import PluginRecord, QuarantineEntry

QUARANTINE_DIR = Path.home() / "PluginQuarantine"
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


def quarantine_plugin(record: PluginRecord) -> QuarantineEntry:
    """Move plugin bundle to quarantine folder. Returns the QuarantineEntry."""
    dest_dir = QUARANTINE_DIR / record.format.value
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / record.bundle_name

    # If a file with that name already exists in quarantine, suffix it
    if dest.exists():
        stem = record.bundle_path.stem
        suffix = record.bundle_path.suffix
        dest = dest_dir / f"{stem}_dup{suffix}"

    os.rename(str(record.bundle_path), str(dest))

    entry = QuarantineEntry(
        bundle_name     = record.bundle_name,
        format          = record.format.value,
        original_path   = str(record.bundle_path),
        quarantine_path = str(dest),
        quarantined_at  = datetime.now().isoformat(timespec="seconds"),
        display_name    = record.display_name,
        vendor          = record.vendor,
        version         = record.version,
        was_status      = record.status.value,
        size_bytes      = record.size_bytes,
    )

    entries = _load_manifest()
    entries.append(entry.__dict__)
    _save_manifest(entries)
    record.is_quarantined = True
    return entry


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
