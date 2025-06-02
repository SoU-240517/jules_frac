from PyQt6.QtCore import QObject, pyqtSignal
# Import for type hinting, will be commented out if it causes issues in this environment
# from src.app.models.fractal_engine import FractalEngine
# from src.app.views.main_window import MainWindow


class FractalController(QObject):
    image_rendered = pyqtSignal(object)  # For the colored RGBA data (NumPy array)
    status_updated = pyqtSignal(str) # For status bar display
    parameters_updated_externally = pyqtSignal() # To notify UI if params change non-interactively

import time # For measuring execution time

class FractalController(QObject):
    image_rendered = pyqtSignal(object)  # For the colored RGBA data (NumPy array)
    status_updated = pyqtSignal(str) # For status bar display
    parameters_updated_externally = pyqtSignal() # To notify UI common params if params change non-interactively
    active_plugin_ui_needs_update = pyqtSignal(str) # To tell ParameterPanel to rebuild plugin-specific UI

    def __init__(self, fractal_engine): # fractal_engine: FractalEngine
        super().__init__()
        self.fractal_engine = fractal_engine
        self.main_window = None # main_window: MainWindow
        self.last_compute_time_ms = 0.0
        self.last_coloring_time_ms = 0.0
        # Store initial width for zoom factor calculation.
        # Assumes fractal_engine is initialized with some default width.
        self.initial_width = self.fractal_engine.width if self.fractal_engine else 3.0


    def set_main_window(self, main_window): # main_window: MainWindow
        self.main_window = main_window
        self.update_status_display() # Initial status update

    def update_fractal_parameters(self, center_real, center_imag, width, max_iterations):
        """Called from UI or other methods to update fractal parameters."""
        # print(f"Controller: Updating fractal parameters to (real={center_real}, imag={center_imag}), width={width}, iter={max_iterations}")
        if self.fractal_engine:
            self.fractal_engine.set_parameters(center_real, center_imag, width, max_iterations)
            # If width is changed directly by user (not zoom/pan), consider resetting initial_width for zoom factor
            # For now, initial_width remains fixed to the very first width.
            # Or, update initial_width if source is UI direct and it's a width change.
            # self.initial_width = width # This would make current view 1x zoom.
        self.update_status_display()


    def trigger_render(self, image_width_px=None, image_height_px=None):
        """Initiates the fractal computation, coloring, and emits the result."""
        if self.fractal_engine is None:
            self.status_updated.emit("エラー: フラクタルエンジンが設定されていません.")
            return

        if image_width_px is not None and image_height_px is not None:
             self.fractal_engine.update_image_size(image_width_px, image_height_px)

        # Ensure image dimensions are set if not provided (e.g., from RenderArea size)
        if self.fractal_engine.image_width_px <= 0 or self.fractal_engine.image_height_px <= 0:
            if self.main_window and hasattr(self.main_window, 'render_area'):
                # Fallback to RenderArea's current size if available
                current_render_area_width = self.main_window.render_area.width()
                current_render_area_height = self.main_window.render_area.height()
                if current_render_area_width > 0 and current_render_area_height > 0:
                    self.fractal_engine.update_image_size(current_render_area_width, current_render_area_height)
                else:
                    self.status_updated.emit("Error: Invalid image dimensions for rendering.")
                    return
            else: # Default if no main_window or render_area info
                self.fractal_engine.update_image_size(800, 600) # Default size
                self.status_updated.emit("Warning: Rendering with default image size (800x600).")


        print(f"Controller: Triggering render for {self.fractal_engine.image_width_px}x{self.fractal_engine.image_height_px}...")
        # Update status to indicate computation is starting
        self.status_updated.emit(
            f"計算中... 中心:({self.fractal_engine.center_real:.4f}, {self.fractal_engine.center_imag:.4f}), "
            f"幅:{self.fractal_engine.width:.3e}, Iter:{self.fractal_engine.max_iterations}"
        )

        if image_width_px is not None and image_height_px is not None:
             self.fractal_engine.update_image_size(image_width_px, image_height_px)

        if self.fractal_engine.image_width_px <= 0 or self.fractal_engine.image_height_px <= 0:
            # This check was in controller, ensure it's still relevant or handled by engine
            if self.main_window and hasattr(self.main_window, 'render_area'):
                current_render_area_width = self.main_window.render_area.width()
                current_render_area_height = self.main_window.render_area.height()
                if current_render_area_width > 0 and current_render_area_height > 0:
                    self.fractal_engine.update_image_size(current_render_area_width, current_render_area_height)
                else:
                    self.status_updated.emit("エラー: 画像サイズが不正です.")
                    return
            else:
                self.fractal_engine.update_image_size(800, 600)
                self.status_updated.emit("警告: デフォルト画像サイズ(800x600)で描画します.")

        # Measure computation time
        start_compute_time = time.perf_counter()
        escape_time_data = self.fractal_engine.compute_mandelbrot()
        end_compute_time = time.perf_counter()
        self.last_compute_time_ms = (end_compute_time - start_compute_time) * 1000

        if escape_time_data is None:
            self.status_updated.emit("エラー: 計算に失敗しました.")
            return

        # Measure coloring time
        start_coloring_time = time.perf_counter()
        colored_data = self.fractal_engine.apply_basic_coloring(escape_time_data)
        end_coloring_time = time.perf_counter()
        self.last_coloring_time_ms = (end_coloring_time - start_coloring_time) * 1000

        self.image_rendered.emit(colored_data)
        # print(f"Controller: Render complete. Compute: {self.last_compute_time_ms:.2f}ms, Coloring: {self.last_coloring_time_ms:.2f}ms")

        # Update status display with final information including timings
        self.update_status_display()


    def update_status_display(self):
        """Updates the status bar text with current fractal parameters, plugin info, and performance metrics."""
        if not self.fractal_engine:
            self.status_updated.emit("フラクタルエンジンが準備できていません.")
            return

        active_plugin = self.fractal_engine.get_active_plugin()
        if not active_plugin:
            self.status_updated.emit("アクティブなフラクタルプラグインがありません。")
            return

        common_params = self.fractal_engine.get_common_parameters()
        plugin_params = self.fractal_engine.get_plugin_parameters()

        current_width = common_params.get('width', self.initial_width) # Use initial_width as fallback if width not in common_params
        zoom_level = self.initial_width / current_width if current_width > 0 else float('inf')

        status_parts = [
            f"プラグイン: {active_plugin.name}",
            f"中心: ({common_params.get('center_real', 0):.5f}, {common_params.get('center_imag', 0):.5f})",
            f"幅: {current_width:.3e} (ズーム: {zoom_level:.2f}x)",
            f"Iter: {common_params.get('max_iterations', 0)}"
        ]

        if plugin_params:
            param_str_parts = []
            for k, v in plugin_params.items():
                if isinstance(v, float):
                    param_str_parts.append(f"{k}: {v:.4f}")
                else:
                    param_str_parts.append(f"{k}: {v}")
            status_parts.append(f"プラグインP: [{', '.join(param_str_parts)}]")

        status_parts.extend([
            f"解像度: {self.fractal_engine.image_width_px}x{self.fractal_engine.image_height_px}",
            f"計算: {self.last_compute_time_ms:.2f} ms",
            f"着色: {self.last_coloring_time_ms:.2f} ms"
        ])

        self.status_updated.emit(" | ".join(status_parts))


    def get_current_parameters(self): # Keep this as it might be used by ParameterPanel directly
        """Returns a dictionary of all current parameters relevant for UI (common and engine's image size)."""
        if self.fractal_engine:
            return {
                "center_real": self.fractal_engine.center_real,
                "center_imag": self.fractal_engine.center_imag,
                "width": self.fractal_engine.width,
                "max_iterations": self.fractal_engine.max_iterations,
                "image_width_px": self.fractal_engine.image_width_px,
                "image_height_px": self.fractal_engine.image_height_px,
                "height": self.fractal_engine.height
            }
        return {}

    # Renaming for clarity and consistency with get_current_parameters
    def get_current_engine_parameters(self):
        """Returns a dictionary of the current fractal engine's core calculation parameters."""
        # This is similar to get_current_parameters but might be focused on what RenderArea needs for coord calculations
        if self.fractal_engine:
            return {
                "center_real": self.fractal_engine.center_real,
                "center_imag": self.fractal_engine.center_imag,
                "width": self.fractal_engine.width,
                "height": self.fractal_engine.height,
                "max_iterations": self.fractal_engine.max_iterations
                # image_width_px and image_height_px might also be useful here if RenderArea needs them
            }
        return {}

    def get_plugin_presets(self, plugin_name: str) -> dict | None:
        """Gets presets for a specific plugin by its name, if available."""
        if self.fractal_engine:
            plugin = self.fractal_engine.plugin_manager.get_plugin(plugin_name)
            if plugin: # Plugin instance itself, not its name
                return plugin.get_presets() # Assumes get_presets() is defined in base or implemented
        return None


    def get_available_plugin_names_from_engine(self) -> list[str]:
        """Retrieves the list of available plugin names from the fractal engine."""
        if self.fractal_engine:
            return self.fractal_engine.get_available_plugin_names()
        return []

    def get_active_plugin_name_from_engine(self) -> str | None:
        """Retrieves the name of the currently active plugin from the fractal engine."""
        if self.fractal_engine and self.fractal_engine.get_active_plugin():
            return self.fractal_engine.get_active_plugin().name
        return None

    def get_plugin_parameter_definitions(self, plugin_name: str) -> list:
        """Gets parameter definitions for a specific plugin by its name."""
        if self.fractal_engine:
            plugin = self.fractal_engine.plugin_manager.get_plugin(plugin_name)
            if plugin:
                return plugin.get_parameters_definition()
        return []

    def get_current_plugin_parameters(self) -> dict:
        """Gets current parameter values for the active plugin from the engine."""
        if self.fractal_engine:
            return self.fractal_engine.get_plugin_parameters()
        return {}

    def set_plugin_parameter_value(self, param_name: str, value: any):
        """Sets a specific parameter value for the active plugin in the engine."""
        if self.fractal_engine:
            self.fractal_engine.set_plugin_parameter(param_name, value)
            # Parameter change might affect status or require UI update, but not a full redraw usually
            self.update_status_display()


    def set_active_fractal_plugin_and_redraw(self, plugin_name: str):
        """
        Sets the active fractal plugin, updates UI (common and specific), and triggers re-render.
        """
        if not self.fractal_engine:
            print("Controller Error: Fractal engine not available.")
            return

        success = self.fractal_engine.set_active_plugin(plugin_name)
        if success:
            print(f"Controller: Active plugin set to '{plugin_name}'. Initiating UI updates and re-render.")

            # 1. Notify ParameterPanel to update its common parameter fields (center, width, iterations)
            self.parameters_updated_externally.emit()

            # 2. Notify ParameterPanel to update plugin-specific UI section
            self.active_plugin_ui_needs_update.emit(plugin_name)

            # 3. Trigger re-render with the new plugin's (potentially new) default view
            if self.main_window and hasattr(self.main_window, 'render_area'):
                render_width = self.main_window.render_area.width()
                render_height = self.main_window.render_area.height()
                if render_width > 0 and render_height > 0:
                    self.trigger_render(render_width, render_height)
                else:
                    # Fallback if render area size is not yet determined
                    self.trigger_render()
            else:
                self.trigger_render() # Fallback if main_window or render_area not available
        else:
            print(f"Controller: Failed to set active plugin to '{plugin_name}'.")


    def pan_fractal(self, delta_real, delta_imag):
        """Pans the fractal view by the given delta in complex coordinates."""
        current_params = self.get_current_engine_parameters()
        if not current_params: # If engine not available or params empty
            print("Controller: Cannot pan, engine parameters not available.")
            return

        # New center is old center MINUS delta, because delta represents mouse dragging direction
        # e.g., mouse drags right (positive delta_real), so fractal's center moves left (negative delta_real on center)
        new_center_real = current_params['center_real'] - delta_real
        new_center_imag = current_params['center_imag'] - delta_imag

        print(f"Controller: Panning. Delta Real: {delta_real:.4e}, Delta Imag: {delta_imag:.4e}")
        print(f"Controller: Old Center: ({current_params['center_real']:.6f}, {current_params['center_imag']:.6f})")
        print(f"Controller: New Center: ({new_center_real:.6f}, {new_center_imag:.6f})")

        # Update engine parameters
        self.fractal_engine.set_parameters(
            new_center_real,
            new_center_imag,
            current_params['width'],       # Width remains the same during pan
            current_params['max_iterations'] # Iterations remain the same
        )
        self.update_status_display() # Update status bar
        self.parameters_updated_externally.emit() # Notify UI (ParameterPanel) to update its fields

        # Trigger re-render with current RenderArea dimensions
        if self.main_window and hasattr(self.main_window, 'render_area'):
            render_width = self.main_window.render_area.width()
            render_height = self.main_window.render_area.height()
            if render_width > 0 and render_height > 0:
                self.trigger_render(render_width, render_height)
            else:
                self.trigger_render() # Fallback to controller's default/last known size
        else:
            self.trigger_render()


    def zoom_fractal_to_point(self, fixed_point_real, fixed_point_imag, mouse_frac_x, mouse_frac_y, new_width):
        """
        Zooms the view such that the given fractal coordinate (fixed_point_real, fixed_point_imag)
        remains at the same relative mouse position (mouse_frac_x, mouse_frac_y) in the RenderArea,
        using the new_width for the fractal's complex plane view.
        """
        if self.fractal_engine is None:
            print("Controller: Fractal engine not available for zoom.")
            return

        # Store old width and height for reference if needed, though engine handles aspect ratio.
        # old_width = self.fractal_engine.width

        # The engine will calculate the new_height based on new_width and image aspect ratio.
        # We need to set the new_width in the engine first to get the correct new_height for center calculation.
        # However, set_parameters takes all params. So, we calculate new_center first, then call set_parameters.

        # Calculate new_height based on the image's aspect ratio
        # This assumes image_width_px and image_height_px are correctly set in the engine.
        if self.fractal_engine.image_width_px == 0: # Avoid division by zero
            print("Controller: Error - image_width_px is zero in fractal_engine. Cannot calculate aspect ratio for zoom.")
            return
        aspect_ratio = self.fractal_engine.image_height_px / self.fractal_engine.image_width_px
        new_height = new_width * aspect_ratio

        # Calculate the new center coordinates.
        # The fixed fractal point (fixed_point_real, fixed_point_imag) should correspond to
        # the relative mouse position (mouse_frac_x, mouse_frac_y) in the new view.
        # new_center_real = fixed_point_real - (mouse_frac_x * new_width) + (0.5 * new_width)
        new_center_real = fixed_point_real - (mouse_frac_x - 0.5) * new_width

        # For imaginary part, remember that mouse_frac_y is 0 at top, 1 at bottom.
        # Complex imaginary usually increases upwards.
        # new_center_imag = fixed_point_imag + (mouse_frac_y * new_height) - (0.5 * new_height)
        new_center_imag = fixed_point_imag + (mouse_frac_y - 0.5) * new_height # Corrected based on typical derivation

        print(f"Controller: Zooming. New Width: {new_width:.6e}, New Height: {new_height:.6e}")
        print(f"Controller: Fixed Point (Real, Imag): ({fixed_point_real:.6f}, {fixed_point_imag:.6f})")
        print(f"Controller: Mouse Frac (X, Y): ({mouse_frac_x:.3f}, {mouse_frac_y:.3f})")
        print(f"Controller: Old Center: ({self.fractal_engine.center_real:.6f}, {self.fractal_engine.center_imag:.6f})")
        print(f"Controller: Calculated New Center: ({new_center_real:.6f}, {new_center_imag:.6f})")

        self.fractal_engine.set_parameters(
            new_center_real,
            new_center_imag,
            new_width,
            self.fractal_engine.max_iterations # Iterations typically unchanged by zoom
        )
        self.update_status_display()
        self.parameters_updated_externally.emit() # Notify UI to update

        # Trigger re-render
        if self.main_window and hasattr(self.main_window, 'render_area'):
            render_width = self.main_window.render_area.width()
            render_height = self.main_window.render_area.height()
            if render_width > 0 and render_height > 0:
                self.trigger_render(render_width, render_height)
            else:
                self.trigger_render()
        else:
            self.trigger_render()


    def handle_programmatic_parameter_change(self, center_real, center_imag, width, max_iterations=None):
        """
        Call this after parameters are changed programmatically (e.g., future explicit set, load preset).
        This method updates the engine and then notifies the UI.
        """
        current_max_iter = self.fractal_engine.max_iterations if max_iterations is None else max_iterations
        self.fractal_engine.set_parameters(center_real, center_imag, width, current_max_iter)
        self.update_status_display()
        self.parameters_updated_externally.emit() # Notify UI to update its input fields
        # Optionally, trigger a re-render automatically after such changes
        # self.trigger_render()


