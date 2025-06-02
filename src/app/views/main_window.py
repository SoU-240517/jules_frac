from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QStatusBar, QSplitter, QLabel, QWidget, QApplication, QVBoxLayout
)
from PyQt6.QtGui import QAction
from .render_area import RenderArea
from .parameter_panel import ParameterPanel
from PyQt6.QtCore import Qt, pyqtSlot, QTimer # Added pyqtSlot and QTimer
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
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("準備完了")

        # _setup_central_widget must be called AFTER fractal_controller is set,
        # because ParameterPanel needs it.
        self._setup_central_widget()

        # Connect signals
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("準備完了")

        self._setup_central_widget()

        # Signal connections
        if self.fractal_controller:
            if hasattr(self.render_area, 'update_image'):
                self.fractal_controller.image_rendered.connect(self.render_area.update_image)
            if hasattr(self.parameter_panel, 'parameters_changed_in_ui_signal'):
                self.parameter_panel.parameters_changed_in_ui_signal.connect(self.on_ui_parameters_changed)
            if hasattr(self.parameter_panel, 'render_button'):
                self.parameter_panel.render_button.clicked.connect(self.trigger_render_from_panel)
            # Connect controller's external param update to panel's UI update slot
            if hasattr(self.fractal_controller, 'parameters_updated_externally') and \
               hasattr(self.parameter_panel, 'update_ui_from_controller_parameters'):
                self.fractal_controller.parameters_updated_externally.connect(
                    self.parameter_panel.update_ui_from_controller_parameters
                )
        else:
            print("MainWindow: FractalController not available for signal connections.")

        self._initial_render_done = False
        self._initial_render_attempts = 0


    def _create_menu_bar(self):
        menu_bar = self.menuBar()
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

        # Left side: Render Area - Pass fractal_controller to its constructor
        self.render_area = RenderArea(self, fractal_controller=self.fractal_controller)
        splitter.addWidget(self.render_area)

        # Right side: Parameter Panel
        self.parameter_panel = ParameterPanel(self.fractal_controller, self)
        splitter.addWidget(self.parameter_panel)

        self.setCentralWidget(splitter)

        # Set initial sizes (70% for render area, 30% for parameter panel)
        # Calculate based on current window width if possible, or use fixed sizes
        # For simplicity, let's use the initial window width to calculate.
        initial_width = self.width()
        splitter.setSizes([int(initial_width * 0.7), int(initial_width * 0.3)])

    # Optional: Method to request initial render, could be connected to a signal e.g. window shown
    def on_ui_parameters_changed(self, center_real, center_imag, width, max_iterations):
        """Slot to handle parameter changes from the ParameterPanel's UI."""
        if self.fractal_controller:
            print(f"MainWindow: UI parameters changed to CR={center_real}, CI={center_imag}, W={width}, Iters={max_iterations}. Updating controller.")
            # Source "ui_direct_no_render" indicates the parameters are from direct UI manipulation
            # and should not by themselves trigger a re-render or a full UI sync from controller.
            self.fractal_controller.update_fractal_parameters(center_real, center_imag, width, max_iterations) # Removed source argument for now
        else:
            print("MainWindow: FractalController not available to update parameters.")

    @pyqtSlot()
    def trigger_render_from_panel(self):
        """Triggers rendering using current parameters from ParameterPanel and RenderArea size."""
        if not self.fractal_controller:
            print("MainWindow Error: FractalController is not available.")
            return

        print("MainWindow: '描画'ボタンがクリックされました.")
        if not hasattr(self, 'parameter_panel') or self.parameter_panel is None:
            print("MainWindow Error: parameter_panel is not initialized.")
            return

        params = self.parameter_panel.get_current_ui_parameters()
        # Update engine parameters based on current UI state before triggering render
        self.fractal_controller.update_fractal_parameters(
            params['center_real'],
            params['center_imag'],
            params['width'],
            params['max_iterations']
            # source="ui_button" # If source argument is used in controller
        )

        if not hasattr(self, 'render_area') or self.render_area is None:
            print("MainWindow Error: render_area is not initialized.")
            return

        render_width = self.render_area.width()
        render_height = self.render_area.height()

        if render_width <= 0 or render_height <= 0:
            print("MainWindow: RenderAreaのサイズが不正です. デフォルトサイズで描画を試みます.")
            # Trigger render with controller's current (possibly default) image size settings
            self.fractal_controller.trigger_render()
        else:
            self.fractal_controller.trigger_render(render_width, render_height)
        print(f"MainWindow: 描画をトリガーしました (要求解像度: {render_width}x{render_height}).")

    def showEvent(self, event):
        """Called when the window is shown."""
        super().showEvent(event)
        # Perform initial render only once, after a short delay to allow UI to stabilize.
        if not self._initial_render_done:
            # Using QTimer.singleShot to delay the initial render slightly,
            # ensuring the window and its widgets have been sized and are visible.
            QTimer.singleShot(100, self._perform_initial_render)

    def _perform_initial_render(self):
        """Attempts to perform the initial render if conditions are met."""
        if self._initial_render_done:
            return

        if not self.fractal_controller:
            print("MainWindow Error: FractalController not available for initial render.")
            return

        self._initial_render_attempts += 1
        print(f"MainWindow: 初回描画を試みます (試行: {self._initial_render_attempts}).")

        # Check if critical components are initialized and RenderArea has a valid size
        if not hasattr(self, 'render_area') or self.render_area is None or \
           self.render_area.width() <= 0 or self.render_area.height() <= 0 or \
           not hasattr(self, 'parameter_panel') or self.parameter_panel is None:

            if self._initial_render_attempts <= 5: # Retry a few times
                print(f"MainWindow: RenderAreaまたはParameterPanelが未初期化かサイズ不正のため初回描画を遅延します.")
                QTimer.singleShot(200 * self._initial_render_attempts, self._perform_initial_render)
            else:
                print("MainWindow Error: RenderAreaまたはParameterPanelの初期化/サイズ確定に失敗しました. 初回描画を中止します.")
            return

        # Load initial parameters from the panel (which should have loaded from controller or defaults)
        initial_params = self.parameter_panel.get_current_ui_parameters()
        self.fractal_controller.update_fractal_parameters(
            initial_params['center_real'],
            initial_params['center_imag'],
            initial_params['width'],
            initial_params['max_iterations']
            # source="initial_load" # If source argument is used
        )

        render_width = self.render_area.width()
        render_height = self.render_area.height()

        print(f"MainWindow: RenderAreaサイズ ({render_width}x{render_height}) で初回描画を実行します.")
        self.fractal_controller.trigger_render(render_width, render_height)
        self._initial_render_done = True
        print("MainWindow: 初回描画が完了しました.")


