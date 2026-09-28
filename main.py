"""Optima 0.5 application entrypoint, suitable for PyInstaller packaging."""
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Optima")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
#no changes    
