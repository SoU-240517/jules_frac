from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QSlider, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
# from src.app.controllers.fractal_controller import FractalController # For type hinting

class ParameterPanel(QScrollArea):
    # Signal emitted when parameters are changed by the user in this panel
    # Arguments: center_real, center_imag, width, max_iterations
    parameters_changed_in_ui_signal = pyqtSignal(float, float, float, int)

    # def __init__(self, fractal_controller: FractalController, parent=None):
    def __init__(self, fractal_controller, parent=None):
        super().__init__(parent)
        self.fractal_controller = fractal_controller
        self._init_ui()

        if self.fractal_controller:
            self.load_initial_parameters()
            # Connect to the controller's signal for external parameter updates
            self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
        else:
            print("ParameterPanel: FractalController not provided, UI will use default values and won't sync.")
            # Load default values into UI even if no controller
            self._set_ui_values(-0.5, 0.0, 3.0, 100)


    def _init_ui(self):
        self.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        main_layout = QVBoxLayout(self.content_widget)
        self.content_widget.setLayout(main_layout)

        # Fractal Selection Group (Placeholder)
        fractal_group = QGroupBox("フラクタル選択")
        fractal_layout = QVBoxLayout()
        self.fractal_combo = QComboBox()
        self.fractal_combo.addItem("Mandelbrot")
        # self.fractal_combo.setEnabled(False) # For now, only Mandelbrot
        fractal_layout.addWidget(self.fractal_combo)
        fractal_group.setLayout(fractal_layout)
        main_layout.addWidget(fractal_group)

        # Mandelbrot Settings Group
        mandel_group = QGroupBox("Mandelbrot 設定")
        form_layout = QFormLayout()

        # Max Iterations
        self.iter_spinbox = QSpinBox()
        self.iter_spinbox.setRange(10, 100000)
        self.iter_slider = QSlider(Qt.Orientation.Horizontal)
        self.iter_slider.setRange(10, 10000) # Slider might have a more practical upper limit for direct use
        form_layout.addRow(QLabel("最大反復回数:"), self.iter_spinbox)
        form_layout.addRow(self.iter_slider)

        # Center Real
        self.center_real_spinbox = QDoubleSpinBox()
        self.center_real_spinbox.setRange(-2.5, 2.5)
        self.center_real_spinbox.setDecimals(8) # Increased precision
        self.center_real_spinbox.setSingleStep(0.01)
        form_layout.addRow(QLabel("中心 (実部):"), self.center_real_spinbox)

        # Center Imaginary
        self.center_imag_spinbox = QDoubleSpinBox()
        self.center_imag_spinbox.setRange(-2.0, 2.0)
        self.center_imag_spinbox.setDecimals(8) # Increased precision
        self.center_imag_spinbox.setSingleStep(0.01)
        form_layout.addRow(QLabel("中心 (虚部):"), self.center_imag_spinbox)

        # Width
        self.width_spinbox = QDoubleSpinBox()
        self.width_spinbox.setRange(1e-15, 10.0) # Allow very small widths for deep zooms
        self.width_spinbox.setDecimals(15) # Increased precision for width
        self.width_spinbox.setSingleStep(0.1) # Step might need adjustment for very small values
                                             # Consider logarithmic step or context-based step
        form_layout.addRow(QLabel("幅:"), self.width_spinbox)

        mandel_group.setLayout(form_layout)
        main_layout.addWidget(mandel_group)

        # Coloring Settings Group (Placeholder)
        coloring_group = QGroupBox("カラーリング設定")
        coloring_layout = QVBoxLayout()
        coloring_layout.addWidget(QLabel("（今後実装予定）"))
        coloring_group.setLayout(coloring_layout)
        main_layout.addWidget(coloring_group)

        # Render Button
        self.render_button = QPushButton("描画実行")
        # self.render_button.clicked.connect(self._trigger_render_from_button) # Connect this in MainWindow
        main_layout.addWidget(self.render_button)

        main_layout.addStretch(1)

        # Connect signals for UI changes
        self.iter_spinbox.valueChanged.connect(self._on_iter_spinbox_changed)
        self.iter_slider.valueChanged.connect(self._on_iter_slider_changed)
        # For DoubleSpinBoxes, valueChanged can be very frequent during typing.
        # editingFinished is usually better for text-based input if updates are costly.
        # However, for spin boxes with up/down arrows, valueChanged is fine.
        self.center_real_spinbox.valueChanged.connect(self._on_value_changed_by_ui)
        self.center_imag_spinbox.valueChanged.connect(self._on_value_changed_by_ui)
        self.width_spinbox.valueChanged.connect(self._on_value_changed_by_ui)

    def _on_iter_spinbox_changed(self, value):
        self.iter_slider.setValue(value)
        self._on_value_changed_by_ui()

    def _on_iter_slider_changed(self, value):
        # To prevent feedback loop if slider change also triggers spinbox valueChanged,
        # check if value is different before setting.
        if self.iter_spinbox.value() != value:
            self.iter_spinbox.setValue(value)
            # self._on_value_changed_by_ui() will be called by iter_spinbox.valueChanged
        else: # If value is same, but slider was the source, still need to potentially emit.
             self._on_value_changed_by_ui()


    def _on_value_changed_by_ui(self):
        """Emits a signal when any parameter is changed by the user via UI controls."""
        cr = self.center_real_spinbox.value()
        ci = self.center_imag_spinbox.value()
        w = self.width_spinbox.value()
        iters = self.iter_spinbox.value()
        print(f"ParameterPanel: UI value changed. Emitting signal: CR={cr}, CI={ci}, W={w}, Iters={iters}")
        self.parameters_changed_in_ui_signal.emit(cr, ci, w, iters)

    def load_initial_parameters(self):
        """Loads parameters from the controller and updates the UI elements."""
        if self.fractal_controller:
            params = self.fractal_controller.get_current_parameters()
            if params: # Ensure params is not empty
                 print(f"ParameterPanel: Loading initial parameters from controller: {params}")
                 self._set_ui_values(params.get('center_real', -0.5),
                                    params.get('center_imag', 0.0),
                                    params.get('width', 3.0),
                                    params.get('max_iterations', 100))
            else:
                print("ParameterPanel: Controller returned no parameters, using defaults.")
                self._set_ui_values(-0.5, 0.0, 3.0, 100) # Fallback defaults

    @pyqtSlot() # Decorator to explicitly mark this as a PyQt slot
    def update_ui_from_controller_parameters(self):
        """Updates UI elements based on current parameters from the FractalController."""
        if self.fractal_controller:
            params = self.fractal_controller.get_current_parameters()
            if params:
                print(f"ParameterPanel: Syncing UI from controller parameters: {params}")
                self._set_ui_values(params['center_real'], params['center_imag'],
                                    params['width'], params['max_iterations'])
        else:
            print("ParameterPanel: Attempted to update UI from controller, but no controller is set.")

    def _set_ui_values(self, cr, ci, w, iters):
        """Helper method to set all UI parameter input widgets, blocking signals."""
        # Block signals to prevent feedback loops while programmatically setting values
        self.iter_spinbox.blockSignals(True)
        self.iter_slider.blockSignals(True)
        self.center_real_spinbox.blockSignals(True)
        self.center_imag_spinbox.blockSignals(True)
        self.width_spinbox.blockSignals(True)

        self.iter_spinbox.setValue(int(iters)) # Ensure iters is int for QSpinBox
        self.iter_slider.setValue(int(iters))
        self.center_real_spinbox.setValue(cr)
        self.center_imag_spinbox.setValue(ci)
        self.width_spinbox.setValue(w)

        # Unblock signals
        self.iter_spinbox.blockSignals(False)
        self.iter_slider.blockSignals(False)
        self.center_real_spinbox.blockSignals(False)
        self.center_imag_spinbox.blockSignals(False)
        self.width_spinbox.blockSignals(False)
        print(f"ParameterPanel: UI elements set to CR={cr}, CI={ci}, W={w}, Iters={iters}")

    def get_current_ui_parameters(self):
        """Returns a dictionary of the current parameters from the UI elements."""
        return {
            "center_real": self.center_real_spinbox.value(),
            "center_imag": self.center_imag_spinbox.value(),
            "width": self.width_spinbox.value(),
            "max_iterations": self.iter_spinbox.value()
        }