if __name__ == '__main__':
    # Mock classes for testing
    class MockFractalEngine:
        def __init__(self):
            self.max_iterations = 50
            self.center_real = -0.6
            self.center_imag = 0.0
            self.width = 3.5
            self.image_width_px = 100
            self.image_height_px = 75
            self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width
            # print(f"MockEngine initialized: {self.image_width_px}x{self.image_height_px}, height={self.height}") # Less verbose


        def set_parameters(self, cr, ci, w, mi=None):
            self.center_real, self.center_imag, self.width = cr, ci, w
            if mi is not None: self.max_iterations = mi
            if self.image_width_px > 0:
                self.height = (self.width * self.image_height_px) / self.image_width_px
            print(f"MockEngine: Params set - CR={cr}, CI={ci}, W={w}, MI={self.max_iterations}, H={self.height}")

        def compute_mandelbrot(self):
            # print(f"MockEngine: compute_mandelbrot called for {self.image_width_px}x{self.image_height_px}") # Less verbose
            import numpy
            return numpy.zeros((self.image_height_px, self.image_width_px), dtype=numpy.int32)

        def apply_basic_coloring(self, escape_times):
            # print(f"MockEngine: apply_basic_coloring called for data of shape {escape_times.shape}") # Less verbose
            import numpy
            # Return a dummy RGBA image
            return numpy.zeros((escape_times.shape[0], escape_times.shape[1], 4), dtype=numpy.uint8)

        def update_image_size(self, w_px, h_px):
            self.image_width_px = w_px
            self.image_height_px = h_px
            if self.image_width_px > 0:
                self.height = (self.width * self.image_height_px) / self.image_width_px
            # print(f"MockEngine: Image size updated to {w_px}x{h_px}, new height {self.height}") # Less verbose

    class MockMainWindow:
        def __init__(self):
            class MockRenderArea: # Mock RenderArea for size
                def width(self): return 20 # Small default for faster test
                def height(self): return 15 # Small default for faster test
            self.render_area = MockRenderArea()
            # print("MockMainWindow initialized with MockRenderArea") # Less verbose

    # Test setup
    mock_engine = MockFractalEngine()
    controller = FractalController(mock_engine)
    mock_main_win = MockMainWindow() # MockMainWindow now has a mock RenderArea
    controller.set_main_window(mock_main_win)

    rendered_data_info = {}
    last_status = ""
    params_externally_updated_fired_count = 0

    def handle_image_rendered(data):
        nonlocal rendered_data_info
        rendered_data_info['shape'] = data.shape
        rendered_data_info['dtype'] = data.dtype

    def handle_status_update(status):
        nonlocal last_status
        last_status = status

    def handle_params_externally_updated():
        nonlocal params_externally_updated_fired_count
        params_externally_updated_fired_count +=1
        print(f"Test: Controller.parameters_updated_externally signal received (count: {params_externally_updated_fired_count}).")

    controller.image_rendered.connect(handle_image_rendered)
    controller.status_updated.connect(handle_status_update)
    controller.parameters_updated_externally.connect(handle_params_externally_updated)

    print("\nTesting direct parameter update (simulates UI change, no external signal)...")
    controller.update_fractal_parameters(-0.7, 0.3, 2.0, 150)
    assert controller.get_current_engine_parameters()["width"] == 2.0
    assert "Width: 2.0000e+00" in last_status
    assert params_externally_updated_fired_count == 0

    print("\nTesting programmatic parameter change (e.g., after hypothetical zoom/pan)...")
    controller.handle_programmatic_parameter_change(-0.5, 0.1, 1.0, 200)
    assert controller.get_current_engine_parameters()["width"] == 1.0
    assert "Width: 1.0000e+00" in last_status
    assert controller.get_current_engine_parameters()["max_iterations"] == 200
    assert params_externally_updated_fired_count == 1

    print("\nTesting pan_fractal...")
    mock_engine.image_width_px = 800 # Ensure mock engine has image dims for aspect ratio in pan/zoom
    mock_engine.image_height_px = 600
    mock_engine.update_aspect_ratio() # Update height based on width and new image dims
    initial_cr = controller.get_current_engine_parameters()['center_real']
    initial_ci = controller.get_current_engine_parameters()['center_imag']
    controller.pan_fractal(0.1, -0.05)
    expected_cr = initial_cr - 0.1
    expected_ci = initial_ci - (-0.05) # Corrected: delta_imag is subtracted, so initial_ci - (-0.05) = initial_ci + 0.05
    assert abs(controller.get_current_engine_parameters()['center_real'] - expected_cr) < 1e-9
    assert abs(controller.get_current_engine_parameters()['center_imag'] - expected_ci) < 1e-9
    assert params_externally_updated_fired_count == 2

    print("\nTesting zoom_fractal_to_point...")
    # Ensure mock engine has image dimensions for aspect ratio calculations in controller's zoom
    mock_engine.image_width_px = 800
    mock_engine.image_height_px = 600
    if hasattr(mock_engine, 'update_aspect_ratio'): mock_engine.update_aspect_ratio()

    current_params_before_zoom = controller.get_current_engine_parameters()
    zoom_center_r, zoom_center_i = current_params_before_zoom['center_real'], current_params_before_zoom['center_imag']
    mouse_rel_x, mouse_rel_y = 0.5, 0.5
    new_zoom_width = current_params_before_zoom['width'] / 2.0

    controller.zoom_fractal_to_point(zoom_center_r, zoom_center_i, mouse_rel_x, mouse_rel_y, new_zoom_width)

    zoomed_params = controller.get_current_engine_parameters()
    assert abs(zoomed_params['center_real'] - zoom_center_r) < 1e-9, "Center real coord changed after zooming at center."
    assert abs(zoomed_params['center_imag'] - zoom_center_i) < 1e-9, "Center imag coord changed after zooming at center."
    assert abs(zoomed_params['width'] - new_zoom_width) < 1e-9, "Width did not update correctly after zoom."
    assert params_externally_updated_fired_count == 3, "parameters_updated_externally signal count incorrect after zoom."

    print("\nTesting plugin switching...")
    active_plugin_ui_updated_for = ""
    def handle_active_plugin_ui_needs_update(plugin_name_for_ui):
        nonlocal active_plugin_ui_updated_for
        active_plugin_ui_updated_for = plugin_name_for_ui
        print(f"Test: active_plugin_ui_needs_update signal received for '{plugin_name_for_ui}'.")
    controller.active_plugin_ui_needs_update.connect(handle_active_plugin_ui_needs_update)

    # Mock methods for PluginManager and Plugin interaction in FractalEngine
    class MockPlugin:
        def __init__(self, name, params_def=None, default_view=None):
            self._name = name
            self._params_def = params_def if params_def else []
            self._default_view = default_view if default_view else {}
        @property
        def name(self): return self._name
        def get_parameters_definition(self): return self._params_def
        def get_default_view_parameters(self): return self._default_view

    mock_mandelbrot_plugin = MockPlugin("Mandelbrot", default_view={'center_real':-0.5, 'width':3.0})
    mock_julia_plugin = MockPlugin("Julia",
                                   params_def=[{'name':'cx','default':0.1}],
                                   default_view={'center_real':0.0, 'width':2.5})

    mock_engine.plugin_manager.get_plugin = lambda name: mock_mandelbrot_plugin if name=="Mandelbrot" else (mock_julia_plugin if name=="Julia" else None)
    mock_engine.get_available_plugin_names = lambda: ["Mandelbrot", "Julia"]
    # Simulate engine's set_active_plugin behavior closely
    def mock_engine_set_active_plugin(plugin_name):
        plugin = mock_engine.plugin_manager.get_plugin(plugin_name)
        if plugin:
            mock_engine.current_plugin = plugin # Engine would store the instance
            # Engine would update its common params from plugin's default view
            dv = plugin.get_default_view_parameters()
            mock_engine.center_real = dv.get('center_real', mock_engine.center_real)
            mock_engine.width = dv.get('width', mock_engine.width)
            # Engine would reset its current_plugin_parameters
            mock_engine.current_plugin_parameters = {p['name']:p['default'] for p in plugin.get_parameters_definition()}
            print(f"MockEngine: Active plugin set to {plugin_name}. Common params updated. Plugin params reset to {mock_engine.current_plugin_parameters}")
            return True
        return False
    mock_engine.set_active_plugin = mock_engine_set_active_plugin
    # Ensure get_active_plugin returns what set_active_plugin sets
    mock_engine.get_active_plugin = lambda: mock_engine.current_plugin if hasattr(mock_engine, 'current_plugin') else None


    controller.set_active_fractal_plugin_and_redraw("Julia")
    assert controller.get_active_plugin_name_from_engine() == "Julia"
    assert abs(mock_engine.center_real - 0.0) < 1e-9 # Check if engine common params were updated from Julia's default view
    assert params_externally_updated_fired_count == 4
    assert active_plugin_ui_updated_for == "Julia"

    print("\nTesting render trigger with specific size...")
    # For this test, using a small specific size to check colored output format
    test_width_px, test_height_px = 20, 15
    controller.trigger_render(image_width_px=test_width_px, image_height_px=test_height_px)
    assert rendered_data_info['shape'] == (test_height_px, test_width_px, 4) # RGBA
    assert rendered_data_info['dtype'] == np.uint8 # Check for uint8
    assert mock_engine.image_width_px == test_width_px and mock_engine.image_height_px == test_height_px

    print("\nTesting render trigger without specific size (should use RenderArea size from MockMainWindow)...")
    mock_main_win.render_area = MockMainWindow.MockRenderArea() # Re-init to get its default size (20x15)
    controller.trigger_render()
    assert rendered_data_info['shape'] == (mock_main_win.render_area.height(), mock_main_win.render_area.width(), 4)
    assert "View: 20x15px" in last_status # Check if status reflects the render area size

    current_params = controller.get_current_parameters()
    print(f"\nTest: Current params from controller: {current_params}")
    assert current_params["max_iterations"] == 150

    print("\nAll basic controller tests passed.")