if __name__ == '__main__':
    import sys
    from PyQt6.QtCore import QTimer # For timed emission in test
    import numpy # For creating dummy data in test

    class MockFractalController(QObject):
        status_updated = pyqtSignal(str)
        image_rendered = pyqtSignal(object)
        parameters_updated_externally = pyqtSignal() # Keep this for consistency if ParameterPanel uses it

        def __init__(self, engine=None):
            super().__init__()
            self.dummy_image_counter = 0
            self._params_cache = {"center_real":-0.5, "center_imag":0.0, "width":3.0, "max_iterations":100, "height":2.0}


        def set_main_window(self, win): pass

        def trigger_render(self, w=None, h=None):
            print(f"MockController: render triggered for approx {w}x{h}")
            self.dummy_image_counter += 1
            width, height = 100 + self.dummy_image_counter*20, 80 + self.dummy_image_counter*15
            dummy_data = np.zeros((height, width, 4), dtype=np.uint8) # RGBA
            dummy_data[:, :, 0] = (self.dummy_image_counter * 60) % 255
            dummy_data[:, :, 1] = (128 + self.dummy_image_counter * 10) % 255
            dummy_data[:, :, 2] = (50 + self.dummy_image_counter * 5) % 255
            dummy_data[:, :, 3] = 255
            self.image_rendered.emit(dummy_data)
            self.status_updated.emit(f"Mock: Rendered dummy image {self.dummy_image_counter} ({width}x{height})")

        def update_status_display(self):
            self.status_updated.emit("Mock status: Parameters updated")

        def get_current_parameters(self):
            return self._params_cache

        def get_current_engine_parameters(self): # For RenderArea pan calculation
             return self.get_current_parameters()

        def update_fractal_parameters(self, cr, ci, w, iters): # Removed source for simplicity in mock
            print(f"MockController: update_fractal_parameters: CR={cr}, CI={ci}, W={w}, Iters={iters}")
            self._params_cache = {"center_real":cr, "center_imag":ci, "width":w, "max_iterations":iters}
            # Ensure height is updated based on some aspect ratio if relevant for mock tests
            self._params_cache["height"] = w * ( (self._params_cache.get("image_height_px",3) / self._params_cache.get("image_width_px",4) ) if self._params_cache.get("image_width_px",4) > 0 else 0.75)
            self.status_updated.emit(f"Mock: Params updated to CR={cr:.2f}, W={w:.2f}, Iters={iters}")
            # self.parameters_updated_externally.emit() # Only if change was non-UI

        def pan_fractal(self, dr, di):
            print(f"MockController (MainWindow test): pan_fractal called with dr={dr:.4e}, di={di:.4e}")
            params = self.get_current_parameters()
            new_cr = params["center_real"] - dr
            new_ci = params["center_imag"] - di
            self.update_fractal_parameters(new_cr, new_ci, params["width"], params["max_iterations"])
            self.parameters_updated_externally.emit() # Panning is an external update to parameters
            self.trigger_render()


    app = QApplication(sys.argv)
    mock_controller = MockFractalController()
    main_win = MainWindow(fractal_controller=mock_controller)

    # Connect status update, already done if MainWindow connects it internally, but good for test clarity
    if hasattr(mock_controller, 'status_updated') and hasattr(main_win, 'update_status_bar'):
         mock_controller.status_updated.connect(main_win.update_status_bar)
    # The key connections are now inside MainWindow's __init__

    main_win.show()

    # Simulate a render trigger from the "button" after a short delay
    # In a real scenario, user would click ParameterPanel's render_button
    def simulate_render_button_click():
        if hasattr(main_win, 'trigger_render_from_panel'):
            print("\nTest Harness: Simulating render button click...")
            main_win.trigger_render_from_panel()

    QTimer.singleShot(1000, simulate_render_button_click)

    # Simulate a UI parameter change then render button click
    def simulate_ui_change_then_render():
        print("\nTest Harness: Simulating UI parameter change in panel...")
        if hasattr(main_win, 'parameter_panel'):
            # This will emit parameters_changed_in_ui_signal, which MainWindow connects to on_ui_parameters_changed
            main_win.parameter_panel.width_spinbox.setValue(1.5)

        # Then simulate render button click after a short delay for param update to process
        QTimer.singleShot(200, simulate_render_button_click)


    QTimer.singleShot(2500, simulate_ui_change_then_render)


    sys.exit(app.exec())
