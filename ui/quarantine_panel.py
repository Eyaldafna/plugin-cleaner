from __future__ import annotations
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableView, QVBoxLayout, QWidget,
)
from core.models import QuarantineEntry
import core.quarantine as qm

Q_COL_NAME   = 0
Q_COL_FORMAT = 1
Q_COL_VENDOR = 2
Q_COL_DATE   = 3
Q_COL_SIZE   = 4
Q_HEADERS = ["Name", "Format", "Vendor", "Quarantined", "Size"]


class QuarantineModel(QAbstractTableModel):
    def __init__(self, entries: list[QuarantineEntry], parent=None):
        super().__init__(parent)
        self._entries = entries

    def rowCount(self, _parent=QModelIndex()) -> int:
        return len(self._entries)

    def columnCount(self, _parent=QModelIndex()) -> int:
        return len(Q_HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return Q_HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        e = self._entries[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == Q_COL_NAME:    return e.display_name or e.bundle_name
            if col == Q_COL_FORMAT:  return e.format
            if col == Q_COL_VENDOR:  return e.vendor
            if col == Q_COL_DATE:    return e.quarantined_at[:10]
            if col == Q_COL_SIZE:    return e.size_mb()
        if role == Qt.ItemDataRole.UserRole:
            return e
        return None

    def set_entries(self, entries: list[QuarantineEntry]) -> None:
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def remove_entry(self, entry: QuarantineEntry) -> None:
        for i, e in enumerate(self._entries):
            if e.quarantine_path == entry.quarantine_path:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._entries.pop(i)
                self.endRemoveRows()
                return


class QuarantinePanel(QWidget):
    restored = Signal(str)   # original_path

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._model = QuarantineModel([])
        self._view  = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._view.setSortingEnabled(True)
        self._view.setShowGrid(False)
        self._view.verticalHeader().setVisible(False)
        hdr = self._view.horizontalHeader()
        hdr.resizeSection(Q_COL_NAME,   240)
        hdr.resizeSection(Q_COL_FORMAT,  60)
        hdr.resizeSection(Q_COL_VENDOR, 140)
        hdr.resizeSection(Q_COL_DATE,   100)
        hdr.resizeSection(Q_COL_SIZE,    70)
        hdr.setStretchLastSection(True)
        self._view.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self._view)

        # Bottom action bar
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 8, 10, 8)

        self._info_label = QLabel()
        bar_layout.addWidget(self._info_label)
        bar_layout.addStretch()

        self._clean_btn = QPushButton("Clean DAW Caches")
        self._clean_btn.setToolTip(
            "Remove all quarantined plugins from Reaper and Logic caches.\n"
            "Restart your DAWs after clicking."
        )
        self._clean_btn.clicked.connect(self._on_clean_caches)
        bar_layout.addWidget(self._clean_btn)

        self._restore_btn = QPushButton("↩ Restore")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore)
        bar_layout.addWidget(self._restore_btn)

        self._delete_btn = QPushButton("Delete Permanently")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        bar_layout.addWidget(self._delete_btn)

        layout.addWidget(bar)

        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.refresh()

    def refresh(self) -> None:
        entries = qm.load_quarantine_entries()
        self._model.set_entries(entries)
        self._update_info_label()
        self._restore_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

    def _update_info_label(self) -> None:
        n = self._model.rowCount()
        self._info_label.setText(f"{n} plugin{'s' if n != 1 else ''} quarantined")

    def _selected_entries(self) -> list[QuarantineEntry]:
        idxs = self._view.selectionModel().selectedRows()
        entries = []
        for idx in idxs:
            src = self._view.model().mapToSource(idx) if hasattr(self._view.model(), "mapToSource") else idx
            e = self._model.data(src, Qt.ItemDataRole.UserRole)
            if e:
                entries.append(e)
        return entries

    def _on_clean_caches(self):
        entries = qm.load_quarantine_entries()
        if not entries:
            QMessageBox.information(self, "Nothing to Clean", "No quarantined plugins found.")
            return
        qm.clear_daw_caches_for_entries(entries)
        running = qm.daws_running()
        if running:
            daw_str = " and ".join(running)
            QMessageBox.information(
                self, "Restart Required",
                f"Caches cleaned for {len(entries)} quarantined plugin{'s' if len(entries) != 1 else ''}.\n\n"
                f"Quit and reopen {daw_str} to remove them from the plugin browser.",
            )
        else:
            QMessageBox.information(
                self, "Caches Cleaned",
                f"Caches cleaned for {len(entries)} quarantined plugin{'s' if len(entries) != 1 else ''}.",
            )

    def _on_selection_changed(self):
        has = bool(self._view.selectionModel().selectedRows())
        self._restore_btn.setEnabled(has)
        self._delete_btn.setEnabled(has)

    def _on_restore(self):
        entries = self._selected_entries()
        if not entries:
            return
        n = len(entries)
        msg = (f"Restore '{entries[0].display_name}' to its original location?\n\n{entries[0].original_path}"
               if n == 1 else f"Restore {n} plugins to their original locations?")
        ans = QMessageBox.question(
            self, "Restore Plugin", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        restored, errors = qm.restore_plugins(entries)
        for entry in restored:
            self._model.remove_entry(entry)
            self.restored.emit(entry.original_path)
        self._update_info_label()
        if errors:
            QMessageBox.critical(self, "Restore Failed", "\n".join(errors))

    def _on_delete(self):
        entries = self._selected_entries()
        if not entries:
            return
        n = len(entries)
        msg = (f"Permanently delete '{entries[0].display_name}'?\n\nThis cannot be undone."
               if n == 1 else f"Permanently delete {n} plugins?\n\nThis cannot be undone.")
        ans = QMessageBox.question(
            self, "Delete Permanently", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        deleted, errors = qm.delete_plugins_permanently(entries)
        for entry in deleted:
            self._model.remove_entry(entry)
        self._update_info_label()
        if errors:
            QMessageBox.critical(self, "Delete Failed", "\n".join(errors))
