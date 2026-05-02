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
        done_entries: list[QuarantineEntry] = []
        errors: list[str] = []
        total = len(self._records)

        for i, rec in enumerate(self._records):
            self.progress.emit(i, total, rec.display_name)
            try:
                entry = qm.quarantine_plugin(rec)
                done_entries.append(entry)
            except Exception as e:
                errors.append(f"{rec.display_name}: {e}")

        self.progress.emit(total, total, "Done")
        if errors:
            self.error.emit("\n".join(errors))
        self.finished.emit(done_entries)
