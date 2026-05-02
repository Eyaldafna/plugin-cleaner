from __future__ import annotations
from collections import Counter

from PySide6.QtCharts import (
    QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView,
    QHorizontalBarSeries, QPieSeries, QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from core.models import PluginFormat, PluginRecord, UsageStatus
from ui.theme import (
    COLOR_ACCENT, COLOR_BG_ALT,
    COLOR_BORDER, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_USED, COLOR_WARN,
)


def _chart_base(title: str = "") -> QChart:
    chart = QChart()
    chart.setTitle(title)
    chart.setBackgroundBrush(QColor(COLOR_BG_ALT))
    chart.setBackgroundRoundness(8)
    chart.setTitleBrush(QColor(COLOR_TEXT))
    f = QFont()
    f.setPointSize(11)
    f.setWeight(QFont.Weight.Medium)
    chart.setTitleFont(f)
    chart.legend().setLabelColor(QColor(COLOR_TEXT_DIM))
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
    chart.setMargins(QMargins(12, 8, 12, 8))
    chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
    chart.setAnimationDuration(400)
    return chart


def _chart_view(chart: QChart, min_h: int = 280) -> QChartView:
    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(min_h)
    view.setStyleSheet(f"background: {COLOR_BG_ALT}; border: 1px solid {COLOR_BORDER}; border-radius: 8px;")
    return view


def _axis_style(axis: QBarCategoryAxis | QValueAxis) -> None:
    axis.setLabelsColor(QColor(COLOR_TEXT_DIM))
    axis.setGridLineColor(QColor(COLOR_BORDER))
    axis.setLinePen(QColor(COLOR_BORDER))
    f = QFont()
    f.setPointSize(9)
    axis.setLabelsFont(f)


# ── Stat card ──────────────────────────────────────────────────────────────

class StatCard(QWidget):
    def __init__(self, value: str, label: str, color: str = COLOR_ACCENT, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {COLOR_BG_ALT}; border: 1px solid {COLOR_BORDER};"
            f" border-radius: 8px; padding: 4px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 700; border: none;")
        layout.addWidget(val)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px; border: none;")
        layout.addWidget(lbl)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


# ── Chart builders ─────────────────────────────────────────────────────────

def _build_format_donut(records: list[PluginRecord]) -> QChartView:
    chart = _chart_base()
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)

    series = QPieSeries()
    series.setHoleSize(0.45)

    data = []
    for fmt in PluginFormat:
        used   = sum(1 for r in records if r.format == fmt and r.status == UsageStatus.USED)
        unused = sum(1 for r in records if r.format == fmt and r.status == UsageStatus.UNUSED)
        data.append((fmt.value, used, unused))

    colors = {
        ("AU",   "Used"):   "#4caf50",
        ("AU",   "Unused"): "#2e5e32",
        ("VST3", "Used"):   "#4a9eff",
        ("VST3", "Unused"): "#1a3a5e",
        ("VST2", "Used"):   "#ff9800",
        ("VST2", "Unused"): "#7a4800",
    }

    for fmt_name, used, unused in data:
        if used:
            sl = series.append(f"{fmt_name} Used ({used})", used)
            sl.setColor(QColor(colors.get((fmt_name, "Used"), "#4caf50")))
            sl.setLabelVisible(False)
        if unused:
            sl = series.append(f"{fmt_name} Unused ({unused})", unused)
            sl.setColor(QColor(colors.get((fmt_name, "Unused"), "#888")))
            sl.setLabelVisible(False)

    chart.addSeries(series)

    # Centre label
    total = len(records)
    used_t = sum(1 for r in records if r.status == UsageStatus.USED)
    pct = int(100 * used_t / total) if total else 0
    chart.setTitle(f"Format breakdown  ·  {pct}% used")

    view = _chart_view(chart, 300)
    return view


