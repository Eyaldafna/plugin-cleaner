from __future__ import annotations
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTableView

from core.models import PluginFormat, PluginRecord, UsageStatus
from ui.theme import COLOR_USED, COLOR_UNUSED, COLOR_WARN

COL_STATUS = 0
COL_NAME   = 1
COL_VENDOR = 2
COL_FORMAT = 3
COL_VER    = 4
COL_SIZE   = 5
COL_SESSIONS = 6
HEADERS = ["", "Name", "Vendor", "Format", "Version", "Size", "Sessions"]


class PluginTableModel(QAbstractTableModel):
    def __init__(self, records: list[PluginRecord], parent=None):
        super().__init__(parent)
        self._records = records

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        rec = self._records[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_STATUS:
                return ""
            if col == COL_NAME:
                return rec.display_name
            if col == COL_VENDOR:
                return rec.vendor
            if col == COL_FORMAT:
                return rec.format.value
            if col == COL_VER:
                return rec.version
            if col == COL_SIZE:
                return rec.size_mb()
            if col == COL_SESSIONS:
                n = len(rec.session_refs)
                return str(n) if n > 0 else "—"

        if role == Qt.ItemDataRole.ForegroundRole:
            if rec.is_quarantined:
                return QColor(COLOR_WARN)
            if rec.status == UsageStatus.UNUSED:
                return QColor("#999999")

        if role == Qt.ItemDataRole.UserRole:
            return rec

        if role == Qt.ItemDataRole.UserRole + 1:
            # Sort key for size column
            if col == COL_SIZE:
                return rec.size_bytes
            if col == COL_SESSIONS:
                return len(rec.session_refs)
            return None

        return None

    def record_at(self, row: int) -> PluginRecord:
        return self._records[row]

    def set_records(self, records: list[PluginRecord]) -> None:
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def update_record(self, rec: PluginRecord) -> None:
        for i, r in enumerate(self._records):
            if r is rec:
                idx_l = self.index(i, 0)
                idx_r = self.index(i, len(HEADERS) - 1)
                self.dataChanged.emit(idx_l, idx_r)
                break


class StatusDotDelegate(QStyledItemDelegate):
    DOT_R = 5

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        super().paint(painter, option, index)
        rec: PluginRecord | None = index.data(Qt.ItemDataRole.UserRole)
        if rec is None:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if rec.is_quarantined:
            color = QColor(COLOR_WARN)
        elif rec.status == UsageStatus.USED:
            color = QColor(COLOR_USED)
        else:
            color = QColor(COLOR_UNUSED)

        cx = option.rect.x() + option.rect.width() // 2
        cy = option.rect.y() + option.rect.height() // 2
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - self.DOT_R, cy - self.DOT_R, self.DOT_R * 2, self.DOT_R * 2)
        painter.restore()


class PluginSortFilterModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_filter: str = "All"   # "All" | "Used" | "Unused"
        self._format_filter: set[str] = {"AU", "VST3", "VST2"}
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)   # search all columns
        self.setSortRole(Qt.ItemDataRole.UserRole + 1)

    def set_status_filter(self, status: str) -> None:
        self._status_filter = status
        self.invalidateFilter()

    def set_format_filter(self, formats: set[str]) -> None:
        self._format_filter = formats
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        rec: PluginRecord = model.data(model.index(source_row, COL_STATUS), Qt.ItemDataRole.UserRole)
        if rec is None:
            return True

        # Format filter
        if rec.format.value not in self._format_filter:
            return False

        # Status filter
        if self._status_filter == "Used" and rec.status != UsageStatus.USED:
            return False
        if self._status_filter == "Unused" and rec.status != UsageStatus.UNUSED:
            return False

        # Text search (check name + vendor)
        pattern = self.filterRegularExpression().pattern()
        if pattern:
            text = f"{rec.display_name} {rec.vendor} {rec.format.value}".lower()
            if pattern.lower() not in text:
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        col = left.column()
        # Numeric sort for size and sessions
        if col in (COL_SIZE, COL_SESSIONS):
            lv = self.sourceModel().data(left, Qt.ItemDataRole.UserRole + 1) or 0
            rv = self.sourceModel().data(right, Qt.ItemDataRole.UserRole + 1) or 0
            return lv < rv
        # Default string sort
        lv = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole) or ""
        rv = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return str(lv).lower() < str(rv).lower()


def make_plugin_table(records: list[PluginRecord]) -> tuple[QTableView, PluginTableModel, PluginSortFilterModel]:
    model  = PluginTableModel(records)
    proxy  = PluginSortFilterModel()
    proxy.setSourceModel(model)

    view = QTableView()
    view.setModel(proxy)
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
    view.setSortingEnabled(True)
    view.setShowGrid(False)
    view.verticalHeader().setVisible(False)
    view.horizontalHeader().setStretchLastSection(False)

    # Set status dot delegate for col 0
    view.setItemDelegateForColumn(COL_STATUS, StatusDotDelegate(view))

    # Column widths
    hdr = view.horizontalHeader()
    hdr.resizeSection(COL_STATUS,   22)
    hdr.resizeSection(COL_NAME,    220)
    hdr.resizeSection(COL_VENDOR,  140)
    hdr.resizeSection(COL_FORMAT,   60)
    hdr.resizeSection(COL_VER,      70)
    hdr.resizeSection(COL_SIZE,     70)
    hdr.resizeSection(COL_SESSIONS, 70)
    hdr.setMinimumSectionSize(22)

    # Sort by name by default
    proxy.sort(COL_NAME, Qt.SortOrder.AscendingOrder)

    view.setRowHeight(0, 26)
    view.verticalHeader().setDefaultSectionSize(26)

    return view, model, proxy
