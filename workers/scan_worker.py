from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from core.scanner import scan_all
from core.session_parser import (
    parse_logic_sessions, parse_reaper_sessions, parse_wavelab_usage,
    SESSIONS_ROOT,
)
from core.resolver import resolve
from core.models import PluginRecord


class ScanWorker(QThread):
    progress  = Signal(int, int, str)   # current, total, message
    finished  = Signal(list)            # list[PluginRecord]
    error     = Signal(str)

    def __init__(self, sessions_root: Path | None = None, parent=None):
        super().__init__(parent)
        self._sessions_root = sessions_root or SESSIONS_ROOT

    def run(self):
        try:
            records: list[PluginRecord] = []

            # Phase 1: plugin inventory
            def plugin_cb(msg: str):
                self.progress.emit(0, 100, msg)

            records = scan_all(progress_cb=plugin_cb)
            n = len(records)
            self.progress.emit(10, 100, f"Found {n} plugin records. Scanning Reaper sessions…")

            # Phase 2: Reaper sessions
            def reaper_cb(i, total, msg):
                pct = 10 + int(40 * i / max(total, 1))
                self.progress.emit(pct, 100, msg)

            reaper_refs = parse_reaper_sessions(root=self._sessions_root, progress_cb=reaper_cb)
            self.progress.emit(50, 100, f"Reaper done ({len(reaper_refs)} refs). Scanning Logic…")

            # Phase 3: Logic sessions
            def logic_cb(i, total, msg):
                pct = 50 + int(35 * i / max(total, 1))
                self.progress.emit(pct, 100, msg)

            logic_refs = parse_logic_sessions(root=self._sessions_root, progress_cb=logic_cb)
            self.progress.emit(85, 100, f"Logic done ({len(logic_refs)} refs). Scanning WaveLab…")

            # Phase 4: WaveLab
            def wl_cb(i, total, msg):
                self.progress.emit(90, 100, msg)

            wl_refs = parse_wavelab_usage(progress_cb=wl_cb)
            self.progress.emit(95, 100, "Resolving…")

            all_refs = reaper_refs + logic_refs + wl_refs
            resolve(records, all_refs)

            self.progress.emit(100, 100, "Done")
            self.finished.emit(records)

        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())
