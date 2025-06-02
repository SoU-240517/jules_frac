import numpy as np
from numba import jit # For coloring
import time # For __main__ test block, can be removed if test is removed

# Assuming these paths are correct from the project root
from src.app.plugins.plugin_manager import PluginManager
from src.app.plugins.base_plugin import FractalPlugin # For type hinting


@jit(nopython=True, cache=True, parallel=True) # This coloring function remains in FractalEngine
def _apply_grayscale_coloring(escape_times, max_iters):
    height, width = escape_times.shape
    colored_image = np.empty((height, width, 4), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            iters = escape_times[y, x]
            if iters == max_iters:
                colored_image[y, x, 0] = 0; colored_image[y, x, 1] = 0; colored_image[y, x, 2] = 0; colored_image[y, x, 3] = 255
            else:
                # Simple linear grayscale, darker for faster escape
                # norm_iters = iters / max_iters
                # color_val = int(255 * (1.0 - norm_iters)) # Brighter for faster escape
                color_val = int( (iters / max_iters) * 200 ) + 55 # Avoid pure black for escaped points, ensure visible
                color_val = max(0, min(255, color_val))
                colored_image[y, x, 0] = np.uint8(color_val); colored_image[y, x, 1] = np.uint8(color_val); colored_image[y, x, 2] = np.uint8(color_val); colored_image[y, x, 3] = 255
    return colored_image


class FractalEngine:
    def __init__(self, image_width_px=800, image_height_px=600, plugin_folder="src/app/plugins/fractals"):
        # Common fractal parameters
        self.max_iterations = 100
        self.center_real = -0.5
        self.center_imag = 0.0
        self.width = 3.0
        self.escape_radius = 2.0

        self.image_width_px = image_width_px if image_width_px > 0 else 800
        self.image_height_px = image_height_px if image_height_px > 0 else 600
        # Height of the complex plane view, calculated based on width and image aspect ratio
        self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width

        self.plugin_manager = PluginManager(plugin_folder_path=plugin_folder)
        self.current_plugin: FractalPlugin | None = None
        self.current_plugin_parameters: dict = {}

        # Set a default plugin
        available_plugin_names = self.get_available_plugin_names()
        if available_plugin_names:
            default_plugin_to_try = "Mandelbrot"
            if default_plugin_to_try in available_plugin_names:
                self.set_active_plugin(default_plugin_to_try)
                print(f"FractalEngine: Default plugin set to '{default_plugin_to_try}'.")
            else:
                # If Mandelbrot not found, set the first available plugin
                self.set_active_plugin(available_plugin_names[0])
                print(f"FractalEngine: Default plugin set to '{available_plugin_names[0]}'.")
        else:
            print("FractalEngine Warning: No fractal plugins found. Engine will not be able to compute fractals.")

    def update_image_size(self, image_width_px, image_height_px):
        self.image_width_px = image_width_px if image_width_px > 0 else self.image_width_px
        self.image_height_px = image_height_px if image_height_px > 0 else self.image_height_px
        self.update_aspect_ratio()

    def update_aspect_ratio(self):
        if self.image_width_px > 0 and self.image_height_px > 0 : # Ensure height_px is also positive
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else:
            self.height = self.width # Fallback, though should ideally not happen if sizes are validated

    def set_common_parameters(self, center_real, center_imag, width, max_iterations, escape_radius=None):
        self.center_real = center_real
        self.center_imag = center_imag
        self.width = width
        self.max_iterations = max_iterations
        if escape_radius is not None:
            self.escape_radius = escape_radius
        self.update_aspect_ratio() # Width change affects height
        print(f"FractalEngine: Common parameters updated - Center=({self.center_real:.4f}, {self.center_imag:.4f}), "
              f"Width={self.width:.3e}, Iter={self.max_iterations}, EscapeRadius={self.escape_radius}")

    def get_common_parameters(self) -> dict:
        return {
            'center_real': self.center_real,
            'center_imag': self.center_imag,
            'width': self.width,
            'height': self.height,
            'max_iterations': self.max_iterations,
            'escape_radius': self.escape_radius
        }

    def set_active_plugin(self, plugin_name: str) -> bool:
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if plugin:
            self.current_plugin = plugin
            default_view_params = plugin.get_default_view_parameters()
            # Apply plugin's default view parameters to the engine's common parameters
            self.center_real = default_view_params.get('center_real', self.center_real)
            self.center_imag = default_view_params.get('center_imag', self.center_imag)
            self.width = default_view_params.get('width', self.width)
            # max_iterations usually a global setting, but plugin could suggest one
            self.max_iterations = default_view_params.get('max_iterations', self.max_iterations)
            self.update_aspect_ratio() # Ensure height is correct after width change

            self.current_plugin_parameters.clear()
            for param_def in plugin.get_parameters_definition():
                self.current_plugin_parameters[param_def['name']] = param_def['default']

            print(f"FractalEngine: Active plugin set to '{plugin_name}'. View parameters updated from plugin defaults.")
            print(f"  New common params: Center=({self.center_real:.4f}, {self.center_imag:.4f}), Width={self.width:.3e}")
            print(f"  Plugin-specific params reset to defaults: {self.current_plugin_parameters}")
            return True
        else:
            print(f"FractalEngine Error: Plugin '{plugin_name}' not found.")
            return False

    def get_active_plugin(self) -> FractalPlugin | None:
        return self.current_plugin

    def get_available_plugin_names(self) -> list[str]:
        return [p.name for p in self.plugin_manager.get_available_plugins()]

    def get_current_plugin_parameter_definitions(self) -> list:
        return self.current_plugin.get_parameters_definition() if self.current_plugin else []

    def set_plugin_parameter(self, param_name: str, value: any):
        if self.current_plugin:
            if param_name in self.current_plugin_parameters:
                self.current_plugin_parameters[param_name] = value
                print(f"FractalEngine: Plugin parameter '{param_name}' for '{self.current_plugin.name}' set to '{value}'.")
            else:
                print(f"FractalEngine Warning: Parameter '{param_name}' not defined for plugin '{self.current_plugin.name}'.")
        else:
            print("FractalEngine Warning: No active plugin set. Cannot set plugin parameter.")

    def get_plugin_parameters(self) -> dict:
        return self.current_plugin_parameters.copy()

    def compute_current_fractal(self) -> np.ndarray | None:
        if not self.current_plugin:
            print("FractalEngine Error: No active fractal plugin is set.")
            return None

        common_params = self.get_common_parameters()

        print(f"FractalEngine: Computing with plugin '{self.current_plugin.name}'...")
        # print(f"  Common Params: {common_params}") # Verbose
        # print(f"  Plugin Params: {self.current_plugin_parameters}") # Verbose
        # print(f"  Image Size: {self.image_width_px}x{self.image_height_px}") # Verbose

        try:
            escape_times = self.current_plugin.compute_fractal(
                common_params,
                self.current_plugin_parameters,
                self.image_width_px,
                self.image_height_px
            )
            # print(f"FractalEngine: Computation complete with plugin '{self.current_plugin.name}'.") # Verbose
            return escape_times
        except Exception as e:
            print(f"FractalEngine Error: Exception during computation with plugin '{self.current_plugin.name}': {e}")
            return None

    def apply_basic_coloring(self, escape_times):
        if escape_times is None: # Handle cases where computation might have failed
            print("FractalEngine Warning: apply_basic_coloring received None for escape_times. Returning blank image.")
            h = self.image_height_px if self.image_height_px > 0 else 1
            w = self.image_width_px if self.image_width_px > 0 else 1
            return np.zeros((h, w, 4), dtype=np.uint8)
        # print(f"FractalEngine: Applying grayscale coloring to data of shape {escape_times.shape}.") # Verbose
        return _apply_grayscale_coloring(escape_times, self.max_iterations)

if __name__ == '__main__':
    print("FractalEngine (with PluginManager) Standalone Test")
    # This test assumes that PluginManager can find plugins,
    # especially 'MandelbrotPlugin' from src/app/plugins/fractals/mandelbrot_plugin.py

    engine = FractalEngine(image_width_px=80, image_height_px=60) # Small size for test

    available_plugins = engine.get_available_plugin_names()
    print(f"Available plugins: {available_plugins}")

    if not available_plugins:
        print("No plugins loaded. Ensure PluginManager's path is correct and plugins exist.")
        print(f"PluginManager is looking in: {engine.plugin_manager.plugin_folder.resolve()}")

    if "Mandelbrot" in available_plugins:
        print("\nTesting with Mandelbrot Plugin...")
        if not engine.current_plugin or engine.current_plugin.name != "Mandelbrot":
            engine.set_active_plugin("Mandelbrot") # Ensure it's active

        active_plugin = engine.get_active_plugin()
        if active_plugin:
            print(f"Active plugin: {active_plugin.name}")

            # Test common parameter setting
            engine.set_common_parameters(center_real=-0.75, center_imag=0.1, width=0.01, max_iterations=70)

            # Mandelbrot has no specific plugin parameters, so current_plugin_parameters should be empty
            print(f"Plugin parameters for Mandelbrot: {engine.get_plugin_parameters()}")
            assert not engine.get_plugin_parameters()

            print("Computing fractal data via Mandelbrot plugin...")
            start_time = time.perf_counter()
            fractal_data = engine.compute_current_fractal()
            compute_time = (time.perf_counter() - start_time) * 1000

            if fractal_data is not None:
                print(f"  Computation successful. Shape: {fractal_data.shape}. Time: {compute_time:.2f} ms")
                start_color_time = time.perf_counter()
                colored_data = engine.apply_basic_coloring(fractal_data)
                color_time = (time.perf_counter() - start_color_time) * 1000
                print(f"  Coloring successful. Shape: {colored_data.shape}. Time: {color_time:.2f} ms")

                # Optional: matplotlib display (if in an environment that supports it)
                # import matplotlib.pyplot as plt
                # plt.imshow(colored_data)
                # plt.title(f"{active_plugin.name} - Test")
                # plt.show()
            else:
                print("  Fractal computation failed.")
        else:
            print("  Could not activate Mandelbrot plugin for test.")
    else:
        print("\nMandelbrot plugin not found. Cannot run full test.")

    print("\nFractalEngine test finished.")
