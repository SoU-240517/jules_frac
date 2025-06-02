import numpy as np
from numba import jit

try:
    from ..base_plugin import FractalPlugin
except ImportError:
    # This fallback assumes 'base_plugin.py' is in a discoverable path if run directly,
    # e.g. if sys.path is modified or this script is in the same dir as base_plugin.py
    from base_plugin import FractalPlugin

# Numba JIT-compiled helper functions for Julia Set
@jit(nopython=True, cache=True)
def _calculate_julia_point_jit(z_real_start, z_imag_start, c_real_const, c_imag_const, max_iters, escape_radius_sq):
    z_real = z_real_start
    z_imag = z_imag_start
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        if z_real_sq + z_imag_sq > escape_radius_sq:
            return i # Escaped

        # Z_new = Z_old^2 + C
        new_z_imag = 2.0 * z_real * z_imag + c_imag_const
        z_real = z_real_sq - z_imag_sq + c_real_const
        z_imag = new_z_imag
    return max_iters # Did not escape

@jit(nopython=True, cache=True, parallel=True)
def _compute_julia_grid_jit(width_px, height_px, min_x, max_x, min_y, max_y,
                            c_real_const, c_imag_const, max_iters, escape_radius_sq):
    result = np.empty((height_px, width_px), dtype=np.int32)
    pixel_width_complex = (max_x - min_x) / width_px
    pixel_height_complex = (max_y - min_y) / height_px

    for y_idx in range(height_px): # Numba may auto-parallelize this loop
        z_imag_start = min_y + y_idx * pixel_height_complex # Z0's imaginary part
        for x_idx in range(width_px):
            z_real_start = min_x + x_idx * pixel_width_complex # Z0's real part
            result[y_idx, x_idx] = _calculate_julia_point_jit(
                z_real_start, z_imag_start,
                c_real_const, c_imag_const,
                max_iters, escape_radius_sq
            )
    return result


class JuliaPlugin(FractalPlugin):
    """
    Julia set plugin.
    """

    @property
    def name(self) -> str:
        return "Julia"

    def get_parameters_definition(self) -> list:
        """Returns definitions for Julia set's C constant (c_real, c_imag)."""
        return [
            {
                'name': 'c_real',
                'label': 'C (実部)',
                'type': 'float',
                'default': -0.745,
                'range': (-2.0, 2.0),
                'step': 0.001,
                'tooltip': 'Julia定数Cの実部'
            },
            {
                'name': 'c_imag',
                'label': 'C (虚部)',
                'type': 'float',
                'default': 0.113,
                'range': (-2.0, 2.0),
                'step': 0.001,
                'tooltip': 'Julia定数Cの虚部'
            }
        ]

    def get_default_view_parameters(self) -> dict:
        """Returns default view parameters suitable for typical Julia sets."""
        return {
            'center_real': 0.0,
            'center_imag': 0.0,
            'width': 3.0,
            # max_iterations is a common parameter
        }

    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> np.ndarray:
        """
        Computes the Julia set for a given C constant and view parameters.
        """
        center_real = common_params['center_real']
        center_imag = common_params['center_imag']
        width = common_params['width']
        height = common_params['height'] # Calculated by FractalEngine based on aspect ratio
        max_iterations = common_params['max_iterations']
        escape_radius = common_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        # Get C constant from plugin-specific parameters
        # Provide default values if not found, though PluginManager should ensure defaults are set.
        c_real_const = plugin_params.get('c_real', self.get_parameters_definition()[0]['default'])
        c_imag_const = plugin_params.get('c_imag', self.get_parameters_definition()[1]['default'])

        min_x = center_real - width / 2.0
        max_x = center_real + width / 2.0
        min_y = center_imag - height / 2.0 # Assuming y-axis of complex plane points upwards
        max_y = center_imag + height / 2.0

        print(f"JuliaPlugin: Starting computation - C=({c_real_const:.4f} + {c_imag_const:.4f}i), "
              f"Image: {image_width_px}x{image_height_px}px, "
              f"Complex Area: Real ({min_x:.4f} to {max_x:.4f}), Imag ({min_y:.4f} to {max_y:.4f}), "
              f"Max Iter: {max_iterations}")

        julia_data = _compute_julia_grid_jit(
            image_width_px, image_height_px,
            min_x, max_x, min_y, max_y,
            c_real_const, c_imag_const,
            max_iterations, escape_radius_sq
        )

        print(f"JuliaPlugin: Computation complete. Output data shape: {julia_data.shape}")
        return julia_data

    def get_presets(self) -> dict | None:
        """Provides some well-known C constants for generating Julia sets."""
        return {
            "Classic Beauty": {"c_real": -0.745, "c_imag": 0.113},
            "Feigenbaum Point": {"c_real": -1.401155, "c_imag": 0.0},
            "Seahorse": {"c_real": -0.75, "c_imag": 0.1}, # Often similar to Mandelbrot seahorse valley
            "Dragon Tail": {"c_real": -0.8, "c_imag": 0.156},
            "Electric Eels": {"c_real": -0.162, "c_imag": 1.04},
            "Snowflakes": {"c_real": 0.285, "c_imag": 0.01},
            "Spiral": {"c_real": -0.778, "c_imag": -0.136},
        }

if __name__ == '__main__':
    plugin = JuliaPlugin()
    print(f"Plugin Name: {plugin.name}")
    param_defs = plugin.get_parameters_definition()
    print(f"Parameter Definitions: {param_defs}")
    print(f"Default View Parameters: {plugin.get_default_view_parameters()}")

    presets = plugin.get_presets()
    print(f"Presets Available: {list(presets.keys()) if presets else 'None'}")

    test_common_params = {
        'center_real': 0.0,
        'center_imag': 0.0,
        'width': 3.0,
        'height': 2.25, # Assuming 4:3 aspect for width 3.0
        'max_iterations': 150, # Increased for better detail
        'escape_radius': 2.0
    }

    # Use the first preset for testing, or defaults if no presets
    test_plugin_params = {}
    if presets:
        first_preset_name = list(presets.keys())[0]
        test_plugin_params = presets[first_preset_name]
        print(f"\nUsing preset '{first_preset_name}' for computation test: {test_plugin_params}")
    else:
        # Fallback to default values from parameter definitions
        for p_def in param_defs:
            test_plugin_params[p_def['name']] = p_def['default']
        print(f"\nUsing default plugin parameters for computation test: {test_plugin_params}")

    img_width_test, img_height_test = 160, 120 # Small size for quick test

    print(f"Testing compute_fractal ({img_width_test}x{img_height_test})...")
    result = plugin.compute_fractal(test_common_params, test_plugin_params, img_width_test, img_height_test)
    print(f"  Result shape: {result.shape}, dtype: {result.dtype}")

    # Optional: Display using matplotlib if available
    try:
        import matplotlib.pyplot as plt
        plt.imshow(result, cmap='magma', extent=(
            test_common_params['center_real'] - test_common_params['width']/2,
            test_common_params['center_real'] + test_common_params['width']/2,
            test_common_params['center_imag'] - test_common_params['height']/2,
            test_common_params['center_imag'] + test_common_params['height']/2
        ))
        plt.colorbar(label="Iterations")
        c_text = f"C=({test_plugin_params.get('c_real',0):.3f} + {test_plugin_params.get('c_imag',0):.3f}i)"
        plt.title(f"{plugin.name} Test ({img_width_test}x{img_height_test})\n{c_text}")
        plt.xlabel("Real")
        plt.ylabel("Imaginary")
        plt.show()
    except ImportError:
        print("  matplotlib not found. Skipping image display test.")

    print("\nJuliaPlugin test finished.")
