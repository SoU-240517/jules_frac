from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QStatusBar, QSplitter, QLabel, QWidget, QApplication, QVBoxLayout
)
from PyQt6.QtGui import QAction
from .render_area import RenderArea
from .parameter_panel import ParameterPanel
from PyQt6.QtCore import Qt
# from src.app.controllers.fractal_controller import FractalController # For type hinting


class MainWindow(QMainWindow):
    # def __init__(self, fractal_controller: FractalController): # fractal_controller を引数に追加
    def __init__(self, fractal_controller): # fractal_controller を引数に追加
        super().__init__()
        self.fractal_controller = fractal_controller

        self.setWindowTitle("高機能フラクタル描画アプリケーション")
        self.resize(1400, 800)

        self._create_menu_bar()
        # self._create_status_bar() # QMainWindow creates one by default, just get it
        self.status_bar = self.statusBar() # Get the default status bar
        self.status_bar.showMessage("準備完了") # Set initial message
        self._setup_central_widget()

    def _create_menu_bar(self):
        # menu_bar = QMenuBar(self) # No need to create, setMenuBar handles it if parent is QMainWindow
        menu_bar = self.menuBar() # Get the existing menu bar or create one
        self.setMenuBar(menu_bar)

        file_menu = menu_bar.addMenu("ファイル")
        # Add actions to file_menu later
        # e.g., file_menu.addAction("開く...")

        help_menu = menu_bar.addMenu("ヘルプ")
        # Add actions to help_menu later
        # e.g., help_menu.addAction("バージョン情報")

    # def _create_status_bar(self): # Not needed as QMainWindow provides one
    #     status_bar = QStatusBar(self)
    #     self.setStatusBar(status_bar)
    #     status_bar.showMessage("準備完了")

    def update_status_bar(self, message: str):
        """Slot to update the status bar message."""
        if self.status_bar:
            self.status_bar.showMessage(message)

    def _setup_central_widget(self):
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left side: Render Area
        self.render_area = RenderArea(self) # Store as instance variable to access its size
        splitter.addWidget(self.render_area)

        # Right side: Parameter Panel
        parameter_panel = ParameterPanel(self) # Use ParameterPanel instance
        splitter.addWidget(parameter_panel)

        self.setCentralWidget(splitter)

        # Set initial sizes (70% for render area, 30% for parameter panel)
        # Calculate based on current window width if possible, or use fixed sizes
        # For simplicity, let's use the initial window width to calculate.
        initial_width = self.width()
        splitter.setSizes([int(initial_width * 0.7), int(initial_width * 0.3)])

    # Optional: Method to request initial render, could be connected to a signal e.g. window shown
    # def request_initial_render(self):
    #    if self.fractal_controller and hasattr(self, 'render_area'):
    #        # Ensure render_area has a valid size before requesting render
    #        if self.render_area.width() > 0 and self.render_area.height() > 0:
    #            self.fractal_controller.trigger_render(
    #                self.render_area.width(),
    #                self.render_area.height()
    #            )
    #        else:
    #            # Handle case where render_area size is not yet determined
    #            # For example, defer render or use a default size
    #            print("RenderArea size not available for initial render yet.")
    #            # self.fractal_controller.trigger_render() # Trigger with default size in controller


if __name__ == '__main__':
    # This part is for testing the MainWindow independently.
    # It will be removed or modified when integrated into the main application flow.
    import sys
    # Mock FractalController for standalone testing
    class MockFractalController(QObject):
        status_updated = pyqtSignal(str)
        def __init__(self, engine=None): super().__init__()
        def set_main_window(self, win): pass
        def trigger_render(self, w, h): print(f"MockController: render triggered {w}x{h}")
        def update_status_display(self): self.status_updated.emit("Mock status")

    app = QApplication(sys.argv)
    mock_controller = MockFractalController()
    main_win = MainWindow(fractal_controller=mock_controller)
    mock_controller.status_updated.connect(main_win.update_status_bar)
    main_win.show()
    # main_win.request_initial_render() # Test initial render request
    sys.exit(app.exec())
