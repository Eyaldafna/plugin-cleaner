from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)
from core.models import PluginRecord, UsageStatus
from ui.theme import COLOR_ACCENT, COLOR_TEXT_DIM, COLOR_USED, COLOR_UNUSED, COLOR_WARN


class DetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._name_label    = QLabel()
        self._name_label.setWordWrap(True)
        self._name_label.setStyleSheet("font-size: 15px; font-weight: 600;")

        self._vendor_label  = QLabel()
        self._vendor_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px;")

        self._format_label  = QLabel()
        self._version_label = QLabel()
        self._status_label  = QLabel()
        self._path_label    = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px;")
        self._size_label    = QLabel()

        self._sessions_header = QLabel("Sessions")
        self._sessions_header.setObjectName("sectionHeader")
        self._sessions_list = QListWidget()
        self._sessions_list.setMaximumHeight(160)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)

        for w in [
            self._name_label, self._vendor_label,
            sep,
            self._make_row("Format", self._format_label),
            self._make_row("Version", self._version_label),
            self._make_row("Size", self._size_label),
            self._make_row("Status", self._status_label),
            self._sessions_header,
            self._sessions_list,
        ]:
            if isinstance(w, QWidget):
                layout.addWidget(w)
            else:
                layout.addLayout(w)

        layout.addWidget(self._path_label)
        layout.addStretch()

        self.clear()

    def _make_row(self, label_text: str, value_widget: QLabel):
        from PySide6.QtWidgets import QHBoxLayout
        row = QHBoxLayout()
        lbl = QLabel(label_text + ":")
        lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px; min-width: 55px;")
        row.addWidget(lbl)
        row.addWidget(value_widget)
        row.addStretch()
        return row

    def clear(self):
        self._name_label.setText("Select a plugin")
        self._name_label.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {COLOR_TEXT_DIM};")
        self._vendor_label.setText("")
        self._format_label.setText("")
        self._version_label.setText("")
        self._status_label.setText("")
        self._size_label.setText("")
        self._path_label.setText("")
        self._sessions_list.clear()
        self._sessions_header.setVisible(False)
        self._sessions_list.setVisible(False)

    def show_record(self, rec: PluginRecord) -> None:
        self._name_label.setText(rec.display_name or rec.bundle_name)
        self._name_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #d4d4d4;")
        self._vendor_label.setText(rec.vendor)
        self._format_label.setText(rec.format.value)
        self._version_label.setText(rec.version or "—")
        self._size_label.setText(rec.size_mb())
        self._path_label.setText(str(rec.bundle_path))

        if rec.is_quarantined:
            self._status_label.setText("Quarantined")
            self._status_label.setStyleSheet(f"color: {COLOR_WARN};")
        elif rec.status == UsageStatus.USED:
            self._status_label.setText("● Used")
            self._status_label.setStyleSheet(f"color: {COLOR_USED};")
        else:
            self._status_label.setText("○ Unused")
            self._status_label.setStyleSheet(f"color: {COLOR_UNUSED};")

        self._sessions_list.clear()
        if rec.session_refs:
            self._sessions_header.setVisible(True)
            self._sessions_list.setVisible(True)
            self._sessions_header.setText(f"Sessions ({len(rec.session_refs)})")
            seen: set[str] = set()
            for ref in rec.session_refs:
                short = ref if len(ref) < 60 else "…" + ref[-57:]
                if short not in seen:
                    seen.add(short)
                    self._sessions_list.addItem(QListWidgetItem(short))
        else:
            self._sessions_header.setVisible(False)
            self._sessions_list.setVisible(False)
