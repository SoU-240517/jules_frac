import os
from functools import partial
from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSlider, QSpinBox, QLabel, QFormLayout, QVBoxLayout,
    QHBoxLayout, QGroupBox, QFileDialog, QDialogButtonBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize
from PyQt6.QtWidgets import QMessageBox # For error display on accept

from src.app.utils.settings_manager import SettingsManager # Import SettingsManager

class HighResOutputDialog(QDialog):
    SETTINGS_SECTION_NAME = "high_res_export_defaults" # Settings section key

    def __init__(self, settings_manager: SettingsManager,
                 current_dialog_defaults: dict | None = None, # Previously current_export_settings
                 current_view_params: dict | None = None,
                 parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("高解像度出力設定")
        self.setMinimumWidth(550)

        # current_dialog_defaults are the values to populate if no saved settings are found,
        # or to use as a base before applying saved settings.
        # These could be the app's general defaults or last *used* (not necessarily saved) settings.
        self.dialog_defaults = current_dialog_defaults if current_dialog_defaults else {}
        self.current_view_params = current_view_params if current_view_params else {}

        initial_width_px = self.current_view_params.get('image_width_px', 800)
        initial_height_px = self.current_view_params.get('image_height_px', 600)
        self.source_aspect_ratio = initial_width_px / initial_height_px if initial_height_px > 0 else 16.0/9.0
        self.keep_aspect_ratio_enabled = True
        self.updates_enabled = True # To manage recursive updates in dimension change

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._create_file_group())
        main_layout.addWidget(self._create_resolution_group())
        main_layout.addWidget(self._create_options_group())
        main_layout.addWidget(self._create_buttons())

        self._connect_signals()
        self._load_settings() # Load saved settings and apply them
        self._update_memory_usage_label()

    def _create_file_group(self) -> QGroupBox: # No change, just for context
        group = QGroupBox("ファイル設定")
        layout = QFormLayout()

        self.filepath_edit = QLineEdit()
        self.filepath_edit.setReadOnly(True)
        browse_button = QPushButton("参照...")
        browse_button.clicked.connect(self._browse_filepath) # Connect here for early access
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.filepath_edit)
        path_layout.addWidget(browse_button)
        layout.addRow(QLabel("保存場所:"), path_layout)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "TIFF", "BMP"])
        layout.addRow(QLabel("ファイル形式:"), self.format_combo)

        self.png_transparent_check = QCheckBox("背景を透過する (PNGのみ)")
        layout.addRow(self.png_transparent_check)

        jpeg_quality_layout = QHBoxLayout()
        self.jpeg_quality_label = QLabel("JPEG品質:")
        self.jpeg_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_quality_slider.setRange(1, 100)
        self.jpeg_quality_slider.setValue(90)
        self.jpeg_quality_value_label = QLabel(f"{self.jpeg_quality_slider.value()}%")
        self.jpeg_quality_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        jpeg_quality_layout.addWidget(self.jpeg_quality_slider)
        jpeg_quality_layout.addWidget(self.jpeg_quality_value_label)
        self.jpeg_quality_widgets = [self.jpeg_quality_label, self.jpeg_quality_slider, self.jpeg_quality_value_label] # Keep this list
        layout.addRow(self.jpeg_quality_label, jpeg_quality_layout)

        group.setLayout(layout)
        return group

    def _create_resolution_group(self) -> QGroupBox: # No change, just for context
        group = QGroupBox("解像度設定")
        layout = QFormLayout()

        self.preset_combo = QComboBox()
        # self.presets will be initialized in _load_settings or based on current_view_params
        # It's better to populate items after self.presets is fully defined.
        layout.addRow(QLabel("プリセット:"), self.preset_combo)

        self.width_spinbox = QSpinBox(); self.width_spinbox.setRange(1, 32768); self.width_spinbox.setSuffix(" px")
        self.height_spinbox = QSpinBox(); self.height_spinbox.setRange(1, 32768); self.height_spinbox.setSuffix(" px")
        res_size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.width_spinbox.setSizePolicy(res_size_policy); self.height_spinbox.setSizePolicy(res_size_policy)

        dims_layout = QHBoxLayout()
        dims_layout.addWidget(self.width_spinbox); dims_layout.addWidget(QLabel("x")); dims_layout.addWidget(self.height_spinbox)
        layout.addRow(QLabel("サイズ (幅x高):"), dims_layout)

        self.aspect_ratio_check = QCheckBox("現在のアスペクト比を維持")
        # self.aspect_ratio_check.setChecked(True) # Set in _load_settings
        layout.addRow(self.aspect_ratio_check)

        self.memory_usage_label = QLabel("予測メモリ使用量: N/A MB")
        layout.addRow(self.memory_usage_label)

        group.setLayout(layout)
        return group

    def _create_options_group(self) -> QGroupBox: # No change, just for context
        group = QGroupBox("出力オプション")
        layout = QFormLayout()
        self.iterations_spinbox = QSpinBox(); self.iterations_spinbox.setRange(10, 1000000)
        layout.addRow(QLabel("最大反復回数:"), self.iterations_spinbox)
        self.antialiasing_combo = QComboBox()
        self.antialiasing_combo.addItems(["なし", "2x2 SSAA", "3x3 SSAA", "4x4 SSAA"]) # SSAA = Super-sampling Anti-aliasing
        layout.addRow(QLabel("アンチエイリアス:"), self.antialiasing_combo)
        group.setLayout(layout)
        return group

    def _create_buttons(self) -> QDialogButtonBox:
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("出力開始")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        return button_box

    def _connect_signals(self):
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.jpeg_quality_slider.valueChanged.connect(self._on_jpeg_quality_changed)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

        # Use partial to pass which dimension changed
        self.width_spinbox.valueChanged.connect(partial(self._on_dimension_changed, "width"))
        self.height_spinbox.valueChanged.connect(partial(self._on_dimension_changed, "height"))
        self.aspect_ratio_check.stateChanged.connect(self._on_aspect_ratio_toggled)

    def _load_settings(self): # Renamed from _load_initial_settings
        self.updates_enabled = False # Disable updates during loading

        saved_settings = self.settings_manager.get_setting(self.SETTINGS_SECTION_NAME, {})

        # File settings - Use saved settings, then dialog_defaults, then hardcoded defaults
        default_file_path_base = self.dialog_defaults.get('filepath', Path.home() / "fractal_render")
        file_format = saved_settings.get('format', self.dialog_defaults.get('format', 'PNG'))
        self.filepath_edit.setText(saved_settings.get('filepath', str(default_file_path_base) + f".{file_format.lower()}"))
        self.format_combo.setCurrentText(file_format)
        self.png_transparent_check.setChecked(saved_settings.get('png_transparent', self.dialog_defaults.get('png_transparent', False)))
        self.jpeg_quality_slider.setValue(saved_settings.get('jpeg_quality', self.dialog_defaults.get('jpeg_quality', 90)))

        # Resolution presets - needs self.presets to be defined
        self.presets = {
            "現在の表示": (self.current_view_params.get('image_width_px',800), self.current_view_params.get('image_height_px',600)),
            "HD (1280x720)": (1280, 720), "FHD (1920x1080)": (1920, 1080),
            "4K UHD (3840x2160)": (3840, 2160), "8K UHD (7680x4320)": (7680, 4320),
            "カスタム": (-1, -1)
        }
        self.preset_combo.blockSignals(True) # Block while populating
        self.preset_combo.clear()
        self.preset_combo.addItems(self.presets.keys())
        self.preset_combo.blockSignals(False)

        # Load resolution settings
        # Try to match saved width/height to a preset, otherwise set to custom
        saved_w = saved_settings.get('width', self.presets["現在の表示"][0])
        saved_h = saved_settings.get('height', self.presets["現在の表示"][1])
        current_preset_text = "カスタム" # Default to custom if no match
        for name, (pw, ph) in self.presets.items():
            if pw == saved_w and ph == saved_h and name != "カスタム":
                current_preset_text = name
                break

        self.preset_combo.setCurrentText(current_preset_text) # This will trigger _on_preset_changed
        # If it was custom, _on_preset_changed might not set width/height if they are already correct.
        if current_preset_text == "カスタム":
            self.width_spinbox.setValue(saved_w)
            self.height_spinbox.setValue(saved_h) # This will trigger _on_dimension_changed if aspect is kept

        self.aspect_ratio_check.setChecked(saved_settings.get('keep_aspect_ratio', True))

        # Output options
        default_iters = self.current_view_params.get('max_iterations', 100) * 2
        self.iterations_spinbox.setValue(saved_settings.get('iterations', default_iters))
        self.antialiasing_combo.setCurrentText(saved_settings.get('antialiasing', 'なし'))

        self._on_format_changed(self.format_combo.currentText())
        self.updates_enabled = True
        self._update_memory_usage_label() # Update once all resolution settings are stable

    @pyqtSlot()
    def _browse_filepath(self):
        current_path = self.filepath_edit.text()
        if not current_path:
            current_path = os.getcwd()

        format_filter = ""
        selected_format = self.format_combo.currentText()
        if selected_format == "PNG": format_filter = "PNG Files (*.png)"
        elif selected_format == "JPEG": format_filter = "JPEG Files (*.jpg *.jpeg)"
        elif selected_format == "TIFF": format_filter = "TIFF Files (*.tif *.tiff)"
        elif selected_format == "BMP": format_filter = "BMP Files (*.bmp)"
        all_filters = "All Files (*)"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "名前を付けて保存", current_path,
            f"{format_filter};;{all_filters}" if format_filter else all_filters
        )
        if filepath:
            self.filepath_edit.setText(filepath)

    @pyqtSlot(str)
    def _on_format_changed(self, format_str: str):
        is_png = (format_str == "PNG")
        is_jpeg = (format_str == "JPEG")
        self.png_transparent_check.setEnabled(is_png)
        if not is_png: self.png_transparent_check.setChecked(False)
        for widget in self.jpeg_quality_widgets:
            widget.setEnabled(is_jpeg)
        # Update file extension in path if user hasn't typed one
        current_path = self.filepath_edit.text()
        if current_path:
            name, ext = os.path.splitext(current_path)
            new_ext = f".{format_str.lower()}"
            if ext.lower() in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'] and ext.lower() != new_ext:
                 self.filepath_edit.setText(name + new_ext)
            elif not ext: # if no extension was there
                 self.filepath_edit.setText(current_path + new_ext)


    @pyqtSlot(int)
    def _on_jpeg_quality_changed(self, value: int):
        self.jpeg_quality_value_label.setText(f"{value}%")

    @pyqtSlot(str)
    def _on_preset_changed(self, preset_text: str):
        if preset_text == "カスタム":
            self.width_spinbox.setEnabled(True)
            self.height_spinbox.setEnabled(True)
        else:
            width, height = self.presets.get(preset_text, (0,0))
            if width > 0 and height > 0 :
                self.width_spinbox.blockSignals(True)
                self.height_spinbox.blockSignals(True)
                self.width_spinbox.setValue(width)
                self.height_spinbox.setValue(height)
                self.width_spinbox.blockSignals(False)
                self.height_spinbox.blockSignals(False)
                self.width_spinbox.setEnabled(False) # Or based on aspect_ratio_check
                self.height_spinbox.setEnabled(False)
                self._update_memory_usage_label() # Update for new preset

        # If aspect ratio is kept, changing preset should ensure width/height are disabled
        # or one of them is if custom editing is allowed while keeping ratio.
        # For simplicity, preset disables direct W/H edit. "Custom" enables them.
        self._on_aspect_ratio_toggled(self.aspect_ratio_check.isChecked())


    @pyqtSlot(int) # state is int for QCheckBox.stateChanged
    def _on_aspect_ratio_toggled(self, state_int: int):
        self.keep_aspect_ratio_enabled = (state_int == Qt.CheckState.Checked.value)
        # If "Custom" preset, and aspect ratio is checked, one of width/height should be disabled
        # For now, let's assume user changes one, the other follows if checked.
        # And if preset is not "Custom", width/height are usually disabled by _on_preset_changed.
        if self.preset_combo.currentText() == "カスタム":
             self.width_spinbox.setEnabled(True) # Both enabled for custom, aspect handled by _on_dimension_changed
             self.height_spinbox.setEnabled(True)


    @pyqtSlot(str) # Argument 'changed_source' will be "width" or "height"
    def _on_dimension_changed(self, changed_source: str):
        if not self.keep_aspect_ratio_enabled or not self.updates_enabled: return

        self.updates_enabled = False # Prevent recursive updates

        w_box = self.width_spinbox
        h_box = self.height_spinbox

        if changed_source == "width":
            new_width = w_box.value()
            new_height = int(round(new_width / self.source_aspect_ratio))
            if h_box.value() != new_height: h_box.setValue(new_height)
        elif changed_source == "height":
            new_height = h_box.value()
            new_width = int(round(new_height * self.source_aspect_ratio))
            if w_box.value() != new_width: w_box.setValue(new_width)

        if self.preset_combo.currentText() != "カスタム":
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText("カスタム") # Dimensions changed, so it's custom now
            self.preset_combo.blockSignals(False)
            self.width_spinbox.setEnabled(True) # Enable for custom edit
            self.height_spinbox.setEnabled(True)

        self._update_memory_usage_label()
        self.updates_enabled = True


    def _update_memory_usage_label(self):
        width = self.width_spinbox.value(); height = self.height_spinbox.value()
        bytes_per_pixel = 4 # RGBA
        ssaa_text = self.antialiasing_combo.currentText(); ssaa_factor = 1
        if "SSAA" in ssaa_text and ssaa_text[0].isdigit(): ssaa_factor = int(ssaa_text[0])**2
        mem_bytes = width * height * bytes_per_pixel * ssaa_factor
        mem_mb = mem_bytes / (1024 * 1024)
        self.memory_usage_label.setText(f"予測メモリ使用量: {mem_mb:.2f} MB")

    def accept(self): # Override accept to save settings
        current_settings = self.get_export_settings()
        if not current_settings.get('filepath'):
            QMessageBox.warning(self, "入力エラー", "ファイルパスを指定してください。")
            return # Prevent dialog from closing

        self.settings_manager.set_setting(self.SETTINGS_SECTION_NAME, current_settings)
        super().accept()


    def get_export_settings(self) -> dict:
        # Ensure all relevant settings are gathered from UI
        s = {
            'filepath': self.filepath_edit.text(),
            'format': self.format_combo.currentText(),
            'png_transparent': self.png_transparent_check.isChecked(), # Checked state is fine
            'jpeg_quality': self.jpeg_quality_slider.value(),
            'width': self.width_spinbox.value(),
            'height': self.height_spinbox.value(),
            'keep_aspect_ratio': self.aspect_ratio_check.isChecked(),
            'iterations': self.iterations_spinbox.value(),
            'antialiasing': self.antialiasing_combo.currentText()
        }
        # Convert antialiasing text to factor for engine
        aa_text = s['antialiasing']
        if "SSAA" in aa_text and aa_text[0].isdigit(): s['antialiasing_factor'] = int(aa_text[0])
        else: s['antialiasing_factor'] = 1
        return s

    # Removed custom __setattr__ for updates_enabled, using explicit calls or signal blocking.