if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    # Minimal mock controller for testing ParameterPanel standalone
    class MockFractalController(QObject):
        parameters_updated_externally = pyqtSignal()
        status_updated = pyqtSignal(str) # ParameterPanel doesn't use this directly but good for completeness

        def __init__(self):
            super().__init__()
            self._params = {"center_real": -0.7, "center_imag": 0.1, "width": 0.5, "max_iterations": 150, "height":0.0}
            self._params["height"] = (self._params["width"] * 600)/800


        def get_current_parameters(self):
            print(f"MockController: get_current_parameters called, returning {self._params}")
            return self._params

        def update_fractal_parameters(self, cr, ci, w, iters): # Called by MainWindow
            self._params = {"center_real": cr, "center_imag": ci, "width": w, "max_iterations": iters}
            self._params["height"] = (self._params["width"] * 600)/800 # Assume some image aspect ratio
            print(f"MockController: Parameters updated to {self._params}")
            self.status_updated.emit(f"Mock: Params set to {cr}, {ci}, {w}, {iters}")
            # If these params were set by something other than this panel, emit:
            # self.parameters_updated_externally.emit()


        def trigger_render(self): # Called by MainWindow after getting params from panel
            print(f"MockController: Trigger render with current params: {self._params}")
            self.status_updated.emit(f"Mock: Rendering with {self._params['max_iterations']} iterations.")


    app = QApplication(sys.argv)
    main_win = QMainWindow() # To host the panel

    mock_controller = MockFractalController()
    param_panel = ParameterPanel(fractal_controller=mock_controller)

    # Test signal from ParameterPanel
    def handle_panel_param_change(cr, ci, w, iters):
        print(f"Test Harness: ParameterPanel's parameters_changed_in_ui_signal received.")
        # In real app, MainWindow would get this and call controller.update_fractal_parameters
        mock_controller.update_fractal_parameters(cr, ci, w, iters)

    param_panel.parameters_changed_in_ui_signal.connect(handle_panel_param_change)

    # Test updating panel from controller
    def simulate_external_param_change():
        print("\nTest Harness: Simulating external parameter change...")
        mock_controller._params["center_real"] = -1.0
        mock_controller._params["width"] = 2.5
        mock_controller._params["max_iterations"] = 250
        mock_controller.parameters_updated_externally.emit()
        print(f"Test Harness: Panel's UI should now reflect: {mock_controller._params}")
        # Check if UI updated (visual check, or add getters to panel for programmatic check)
        # ui_vals = param_panel.get_current_ui_parameters()
        # assert ui_vals["center_real"] == -1.0

    main_win.setCentralWidget(param_panel)
    main_win.resize(350, 600)
    main_win.setWindowTitle("ParameterPanel Test")
    main_win.show()

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(1000, simulate_external_param_change) # Simulate after UI is shown

    # Simulate UI interaction (requires event loop)
    # param_panel.width_spinbox.setValue(1.23) # This would trigger signals if done in test

    sys.exit(app.exec())
