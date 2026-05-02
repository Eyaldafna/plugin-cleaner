from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QHBoxLayout, QLabel,
    QLineEdit, QRadioButton, QWidget,
)
from ui.theme import COLOR_TEXT_DIM


class FilterBar(QWidget):
    search_changed  = Signal(str)
    status_changed  = Signal(str)   # "All" | "Used" | "Unused"
    formats_changed = Signal(set)   # {"AU","VST3","VST2"}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        # Search box
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search plugins…")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self.search_changed)
        layout.addWidget(self.search)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        layout.addWidget(sep)

        # Format checkboxes
        self._au_cb   = QCheckBox("AU")
        self._vst3_cb = QCheckBox("VST3")
        self._vst2_cb = QCheckBox("VST2")
        for cb in (self._au_cb, self._vst3_cb, self._vst2_cb):
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_format_changed)
            layout.addWidget(cb)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        layout.addWidget(sep2)

        # Status radios
        self._status_group = QButtonGroup(self)
        for label in ("All", "Used", "Unused"):
            rb = QRadioButton(label)
            self._status_group.addButton(rb)
            layout.addWidget(rb)
            if label == "All":
                rb.setChecked(True)
        self._status_group.buttonClicked.connect(
            lambda btn: self.status_changed.emit(btn.text())
        )

        layout.addStretch()

        # Stats label
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px;")
        layout.addWidget(self.stats_label)

    def _on_format_changed(self):
        fmts: set[str] = set()
        if self._au_cb.isChecked():
            fmts.add("AU")
        if self._vst3_cb.isChecked():
            fmts.add("VST3")
        if self._vst2_cb.isChecked():
            fmts.add("VST2")
        self.formats_changed.emit(fmts)

    def update_stats(self, total: int, used: int, unused: int, quarantined: int) -> None:
        self.stats_label.setText(
            f"{total} plugins · {used} used · {unused} unused"
            + (f" · {quarantined} quarantined" if quarantined else "")
        )
