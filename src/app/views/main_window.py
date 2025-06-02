from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QStatusBar, QSplitter, QLabel, QWidget, QApplication, QVBoxLayout
)
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QMainWindow, QMenuBar, QStatusBar, QSplitter, QVBoxLayout, QApplication # Added imports
from .render_area import RenderArea
from .parameter_panel import ParameterPanel
from .high_res_dialog import HighResOutputDialog
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
# Import SettingsManager for type hinting if not already (though not strictly necessary for constructor arg)
# from src.app.utils.settings_manager import SettingsManager


class MainWindow(QMainWindow):
    def __init__(self, fractal_controller, settings_manager): # Added settings_manager
        super().__init__()
        self.fractal_controller = fractal_controller
        self.settings_manager = settings_manager # Store settings_manager

        self.setWindowTitle("高機能フラクタル描画アプリケーション")
        self.resize(1400, 800)

        self.progress_dialog: QProgressDialog | None = None
        # Load last export settings from SettingsManager, or use empty dict
        self.last_export_settings: dict = self.settings_manager.get_setting(
            HighResOutputDialog.SETTINGS_SECTION_NAME, {}
        )


        # UI Initialization
        self._create_actions()
        self._create_menu_bar() # Then create menus and add actions
        self.status_bar = self.statusBar() # Get status bar
        self.status_bar.showMessage("準備完了")

        self._setup_central_widget() # Setup RenderArea and ParameterPanel

        self._connect_controller_signals() # Connect signals from FractalController

        self._initial_render_done = False
        self._initial_render_attempts = 0

    def _create_actions(self):
        self.export_action = QAction("高解像度出力...", self)
        self.export_action.setShortcut("Ctrl+E")
        # self.export_action.triggered.connect(self._open_high_res_dialog) # Connection moved to _connect_controller_signals or direct in menu

        # Example Exit Action (can be expanded)
        self.exit_action = QAction("終了", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)


    def _create_menu_bar(self): # Renamed from _create_menus for consistency
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu("&ファイル")
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Help Menu (Placeholder)
        help_menu = menu_bar.addMenu("&ヘルプ")
        about_action = QAction("バージョン情報", self)
        # about_action.triggered.connect(self._show_about_dialog) # Placeholder for about dialog
        help_menu.addAction(about_action)


    def _connect_controller_signals(self):
        if self.fractal_controller:
            # Fractal rendering and parameter updates
            if hasattr(self.render_area, 'update_image'):
                self.fractal_controller.image_rendered.connect(self.render_area.update_image)
            if hasattr(self.parameter_panel, 'parameters_changed_in_ui_signal'):
                self.parameter_panel.parameters_changed_in_ui_signal.connect(self.on_ui_parameters_changed)
            if hasattr(self.parameter_panel, 'render_button'): # Assuming render button is on ParameterPanel
                self.parameter_panel.render_button.clicked.connect(self.trigger_render_from_panel)

            if hasattr(self.fractal_controller, 'parameters_updated_externally') and \
               hasattr(self.parameter_panel, 'update_ui_from_controller_parameters'):
                self.fractal_controller.parameters_updated_externally.connect(
                    self.parameter_panel.update_ui_from_controller_parameters)

            if hasattr(self.fractal_controller, 'active_fractal_plugin_ui_needs_update') and \
               hasattr(self.parameter_panel, '_update_fractal_plugin_specific_ui'): # Assuming method name
                self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(
                    self.parameter_panel._update_fractal_plugin_specific_ui) # Connect to the correct slot

            if hasattr(self.fractal_controller, 'active_coloring_plugin_ui_needs_update') and \
               hasattr(self.parameter_panel, '_update_coloring_plugin_specific_ui'):
                self.fractal_controller.active_coloring_plugin_ui_needs_update.connect(
                    self.parameter_panel._update_coloring_plugin_specific_ui)

            if hasattr(self.fractal_controller, 'active_color_map_changed_externally') and \
               hasattr(self.parameter_panel, '_update_color_selection_from_controller'):
                self.fractal_controller.active_color_map_changed_externally.connect(
                    self.parameter_panel._update_color_selection_from_controller)

            # High-resolution export signals
            self.fractal_controller.export_started.connect(self._on_export_started)
            self.fractal_controller.export_progress_updated.connect(self._on_export_progress_updated)
            self.fractal_controller.export_process_finished.connect(self._on_export_process_finished)

            # Connect export action trigger
            if hasattr(self, 'export_action'):
                 self.export_action.triggered.connect(self._open_high_res_dialog)
            # Ensure status bar connection is robust
            if hasattr(self, 'status_bar') and self.status_bar is not None:
                 self.fractal_controller.status_updated.connect(self.update_status_bar)
            else:
                 print("MainWindow Warning: StatusBar not initialized before connecting signals.")
        else:
            print("MainWindow: FractalController not available for signal connections.")


    def update_status_bar(self, message: str): # No change
        if self.status_bar: self.status_bar.showMessage(message)

    def _setup_central_widget(self):
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.render_area = RenderArea(self, fractal_controller=self.fractal_controller)
        splitter.addWidget(self.render_area)
        self.parameter_panel = ParameterPanel(self.fractal_controller, self)
        splitter.addWidget(self.parameter_panel)
        self.setCentralWidget(splitter)
        initial_width = self.width()
        splitter.setSizes([int(initial_width * 0.7), int(initial_width * 0.3)])

    def on_ui_parameters_changed(self, center_real, center_imag, width, max_iterations): # No change
        if self.fractal_controller:
            self.fractal_controller.update_common_fractal_parameters(center_real, center_imag, width, max_iterations)
        else:
            print("MainWindow: FractalController not available to update parameters.")

    @pyqtSlot()
    def _open_high_res_dialog(self):
        if not self.fractal_controller:
            QMessageBox.warning(self, "エラー", "コントローラーが利用できません。")
            return

        common_params = self.fractal_controller.get_current_common_parameters()
        fractal_plugin_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        fractal_plugin_params = self.fractal_controller.get_current_fractal_plugin_parameters_from_engine()
        coloring_algo_name = self.fractal_controller.get_active_coloring_plugin_name_from_engine()
        coloring_algo_params = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine()

        # Corrected way to get pack and map names
        current_pack_name_ctrl = self.fractal_controller.get_active_color_pack_name_from_engine()
        current_color_map_ctrl = self.fractal_controller.get_active_color_map_name_from_engine()


        view_params_for_dialog = {
            'image_width_px': self.render_area.width(),
            'image_height_px': self.render_area.height(),
            'max_iterations': common_params.get('max_iterations', 100)
        }

        dialog_defaults = self.last_export_settings.copy()
        dialog_defaults['iterations'] = common_params.get('max_iterations', 100) * 2
        # If last_export_settings is empty, dialog_defaults will use HighResOutputDialog's internal defaults for width/height
        # or we can explicitly set them from current view if last_export_settings is empty.
        if not self.last_export_settings.get('width'): # if no width in saved settings
             dialog_defaults['width'] = self.render_area.width()
             dialog_defaults['height'] = self.render_area.height()


        dialog = HighResOutputDialog(
            settings_manager=self.settings_manager,
            current_dialog_defaults=dialog_defaults,
            current_view_params=view_params_for_dialog,
            parent=self
        )

        if dialog.exec():
            export_settings = dialog.get_export_settings() # This gets settings from UI & saves them via dialog.accept()
            if export_settings and export_settings.get('filepath'):
                print(f"MainWindow: Export dialog accepted. Settings from dialog: {export_settings}")

                # Pass current engine state for parts not directly set in dialog but needed by engine's generate method
                export_settings['fractal_plugin_name'] = fractal_plugin_name
                export_settings['fractal_plugin_params'] = fractal_plugin_params
                export_settings['coloring_algorithm_name'] = coloring_algo_name
                export_settings['coloring_algorithm_params'] = coloring_algo_params
                export_settings['color_pack_name'] = current_pack_name_ctrl
                export_settings['color_map_name'] = current_color_map_ctrl
                # Common params like center/width for the fractal itself are taken from current engine state by default
                # in generate_image_for_output, unless overridden by common_params_override.
                # The dialog mainly overrides iterations, resolution, AA, file details.
                # We must ensure that the common_params_override in generate_image_for_output correctly uses
                # the iterations from export_settings['iterations'].
                # The current engine's center_real, center_imag, width will be used by default by generate_image_for_output
                # which is typically what is desired for exporting the "current view" at high-res.
                # If the dialog were to allow changing center/width for export, those would go into common_params_override.

                self.fractal_controller.start_high_res_export(export_settings)
                self.last_export_settings = export_settings # Update last used settings for next dialog open
            else:
                QMessageBox.warning(self, "出力エラー", "ファイルパスが指定されていません。")
        else:
            print("MainWindow: Export dialog cancelled.")

    @pyqtSlot()
    def _on_export_started(self):
        if self.progress_dialog: self.progress_dialog.cancel()
        self.progress_dialog = QProgressDialog("高解像度画像を生成中...", "キャンセル", 0, 100, self)
        self.progress_dialog.setWindowTitle("エクスポート処理中")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        if self.fractal_controller: self.progress_dialog.canceled.connect(self.fractal_controller.cancel_current_export)
        self.progress_dialog.setValue(0)
        if hasattr(self, 'export_action'): self.export_action.setEnabled(False) # Disable while exporting
        print("MainWindow: Export started. Progress dialog shown.")

    @pyqtSlot(int)
    def _on_export_progress_updated(self, value: int):
        if self.progress_dialog: self.progress_dialog.setValue(value)

    @pyqtSlot(bool, str)
    def _on_export_process_finished(self, success: bool, message: str):
        print(f"MainWindow: Export process finished. Success: {success}, Message: {message}")
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if success: QMessageBox.information(self, "エクスポート完了", f"画像を保存しました:\n{message}")
        else: QMessageBox.warning(self, "エクスポート失敗", f"エラーが発生しました:\n{message}")

        if hasattr(self, 'export_action'): self.export_action.setEnabled(True) # Re-enable
        self.update_status_bar(f"エクスポート完了: {message}" if success else f"エクスポート失敗: {message}")


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
        self.fractal_controller.update_common_fractal_parameters(
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
        self.fractal_controller.update_common_fractal_parameters(
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
    from PyQt6.QtCore import QTimer, QObject, pyqtSignal # For timed emission in test and QObject/pyqtSignal
    import numpy # For creating dummy data in test

    import numpy as np  # Ensure numpy is imported as np

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
