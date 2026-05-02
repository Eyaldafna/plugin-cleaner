from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

COLOR_BG        = "#1e1e1e"
COLOR_BG_ALT    = "#252525"
COLOR_BG_PANEL  = "#2a2a2a"
COLOR_BORDER    = "#3a3a3a"
COLOR_TEXT      = "#d4d4d4"
COLOR_TEXT_DIM  = "#888888"
COLOR_ACCENT    = "#4a9eff"
COLOR_USED      = "#4caf50"
COLOR_UNUSED    = "#888888"
COLOR_WARN      = "#ff9800"
COLOR_SELECTED  = "#264f78"


QSS = f"""
QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: ".AppleSystemUIFont", "Helvetica Neue", Arial;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {COLOR_BG};
}}

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background: {COLOR_BG};
}}

QTabBar::tab {{
    background: {COLOR_BG_ALT};
    color: {COLOR_TEXT_DIM};
    padding: 6px 18px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-radius: 4px 4px 0 0;
}}

QTabBar::tab:selected {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
}}

QTabBar::tab:hover:!selected {{
    color: {COLOR_TEXT};
}}

QTableView {{
    background-color: {COLOR_BG};
    alternate-background-color: {COLOR_BG_ALT};
    gridline-color: {COLOR_BORDER};
    selection-background-color: {COLOR_SELECTED};
    selection-color: {COLOR_TEXT};
    border: none;
    outline: none;
}}

QTableView::item {{
    padding: 2px 6px;
    border: none;
}}

QHeaderView::section {{
    background-color: {COLOR_BG_ALT};
    color: {COLOR_TEXT_DIM};
    padding: 4px 8px;
    border: none;
    border-right: 1px solid {COLOR_BORDER};
    border-bottom: 1px solid {COLOR_BORDER};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:hover {{
    color: {COLOR_TEXT};
}}

QHeaderView::section:pressed {{
    background-color: {COLOR_BORDER};
}}

QLineEdit {{
    background-color: {COLOR_BG_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    color: {COLOR_TEXT};
}}

QLineEdit:focus {{
    border-color: {COLOR_ACCENT};
}}

QPushButton {{
    background-color: {COLOR_BG_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 5px 14px;
    color: {COLOR_TEXT};
    min-width: 80px;
}}

QPushButton:hover {{
    background-color: {COLOR_BORDER};
    border-color: {COLOR_ACCENT};
}}

QPushButton:pressed {{
    background-color: {COLOR_SELECTED};
}}

QPushButton:disabled {{
    color: {COLOR_TEXT_DIM};
    border-color: {COLOR_BORDER};
}}

QPushButton#primary {{
    background-color: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
    color: white;
    font-weight: 600;
}}

QPushButton#primary:hover {{
    background-color: #5aaeff;
}}

QPushButton#danger {{
    background-color: #c0392b;
    border-color: #c0392b;
    color: white;
}}

QPushButton#danger:hover {{
    background-color: #e74c3c;
}}

QCheckBox {{
    color: {COLOR_TEXT};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    background: {COLOR_BG_ALT};
}}

QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}

QRadioButton {{
    color: {COLOR_TEXT};
    spacing: 6px;
}}

QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    background: {COLOR_BG_ALT};
}}

QRadioButton::indicator:checked {{
    background: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}

QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_TEXT_DIM};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {COLOR_BG};
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER};
    border-radius: 4px;
}}

QStatusBar {{
    background: {COLOR_BG_ALT};
    border-top: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_DIM};
    font-size: 12px;
}}

QProgressBar {{
    background: {COLOR_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {COLOR_ACCENT};
    border-radius: 3px;
}}

QLabel#sectionHeader {{
    color: {COLOR_TEXT_DIM};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QFrame#separator {{
    background: {COLOR_BORDER};
    max-height: 1px;
}}

QListWidget {{
    background: {COLOR_BG_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    color: {COLOR_TEXT_DIM};
    font-size: 11px;
}}

QListWidget::item {{
    padding: 3px 6px;
}}

QListWidget::item:selected {{
    background: {COLOR_SELECTED};
    color: {COLOR_TEXT};
}}

QToolBar {{
    background: {COLOR_BG_ALT};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 6px 10px;
    spacing: 8px;
}}

QSplitter::handle {{
    background: {COLOR_BORDER};
    width: 1px;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(QSS)

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Base,            QColor(COLOR_BG_ALT))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(COLOR_BG_PANEL))
    pal.setColor(QPalette.ColorRole.Text,            QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Button,          QColor(COLOR_BG_ALT))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(COLOR_SELECTED))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Link,            QColor(COLOR_ACCENT))
    app.setPalette(pal)
