#!/usr/bin/env python3
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.theme import apply_theme
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Plugin Cleaner")
    app.setOrganizationName("EyalDafna")
    apply_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
