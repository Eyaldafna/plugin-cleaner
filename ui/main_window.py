from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QSplitter, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from core.models import PluginRecord, UsageStatus
import core.quarantine as qm
from core.session_parser import SESSIONS_ROOT
from ui.detail_panel import DetailPanel
from ui.filter_bar import FilterBar
from ui.plugin_table import make_plugin_table
from ui.quarantine_panel import QuarantinePanel
from ui.stats_panel import StatsPanel
from workers.quarantine_worker import QuarantineWorker
from workers.scan_worker import ScanWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plugin Cleaner")
        self.resize(1100, 720)

        self._records: list[PluginRecord] = []
        self._scan_worker: ScanWorker | None = None
        self._q_worker: QuarantineWorker | None = None
        self._sessions_root: Path = SESSIONS_ROOT

        self._build_ui()
        self._start_scan()

    # ------------------------------------------------------------------ Build UI

    def _build_ui(self):
        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._progress = QProgressBar()
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        self._status_label = QLabel("Initialising…")
        self._status_bar.addPermanentWidget(self._status_label)
        self._status_bar.addPermanentWidget(self._progress)

        # Tab widget
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # ---- Main tab ----
        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Filter bar (lives in a toolbar)
        self._filter_bar = FilterBar()
        self._filter_bar.search_changed.connect(self._on_search)
        self._filter_bar.status_changed.connect(self._on_status_filter)
        self._filter_bar.formats_changed.connect(self._on_format_filter)
        main_layout.addWidget(self._filter_bar)

        # Splitter: table + detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Plugin table
        self._view, self._table_model, self._proxy = make_plugin_table([])
        self._view.selectionModel().selectionChanged.connect(self._on_selection)
        splitter.addWidget(self._view)

        # Detail panel
        self._detail = DetailPanel()
        splitter.addWidget(self._detail)
        splitter.setSizes([800, 280])
        splitter.setCollapsible(1, True)
        main_layout.addWidget(splitter)

        # Bottom action bar
        action_bar = QWidget()
        ab_layout = QHBoxLayout(action_bar)
        ab_layout.setContentsMargins(10, 8, 10, 8)

        self._sessions_btn = QPushButton()
        self._sessions_btn.setStyleSheet("color: #888; font-size: 11px; text-align: left; border: none; padding: 0;")
        self._sessions_btn.clicked.connect(self._browse_sessions)
        self._update_sessions_btn()
        ab_layout.addWidget(self._sessions_btn)

        ab_layout.addStretch()

        self._sel_label = QLabel("No plugins selected")
        self._sel_label.setStyleSheet("color: #888; font-size: 12px;")
        ab_layout.addWidget(self._sel_label)
        ab_layout.addStretch()

        self._select_unused_btn = QPushButton("Select All Unused")
        self._select_unused_btn.clicked.connect(self._select_all_unused)
        self._select_unused_btn.setEnabled(False)
        ab_layout.addWidget(self._select_unused_btn)

        self._quarantine_btn = QPushButton("Quarantine Selected")
        self._quarantine_btn.setObjectName("primary")
        self._quarantine_btn.clicked.connect(self._on_quarantine)
        self._quarantine_btn.setEnabled(False)
        ab_layout.addWidget(self._quarantine_btn)

        main_layout.addWidget(action_bar)
        self._tabs.addTab(main_tab, "Plugins")

        # ---- Quarantine tab ----
        self._q_panel = QuarantinePanel()
        self._q_panel.restored.connect(self._on_plugin_restored)
        self._tabs.addTab(self._q_panel, "Quarantine")
        self._update_quarantine_badge()

        # ---- Stats tab ----
        self._stats_panel = StatsPanel()
        self._tabs.addTab(self._stats_panel, "Statistics")

    # ------------------------------------------------------------------ Sessions folder

    def _update_sessions_btn(self):
        home = Path.home()
        try:
            label = "~/" + str(self._sessions_root.relative_to(home))
        except ValueError:
            label = str(self._sessions_root)
        self._sessions_btn.setText(f"Sessions: {label}  ▾")

    def _browse_sessions(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Select Sessions Folder", str(self._sessions_root),
        )
        if not chosen:
            return
        self._sessions_root = Path(chosen)
        self._update_sessions_btn()
        self._start_scan()

    # ------------------------------------------------------------------ Scanning

    def _start_scan(self):
        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._quarantine_btn.setEnabled(False)
        self._select_unused_btn.setEnabled(False)

        self._scan_worker = ScanWorker(sessions_root=self._sessions_root)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_done)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, current: int, _total: int, msg: str):
        self._progress.setValue(current)
        self._status_label.setText(msg)

    def _on_scan_done(self, records: list[PluginRecord]):
        self._records = records
        self._table_model.set_records(records)
        self._progress.setVisible(False)
        self._select_unused_btn.setEnabled(True)
        self._update_stats()
        self._stats_panel.update_stats(records)
        used   = sum(1 for r in records if r.status == UsageStatus.USED)
        unused = sum(1 for r in records if r.status == UsageStatus.UNUSED)
        self._status_label.setText(f"Scan complete — {used} used, {unused} unused")

    def _on_scan_error(self, msg: str):
        self._progress.setVisible(False)
        self._status_label.setText("Scan error — see details")
        QMessageBox.critical(self, "Scan Error", msg)

    # ------------------------------------------------------------------ Filters

    def _on_search(self, text: str):
        self._proxy.setFilterFixedString(text)
        self._update_stats()

    def _on_status_filter(self, status: str):
        self._proxy.set_status_filter(status)
        self._update_stats()

    def _on_format_filter(self, formats: set):
        self._proxy.set_format_filter(formats)
        self._update_stats()

    def _update_stats(self):
        total = used = unused = quarantined = 0
        for r in self._records:
            total += 1
            if r.is_quarantined:
                quarantined += 1
            if r.status == UsageStatus.USED:
                used += 1
            elif r.status == UsageStatus.UNUSED:
                unused += 1
        self._filter_bar.update_stats(total, used, unused, quarantined)

    # ------------------------------------------------------------------ Selection

    def _on_selection(self):
        idxs = self._view.selectionModel().selectedRows()
        if not idxs:
            self._detail.clear()
            self._sel_label.setText("No plugins selected")
            self._quarantine_btn.setEnabled(False)
            return

        # Resolve all selected indices once
        selected_records = [
            self._table_model.record_at(self._proxy.mapToSource(i).row())
            for i in idxs
        ]
        self._detail.show_record(selected_records[0])
        quarantinable = [r for r in selected_records if not r.is_quarantined]
        n = len(idxs)
        self._sel_label.setText(
            f"{n} selected" + (f" · {len(quarantinable)} quarantinable" if len(quarantinable) < n else "")
        )
        self._quarantine_btn.setEnabled(bool(quarantinable))

    def _select_all_unused(self):
        self._view.clearSelection()
        selection = self._view.selectionModel()
        proxy = self._proxy
        for row in range(proxy.rowCount()):
            idx = proxy.index(row, 0)
            src = proxy.mapToSource(idx)
            rec = self._table_model.record_at(src.row())
            if rec.status == UsageStatus.UNUSED and not rec.is_quarantined:
                selection.select(
                    proxy.index(row, 0),
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )

    # ------------------------------------------------------------------ Quarantine

    def _on_quarantine(self):
        idxs = self._view.selectionModel().selectedRows()
        records_to_q = [
            self._table_model.record_at(self._proxy.mapToSource(i).row())
            for i in idxs
            if not self._table_model.record_at(self._proxy.mapToSource(i).row()).is_quarantined
        ]
        if not records_to_q:
            return

        # Check DAWs
        running = qm.daws_running()
        if running:
            ans = QMessageBox.warning(
                self, "DAW Running",
                f"{', '.join(running)} is currently open.\n\nQuarantining plugins while a DAW is running "
                "may cause instability. Close your DAWs first, or proceed at your own risk.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if ans != QMessageBox.StandardButton.Ok:
                return

        total_mb = sum(r.size_bytes for r in records_to_q) / (1024 * 1024)
        ans = QMessageBox.question(
            self, "Quarantine Plugins",
            f"Move {len(records_to_q)} plugin{'s' if len(records_to_q) > 1 else ''} "
            f"({total_mb:.0f} MB) to ~/PluginQuarantine?\n\n"
            "They will be invisible to your DAWs until restored or permanently deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self._quarantine_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(records_to_q))

        self._q_worker = QuarantineWorker(records_to_q)
        self._q_worker.progress.connect(self._on_quarantine_progress)
        self._q_worker.finished.connect(self._on_quarantine_done)
        self._q_worker.error.connect(lambda msg: QMessageBox.warning(self, "Quarantine Errors", msg))
        self._q_worker.start()

    def _on_quarantine_progress(self, i: int, _total: int, name: str) -> None:
        self._progress.setValue(i)
        self._status_label.setText(f"Quarantining {name}…")

    def _on_quarantine_done(self, entries):
        self._progress.setVisible(False)
        n = len(entries)
        self._status_label.setText(f"{n} plugin{'s' if n > 1 else ''} quarantined")
        # Refresh table to reflect new quarantine state
        self._table_model.set_records(self._records)
        self._q_panel.refresh()
        self._update_quarantine_badge()
        self._update_stats()
        self._detail.clear()
        self._view.clearSelection()

    def _on_plugin_restored(self, original_path: str):
        self._update_quarantine_badge()
        # Mark record as not quarantined
        for rec in self._records:
            if str(rec.bundle_path) == original_path:
                rec.is_quarantined = False
                self._table_model.update_record(rec)
                break
        self._update_stats()

    def _update_quarantine_badge(self):
        entries = qm.load_quarantine_entries()
        n = len(entries)
        label = "Quarantine" if n == 0 else f"Quarantine ({n})"
        self._tabs.setTabText(1, label)