def _build_vendor_unused_bar(records: list[PluginRecord], top_n: int = 12) -> QChartView:
    unused = [r for r in records if r.status == UsageStatus.UNUSED and r.vendor]
    vendor_count = Counter(r.vendor for r in unused)
    top = vendor_count.most_common(top_n)
    top.reverse()   # horizontal bar: bottom = most

    categories = [v for v, _ in top]
    counts      = [c for _, c in top]

    bar_set = QBarSet("Unused plugins")
    bar_set.setColor(QColor("#c0392b"))
    bar_set.setLabelColor(QColor(COLOR_TEXT))
    for c in counts:
        bar_set.append(c)

    series = QHorizontalBarSeries()
    series.append(bar_set)
    series.setLabelsVisible(True)
    series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsOutsideEnd)

    chart = _chart_base("Unused plugins by vendor")
    chart.addSeries(series)
    chart.legend().hide()

    cat_axis = QBarCategoryAxis()
    cat_axis.append(categories)
    _axis_style(cat_axis)
    chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(cat_axis)

    val_axis = QValueAxis()
    val_axis.setRange(0, max(counts) * 1.18)
    val_axis.setLabelFormat("%d")
    _axis_style(val_axis)
    chart.addAxis(val_axis, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(val_axis)

    return _chart_view(chart, 380)


def _build_reclaimable_bar(records: list[PluginRecord], top_n: int = 12) -> QChartView:
    unused = [r for r in records if r.status == UsageStatus.UNUSED and r.vendor]
    # Sum GB per vendor
    vendor_gb: dict[str, float] = {}
    for r in unused:
        vendor_gb[r.vendor] = vendor_gb.get(r.vendor, 0) + r.size_bytes / 1024**3

    top = sorted(vendor_gb.items(), key=lambda x: x[1], reverse=True)[:top_n]
    top.reverse()

    categories = [v for v, _ in top]
    values      = [round(gb, 2) for _, gb in top]

    bar_set = QBarSet("GB reclaimable")
    bar_set.setColor(QColor(COLOR_WARN))
    bar_set.setLabelColor(QColor(COLOR_TEXT))
    for v in values:
        bar_set.append(v)

    series = QHorizontalBarSeries()
    series.append(bar_set)
    series.setLabelsVisible(True)
    series.setLabelsFormat("@value GB")
    series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsOutsideEnd)

    chart = _chart_base("Reclaimable disk space by vendor (GB)")
    chart.addSeries(series)
    chart.legend().hide()

    cat_axis = QBarCategoryAxis()
    cat_axis.append(categories)
    _axis_style(cat_axis)
    chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(cat_axis)

    val_axis = QValueAxis()
    val_axis.setRange(0, max(values) * 1.2)
    val_axis.setLabelFormat("%.1f")
    _axis_style(val_axis)
    chart.addAxis(val_axis, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(val_axis)

    return _chart_view(chart, 380)


def _build_workhorse_bar(records: list[PluginRecord], top_n: int = 12) -> QChartView:
    used = [r for r in records if r.status == UsageStatus.USED]
    top = sorted(used, key=lambda r: len(r.session_refs), reverse=True)[:top_n]
    top.reverse()

    categories = [f"{r.display_name[:28]}" for r in top]
    counts      = [len(r.session_refs) for r in top]

    bar_set = QBarSet("Sessions")
    bar_set.setColor(QColor(COLOR_USED))
    bar_set.setLabelColor(QColor(COLOR_TEXT))
    for c in counts:
        bar_set.append(c)

    series = QHorizontalBarSeries()
    series.append(bar_set)
    series.setLabelsVisible(True)
    series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsOutsideEnd)

    chart = _chart_base("Your most-used plugins (session count)")
    chart.addSeries(series)
    chart.legend().hide()

    cat_axis = QBarCategoryAxis()
    cat_axis.append(categories)
    _axis_style(cat_axis)
    chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(cat_axis)

    val_axis = QValueAxis()
    val_axis.setRange(0, max(counts) * 1.2)
    val_axis.setLabelFormat("%d")
    _axis_style(val_axis)
    chart.addAxis(val_axis, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(val_axis)

    return _chart_view(chart, 380)


def _build_format_used_bar(records: list[PluginRecord]) -> QChartView:
    used_set   = QBarSet("Used")
    unused_set = QBarSet("Unused")
    used_set.setColor(QColor(COLOR_USED))
    unused_set.setColor(QColor("#555555"))
    used_set.setLabelColor(QColor(COLOR_TEXT))
    unused_set.setLabelColor(QColor(COLOR_TEXT))

    categories = []
    for fmt in PluginFormat:
        used   = sum(1 for r in records if r.format == fmt and r.status == UsageStatus.USED)
        unused = sum(1 for r in records if r.format == fmt and r.status == UsageStatus.UNUSED)
        used_set.append(used)
        unused_set.append(unused)
        categories.append(fmt.value)

    series = QBarSeries()
    series.append(used_set)
    series.append(unused_set)
    series.setLabelsVisible(True)
    series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

    chart = _chart_base("Used vs Unused per format")
    chart.addSeries(series)

    cat_axis = QBarCategoryAxis()
    cat_axis.append(categories)
    _axis_style(cat_axis)
    chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(cat_axis)

    max_val = max(
        sum(1 for r in records if r.format == fmt)
        for fmt in PluginFormat
    )
    val_axis = QValueAxis()
    val_axis.setRange(0, max_val * 1.15)
    val_axis.setLabelFormat("%d")
    _axis_style(val_axis)
    chart.addAxis(val_axis, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(val_axis)

    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
    return _chart_view(chart, 280)


# ── Insight rows ────────────────────────────────────────────────────────────

class InsightRow(QWidget):
    def __init__(self, icon: str, text: str, color: str = COLOR_ACCENT, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {COLOR_BG_ALT}; border: 1px solid {COLOR_BORDER};"
            " border-radius: 6px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        ico = QLabel(icon)
        ico.setStyleSheet(f"font-size: 20px; border: none; color: {color};")
        ico.setFixedWidth(28)
        layout.addWidget(ico)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px; border: none;")
        layout.addWidget(lbl, 1)


# ── Main stats panel ────────────────────────────────────────────────────────

class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel("Run a scan to see statistics")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 14px;")
        self._outer.addWidget(self._placeholder)

    def update_stats(self, records: list[PluginRecord]) -> None:
        # Remove old content
        while self._outer.count():
            item = self._outer.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Scroll area wraps everything
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Single-pass aggregation ─────────────────────────────────────
        used_n = unused_n = vst2_n = 0
        total_bytes = reclaim_bytes = 0
        vendor_reclaim: dict[str, float] = {}
        by_family: dict[str, list[PluginRecord]] = {}
        top_used_list: list[PluginRecord] = []

        for r in records:
            total_bytes += r.size_bytes
            if r.format == PluginFormat.VST2:
                vst2_n += 1
            if r.status == UsageStatus.USED:
                used_n += 1
                top_used_list.append(r)
            else:
                unused_n += 1
                reclaim_bytes += r.size_bytes
                if r.vendor:
                    vendor_reclaim[r.vendor] = vendor_reclaim.get(r.vendor, 0.0) + r.size_bytes / 1024**3
            by_family.setdefault(r.family_key, []).append(r)

        total     = len(records)
        total_gb  = total_bytes / 1024**3
        reclaim_gb = reclaim_bytes / 1024**3
        pct_used  = int(100 * used_n / total) if total else 0

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.addWidget(StatCard(str(total),        "Total plugin records",         COLOR_ACCENT))
        cards_row.addWidget(StatCard(str(used_n),       f"Used  ({pct_used}%)",          COLOR_USED))
        cards_row.addWidget(StatCard(str(unused_n),     f"Unused  ({100-pct_used}%)",    "#c0392b"))
        cards_row.addWidget(StatCard(f"{reclaim_gb:.1f} GB", "Reclaimable disk space",  COLOR_WARN))
        cards_row.addWidget(StatCard(f"{total_gb:.1f} GB",   "Total plugin storage",    COLOR_TEXT_DIM))
        layout.addLayout(cards_row)

        # ── Insights ───────────────────────────────────────────────────
        insights_label = QLabel("Key Insights")
        insights_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;")
        layout.addWidget(insights_label)

        # Derive insight values from already-computed aggregations
        top_vendor, top_gb = max(vendor_reclaim.items(), key=lambda x: x[1]) if vendor_reclaim else ("—", 0)
        workhorse = max(top_used_list, key=lambda r: len(r.session_refs)) if top_used_list else None

        dual_unused = sum(
            1 for recs in by_family.values()
            if {r.format for r in recs} >= {PluginFormat.AU, PluginFormat.VST3}
            and all(r.status == UsageStatus.UNUSED for r in recs)
        )
        dual_gb = sum(
            sum(r.size_bytes for r in recs) / 1024**3
            for recs in by_family.values()
            if {r.format for r in recs} >= {PluginFormat.AU, PluginFormat.VST3}
            and all(r.status == UsageStatus.UNUSED for r in recs)
        )

        insight_widgets = [
            InsightRow("●", f"All {vst2_n} VST2 plugins are unused — safe to remove, you've fully moved to AU/VST3.",
                       COLOR_WARN),
            InsightRow("●", f"{top_vendor} is your biggest waste: {top_gb:.1f} GB of unused plugins.",
                       "#c0392b"),
            InsightRow("●", f"{dual_unused} plugin families are installed in both AU and VST3 but never used — "
                            f"that's {dual_gb:.1f} GB of duplicate installers.",
                       "#e91e63"),
        ]
        if workhorse:
            insight_widgets.append(InsightRow(
                "●",
                f"Your most-used plugin is {workhorse.display_name} ({workhorse.vendor}) — "
                f"in {len(workhorse.session_refs)} sessions.",
                COLOR_USED,
            ))

        pct_unused = int(100 * reclaim_gb / total_gb) if total_gb else 0
        insight_widgets.append(InsightRow(
            "●",
            f"{pct_unused}% of your plugin storage ({reclaim_gb:.1f} GB) is reclaimable. "
            f"Your active toolkit is only {total_gb - reclaim_gb:.1f} GB.",
            COLOR_ACCENT,
        ))

        for w in insight_widgets:
            layout.addWidget(w)

        # ── Charts grid ────────────────────────────────────────────────
        charts_label = QLabel("Charts")
        charts_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;")
        layout.addWidget(charts_label)

        # Row 1: donut + format bar side by side
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row1.addWidget(_build_format_donut(records), 1)
        row1.addWidget(_build_format_used_bar(records), 1)
        layout.addLayout(row1)

        # Row 2: workhorse full width
        layout.addWidget(_build_workhorse_bar(records))

        # Row 3: vendor unused + reclaimable side by side
        row3 = QHBoxLayout()
        row3.setSpacing(12)
        row3.addWidget(_build_vendor_unused_bar(records), 1)
        row3.addWidget(_build_reclaimable_bar(records), 1)
        layout.addLayout(row3)

        scroll.setWidget(container)
        self._outer.addWidget(scroll)
