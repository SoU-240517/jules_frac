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

from functools import partial

class ParameterPanel(QScrollArea):
    # Signal emitted when parameters are changed by the user in this panel
    # Arguments: center_real, center_imag, width, max_iterations
    parameters_changed_in_ui_signal = pyqtSignal(float, float, float, int) # Common params

    # def __init__(self, fractal_controller: FractalController, parent=None):
    def __init__(self, fractal_controller, parent=None):
        super().__init__(parent)
        self.fractal_controller = fractal_controller
        self.plugin_widgets = {} # Holds dynamically created plugin-specific UI widgets

        self._init_ui() # This creates self.fractal_combo and plugin_specific_group/layout

        self._populate_fractal_combo() # Populate AFTER _init_ui

        if self.fractal_controller:
            self.load_initial_parameters() # Load common params for the initially active plugin
            # Connect signals for UI updates
            self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
            self.fractal_controller.active_plugin_ui_needs_update.connect(self._update_plugin_specific_ui)
            # Initial call to setup plugin UI for the default active plugin
            active_plugin_name = self.fractal_controller.get_active_plugin_name_from_engine()
            if active_plugin_name:
                self._update_plugin_specific_ui(active_plugin_name)
        else:
            print("ParameterPanel: FractalController not provided. UI will use defaults and features will be limited.")
            self._set_ui_values(-0.5, 0.0, 3.0, 100) # Default common params
            self.plugin_specific_group.setVisible(False)


    def _init_ui(self):
        self.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        self.main_layout = QVBoxLayout(self.content_widget) # Store as self.main_layout
        self.content_widget.setLayout(self.main_layout)

        # Fractal Selection Group
        fractal_group = QGroupBox("フラクタル選択")
        fractal_layout = QVBoxLayout()
        self.fractal_combo = QComboBox()
        fractal_layout.addWidget(self.fractal_combo)
        fractal_group.setLayout(fractal_layout)
        self.main_layout.addWidget(fractal_group)

        self.fractal_combo.currentTextChanged.connect(self._on_fractal_type_changed)

        # Common Parameters Group (Formerly Mandelbrot Settings)
        common_params_group = QGroupBox("共通描画設定")
        self.common_params_layout = QFormLayout() # Store as self.common_params_layout

        self.iter_spinbox = QSpinBox()
        self.iter_spinbox.setRange(10, 100000)
        self.iter_slider = QSlider(Qt.Orientation.Horizontal)
        self.iter_slider.setRange(10, 10000)
        self.common_params_layout.addRow(QLabel("最大反復回数:"), self.iter_spinbox)
        self.common_params_layout.addRow(self.iter_slider)

        self.center_real_spinbox = QDoubleSpinBox(); self.center_real_spinbox.setRange(-2.5, 2.5); self.center_real_spinbox.setDecimals(8); self.center_real_spinbox.setSingleStep(0.01)
        self.common_params_layout.addRow(QLabel("中心 (実部):"), self.center_real_spinbox)

        self.center_imag_spinbox = QDoubleSpinBox(); self.center_imag_spinbox.setRange(-2.0, 2.0); self.center_imag_spinbox.setDecimals(8); self.center_imag_spinbox.setSingleStep(0.01)
        self.common_params_layout.addRow(QLabel("中心 (虚部):"), self.center_imag_spinbox)

        self.width_spinbox = QDoubleSpinBox(); self.width_spinbox.setRange(1e-15, 10.0); self.width_spinbox.setDecimals(15); self.width_spinbox.setSingleStep(0.1)
        self.common_params_layout.addRow(QLabel("幅:"), self.width_spinbox)

        common_params_group.setLayout(self.common_params_layout)
        self.main_layout.addWidget(common_params_group)

        # Plugin-Specific Parameters Group
        self.plugin_specific_group = QGroupBox("プラグイン固有設定")
        self.plugin_specific_layout = QFormLayout()
        self.plugin_specific_group.setLayout(self.plugin_specific_layout)
        self.main_layout.addWidget(self.plugin_specific_group)
        self.plugin_specific_group.setVisible(False) # Initially hidden or based on current plugin

        # Coloring Settings Group (Placeholder)
        coloring_group = QGroupBox("カラーリング設定")
        coloring_layout = QVBoxLayout() # Using QVBoxLayout for simple label
        coloring_layout.addWidget(QLabel("（今後実装予定）"))
        coloring_group.setLayout(coloring_layout)
        self.main_layout.addWidget(coloring_group)

        # Render Button
        self.render_button = QPushButton("描画実行")
        self.main_layout.addWidget(self.render_button)

        self.main_layout.addStretch(1)

        # Connect signals for UI changes
        self.iter_spinbox.valueChanged.connect(self._on_iter_spinbox_changed)
        self.iter_slider.valueChanged.connect(self._on_iter_slider_changed)
        # For DoubleSpinBoxes, valueChanged can be very frequent during typing.
        # editingFinished is usually better for text-based input if updates are costly.
        # However, for spin boxes with up/down arrows, valueChanged is fine.
        self.center_real_spinbox.valueChanged.connect(self._on_value_changed_by_ui)
        self.center_imag_spinbox.valueChanged.connect(self._on_value_changed_by_ui)
        self.width_spinbox.valueChanged.connect(self._on_value_changed_by_ui)

    def _clear_plugin_specific_ui(self):
        """Clears all widgets from the plugin-specific UI layout."""
        self.plugin_widgets.clear()
        while self.plugin_specific_layout.count():
            item = self.plugin_specific_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            # Also remove row if QFormLayout still holds it (might need to remove rows explicitly)
            # For QFormLayout, removing widgets is usually enough if rows are auto-adjusted.
            # Or, remove row by row: self.plugin_specific_layout.removeRow(0)
        # print("ParameterPanel: Cleared plugin-specific UI.")


    @pyqtSlot(str)
    def _update_plugin_specific_ui(self, plugin_name: str):
        """Dynamically creates UI elements for the given plugin's specific parameters."""
        self._clear_plugin_specific_ui()
        if not self.fractal_controller or not plugin_name:
            self.plugin_specific_group.setVisible(False)
            return

        param_defs = self.fractal_controller.get_plugin_parameter_definitions(plugin_name)
        if not param_defs:
            self.plugin_specific_group.setVisible(False)
            # print(f"ParameterPanel: Plugin '{plugin_name}' has no specific parameters.")
            return

        self.plugin_specific_group.setVisible(True)
        self.plugin_specific_group.setTitle(f"{plugin_name} 固有設定")
        current_plugin_param_values = self.fractal_controller.get_current_plugin_parameters()

        # プラグインプリセット用UI (もしあれば)
        presets = self.fractal_controller.get_plugin_presets(plugin_name)
        if presets:
            preset_combo = QComboBox()
            preset_combo.addItem("カスタム") # Default, indicates manual parameter setting
            for preset_name in presets.keys():
                preset_combo.addItem(preset_name)

            # Connect signal for preset selection
            # Note: We pass a copy of presets dict at the time of connection using partial.
            # This avoids issues if presets_data were to change later for some reason.
            preset_combo.currentTextChanged.connect(
                partial(self._on_preset_selected, plugin_name=plugin_name, presets_data=presets.copy())
            )
            self.plugin_specific_layout.addRow(QLabel("プリセット:"), preset_combo)
            self.plugin_widgets['_preset_combo'] = preset_combo # Store for potential future access

        for p_def in param_defs:
            label_text = p_def.get('label', p_def['name'])
            param_name = p_def['name']
            param_type = p_def.get('type', 'float')
            default_val = current_plugin_param_values.get(param_name, p_def.get('default')) # Use current value from engine
            widget = None

            if param_type == 'float':
                widget = QDoubleSpinBox()
                widget.setRange(p_def.get('range', (-1e9, 1e9))[0], p_def.get('range', (-1e9, 1e9))[1])
                widget.setValue(default_val if default_val is not None else 0.0)
                widget.setSingleStep(p_def.get('step', 0.01))
                widget.setDecimals(p_def.get('decimals', 6)) # Default to 6 decimals for floats
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
            elif param_type == 'int':
                widget = QSpinBox()
                widget.setRange(p_def.get('range', (-2147483647, 2147483647))[0], p_def.get('range', (-2147483647, 2147483647))[1])
                widget.setValue(default_val if default_val is not None else 0)
                widget.setSingleStep(p_def.get('step', 1))
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])

            if widget:
                self.plugin_specific_layout.addRow(QLabel(label_text + ":"), widget)
                # Connect using partial to pass param_name to the slot
                widget.valueChanged.connect(partial(self._on_plugin_parameter_changed, param_name=param_name))
                self.plugin_widgets[param_name] = widget
        # print(f"ParameterPanel: Updated plugin-specific UI for '{plugin_name}'.")


    def _populate_fractal_combo(self):
        """Populates the fractal selection combobox."""
        if not self.fractal_controller:
            print("ParameterPanel: Cannot populate fractal combo, no controller.")
            return

        plugin_names = self.fractal_controller.get_available_plugin_names_from_engine()
        current_active_plugin_name = self.fractal_controller.get_active_plugin_name_from_engine()

        self.fractal_combo.blockSignals(True)
        self.fractal_combo.clear()
        if plugin_names:
            self.fractal_combo.addItems(plugin_names)
            if current_active_plugin_name and current_active_plugin_name in plugin_names:
                self.fractal_combo.setCurrentText(current_active_plugin_name)
            elif plugin_names: # Default to first if current not found or not set
                self.fractal_combo.setCurrentText(plugin_names[0])
        else:
            self.fractal_combo.addItem("プラグインなし") # Placeholder if no plugins
            self.fractal_combo.setEnabled(False)

        self.fractal_combo.blockSignals(False)
        print(f"ParameterPanel: Fractal combo populated. Items: {plugin_names}. Current: {self.fractal_combo.currentText()}")

    @pyqtSlot(str)
    def _on_fractal_type_changed(self, plugin_name: str):
        """Handles selection change in the fractal type combobox."""
        if not self.fractal_controller or not plugin_name or plugin_name == "プラグインなし":
            return

        # Prevent re-triggering if the change was programmatic (e.g. from parameters_updated_externally)
        # Check if this plugin is already active in the engine
        current_engine_plugin = self.fractal_controller.get_active_plugin_name_from_engine()
        if plugin_name == current_engine_plugin:
            print(f"ParameterPanel: Fractal type '{plugin_name}' is already active. No change needed.")
            return

        print(f"ParameterPanel: User selected fractal type '{plugin_name}'. Notifying controller.")
        self.fractal_controller.set_active_fractal_plugin_and_redraw(plugin_name)
        # After this, controller will emit parameters_updated_externally,
        # which will call update_ui_from_controller_parameters to refresh common params.
        # Plugin-specific UI update would also be needed here.
        # self.update_plugin_specific_ui_for_plugin(plugin_name) # TODO

    def _on_iter_spinbox_changed(self, value):
        self.iter_slider.setValue(value) # Sync slider
        self._on_value_changed_by_ui() # Emit signal

    def _on_iter_slider_changed(self, value):
        if self.iter_spinbox.value() != value: # Avoid loop if already same
            self.iter_spinbox.setValue(value) # Sync spinbox (this will call _on_value_changed_by_ui via spinbox's signal)
        else: # If slider was source and value is already same, ensure signal emits if direct call needed
             self._on_value_changed_by_ui()


    def _on_value_changed_by_ui(self):
        """Gathers current common parameters from UI and emits parameters_changed_in_ui_signal."""
        cr = self.center_real_spinbox.value()
        ci = self.center_imag_spinbox.value()
        w = self.width_spinbox.value()
        iters = self.iter_spinbox.value()
        self.parameters_changed_in_ui_signal.emit(cr, ci, w, iters)

    def _on_plugin_parameter_changed(self, value, param_name: str): # Value arg might be unused if sender is source of truth
        """Handles changes in plugin-specific parameter UI elements."""
        if not self.fractal_controller: return

        sender_widget = self.sender()
        if isinstance(sender_widget, (QDoubleSpinBox, QSpinBox)): # Extend with QCheckBox etc. if needed
            actual_value = sender_widget.value()
            print(f"ParameterPanel: Plugin param '{param_name}' changed to '{actual_value}' by UI.")
            self.fractal_controller.set_plugin_parameter_value(param_name, actual_value)
            # If a preset was selected, and then a specific param is changed, deselect preset
            if '_preset_combo' in self.plugin_widgets:
                self.plugin_widgets['_preset_combo'].blockSignals(True)
                self.plugin_widgets['_preset_combo'].setCurrentText("カスタム")
                self.plugin_widgets['_preset_combo'].blockSignals(False)


    def _on_preset_selected(self, preset_name: str, plugin_name: str, presets_data: dict):
        """Handles selection of a preset value for plugin parameters."""
        if preset_name == "カスタム" or not self.fractal_controller:
            # "カスタム" means user will set params manually, or they already are custom.
            return

        selected_preset_values = presets_data.get(preset_name)
        if selected_preset_values:
            print(f"ParameterPanel: Preset '{preset_name}' for plugin '{plugin_name}' selected. Values: {selected_preset_values}")

            # Update UI elements and notify controller for each parameter in the preset
            for param_name, value in selected_preset_values.items():
                if param_name in self.plugin_widgets:
                    widget = self.plugin_widgets[param_name]
                    widget.blockSignals(True) # Prevent _on_plugin_parameter_changed from firing and setting preset to "カスタム"
                    if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                        widget.setValue(value)
                    # Add other widget types here if necessary (e.g., QCheckBox.setChecked(value))
                    widget.blockSignals(False)
                    # Manually notify controller for this parameter change from preset
                    self.fractal_controller.set_plugin_parameter_value(param_name, value)
                else:
                    # If param_name in preset is not found in UI (should not happen if UI is built from param_defs)
                    # still try to set it in the engine directly.
                    print(f"ParameterPanel: Preset param '{param_name}' has no UI widget, setting directly in engine.")
                    self.fractal_controller.set_plugin_parameter_value(param_name, value)

            # After applying all preset values, could optionally trigger a re-render or notify user.
            # For now, parameter changes update the engine. User clicks "Render" button.
            # If immediate re-render is desired: self.fractal_controller.trigger_render() (after ensuring main_window size is known)
            print(f"ParameterPanel: All parameters for preset '{preset_name}' applied.")


    def load_initial_parameters(self):
        """Loads common parameters from the controller for the current active plugin and updates the UI."""
        if self.fractal_controller:
            # Parameters should reflect the currently active plugin in the engine
            params = self.fractal_controller.get_current_parameters()
            if params:
                 print(f"ParameterPanel: Loading initial common parameters from controller: CR={params.get('center_real')}, W={params.get('width')}, Iters={params.get('max_iterations')}")
                 self._set_ui_values(params.get('center_real', -0.5),
                                    params.get('center_imag', 0.0),
                                    params.get('width', 3.0),
                                    params.get('max_iterations', 100))
                 # TODO: Load plugin-specific parameters if any for the current plugin
                 # self.load_plugin_specific_parameters()
            else:
                print("ParameterPanel: Controller returned no initial parameters, using UI defaults.")
                self._set_ui_values(-0.5, 0.0, 3.0, 100) # Fallback defaults for common params

    @pyqtSlot()
    def update_ui_from_controller_parameters(self):
        """Updates common parameter UI elements based on current parameters from the FractalController."""
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