if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create a dummy settings manager for the test
    # In a real app, this would be passed from MainWindow/Application
    test_settings_file = "dialog_test_settings.json"
    settings_mgr = SettingsManager(settings_filename=test_settings_file)

    # Simulate some saved settings
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.filepath", str(Path.home() / "my_fractal.png"))
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.format", "PNG")
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.width", 2000)
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.iterations", 300)


    dummy_dialog_defaults = {'filepath': str(Path.home()/"default_export.png"), 'format': 'JPEG',
                             'width':1024, 'height':768, 'iterations': 150,
                             'keep_aspect_ratio': False, 'jpeg_quality': 80}
    dummy_view_params = {'max_iterations': 200, 'image_width_px': 800, 'image_height_px': 600}

    dialog = HighResOutputDialog(settings_manager=settings_mgr,
                                 current_dialog_defaults=dummy_dialog_defaults,
                                 current_view_params=dummy_view_params)

    if dialog.exec():
        final_settings = dialog.get_export_settings()
        print("Export Settings from Dialog:", final_settings)
        # Check if settings were saved by the dialog's accept()
        reloaded_saved_settings = settings_mgr.get_setting(HighResOutputDialog.SETTINGS_SECTION_NAME)
        print("Settings saved by Dialog:", reloaded_saved_settings)
        assert final_settings == reloaded_saved_settings # Ensure what's returned is what's saved
    else:
        print("Export Cancelled by user.")

    # Clean up test settings file
    if Path(test_settings_file).exists(): Path(test_settings_file).unlink(missing_ok=True)
    # Clean up settings file potentially created by SettingsManager in default location
    default_sm_file = Path.home() / ".fractalapp" / "fractal_app_settings.json" # Default path in SettingsManager
    if default_sm_file.exists(): default_sm_file.unlink(missing_ok=True)
    if (Path.home() / ".fractalapp").exists() and not any((Path.home() / ".fractalapp").iterdir()):
        (Path.home() / ".fractalapp").rmdir()

    # sys.exit(app.exec()) # Only if this is the main app loop
    # For testing, usually don't start a new app.exec() if one is already running.
    # If this is run as a standalone script, app.exec() is fine.
    # In a larger app, this dialog is modal, so app.exec() isn't needed here.
    # For this test, we'll just let it finish.
    # sys.exit(0) if no event loop was started by this script directly.
    # If app = QApplication(sys.argv) is the only QApplication instance, then sys.exit(app.exec()) is fine.
    # For this specific case, we can omit sys.exit if this is meant to be imported.
    # If run as main:
    # exit_code = app.exec()
    # sys.exit(exit_code)

    # Test done, no app.exec() needed if run as part of a larger test suite that manages the app loop
    # or if just testing dialog logic without showing it modally for long.
    # For this type of __main__ block, usually it's for quick visual check, so app.exec() is fine.
    if not QApplication.instance(): # If no app instance exists (e.g. running script directly)
        sys.exit(app.exec()) # Start event loop
    else: # If an app instance already exists (e.g. imported in a test runner)
        print("Dialog test finished (assuming an external event loop or modal execution).")
        # dialog.show() # Non-modal for inspection if needed, then manually close
        pass
