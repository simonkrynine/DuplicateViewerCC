import sys
from PySide6.QtWidgets import QApplication
from core.crash_logger import setup_crash_logger
from ui.main_window import MainWindow


def main():
    setup_crash_logger()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
