import sys

from PySide6.QtWidgets import QApplication
from desktop_app.main_window import MainWindow
from desktop_app.theme import APP_STYLE
#from core.serial_service import SerialService


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()