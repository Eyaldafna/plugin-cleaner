from __future__ import annotations
from PySide6.QtCore import QThread, Signal
import core.quarantine as qm
from core.models import PluginRecord, QuarantineEntry


class QuarantineWorker(QThread):
    progress  = Signal(int, int, str)   # done, total, plugin name
    finished  = Signal(list)            # list[QuarantineEntry] successfully quarantined
    error     = Signal(str)

    def __init__(self, records: list[PluginRecord], parent=None):
        super().__init__(parent)
        self._records = records

    def run(self):
        done: list[QuarantineEntry] = []
        needs_admin: list[PluginRecord] = []
        errors: list[str] = []
        total = len(self._records)

        # Phase 1: attempt without privileges (user-owned plugins move instantly)
        for i, rec in enumerate(self._records):
            self.progress.emit(i, total, rec.display_name)
            try:
                done.append(qm.quarantine_plugin(rec))
            except PermissionError:
                needs_admin.append(rec)
            except Exception as e:
                errors.append(f"{rec.display_name}: {e}")

        # Phase 2: batch admin move for root-owned plugins (one password dialog)
        if needs_admin:
            self.progress.emit(total - len(needs_admin), total,
                               f"Admin access needed for {len(needs_admin)} plugins…")
            try:
                done.extend(qm.quarantine_plugins_privileged(needs_admin))
            except PermissionError as e:
                errors.append(str(e))

        if done:
            self.progress.emit(total, total, "Cleaning DAW caches…")
            quarantined_records = [r for r in self._records if r.is_quarantined]
            qm.clear_daw_caches(quarantined_records)

        self.progress.emit(total, total, "Done")
        if errors:
            self.error.emit("\n".join(errors))
        self.finished.emit(done)
