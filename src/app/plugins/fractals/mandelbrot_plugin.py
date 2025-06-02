import numpy as np
from numba import jit

# Try relative import for package context, fallback for direct script execution (e.g., tests)
try:
    from ..base_plugin import FractalPlugin
except ImportError:
    # This fallback assumes 'base_plugin.py' is in a discoverable path if run directly.
    # For reliable testing, ensure PYTHONPATH or project structure handles this.
    from base_plugin import FractalPlugin


# Numba JIT-compiled helper functions (formerly in FractalEngine)
# These are now local to this plugin file.
@jit(nopython=True, cache=True)
def _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq):
    z_real = 0.0
    z_imag = 0.0
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        if z_real_sq + z_imag_sq > escape_radius_sq:
            return i # Escaped
        # z_next_imag = 2.0 * z_real * z_imag + c_imag
        # z_next_real = z_real_sq - z_imag_sq + c_real
        # z_real, z_imag = z_next_real, z_next_imag
        # Correct update order for z_imag before z_real uses old z_real
        new_z_imag = 2.0 * z_real * z_imag + c_imag
        z_real = z_real_sq - z_imag_sq + c_real
        z_imag = new_z_imag
    return max_iters # Did not escape

@jit(nopython=True, cache=True, parallel=True)
def _compute_mandelbrot_grid_jit(width_px, height_px, min_x, max_x, min_y, max_y, max_iters, escape_radius_sq):
    result = np.empty((height_px, width_px), dtype=np.int32)
    pixel_width_complex = (max_x - min_x) / width_px
    pixel_height_complex = (max_y - min_y) / height_px

    for y_idx in range(height_px): # Numba may auto-parallelize this loop
        c_imag = min_y + y_idx * pixel_height_complex
        for x_idx in range(width_px):
            c_real = min_x + x_idx * pixel_width_complex
            result[y_idx, x_idx] = _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq)
    return result


class MandelbrotPlugin(FractalPlugin):
    """
    Mandelbrot set plugin.
    """

    @property
    def name(self) -> str:
        return "Mandelbrot"

    def get_parameters_definition(self) -> list:
        """Mandelbrot set has no additional user-adjustable parameters at this plugin level."""
        return []

    def get_default_view_parameters(self) -> dict:
        """Returns default view parameters suitable for the Mandelbrot set."""
        return {
            'center_real': -0.5,
            'center_imag': 0.0,
            'width': 3.0,
            # max_iterations is a common parameter, not defined here.
        }

    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> np.ndarray:
        """
        Computes the Mandelbrot set and returns a NumPy array of escape times.
        plugin_params is not used in this plugin.
        """
        center_real = common_params['center_real']
        center_imag = common_params['center_imag']
        width = common_params['width']
        # Height in complex plane is provided by common_params, calculated by FractalEngine based on aspect ratio
        height = common_params['height']
        max_iterations = common_params['max_iterations']
        # Use .get() for escape_radius to provide a default if not specified in common_params
        escape_radius = common_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        min_x = center_real - width / 2.0
        max_x = center_real + width / 2.0
        min_y = center_imag - height / 2.0 # Assuming y-axis of complex plane points upwards
        max_y = center_imag + height / 2.0

        print(f"MandelbrotPlugin: Starting computation - Image: {image_width_px}x{image_height_px}px, "
              f"Complex area: Real ({min_x:.4f} to {max_x:.4f}), Imag ({min_y:.4f} to {max_y:.4f}), "
              f"Max Iter: {max_iterations}")

        mandelbrot_data = _compute_mandelbrot_grid_jit(
            image_width_px, image_height_px,
            min_x, max_x, min_y, max_y,
            max_iterations, escape_radius_sq
        )

        print(f"MandelbrotPlugin: Computation complete. Output data shape: {mandelbrot_data.shape}")
        return mandelbrot_data

if __name__ == '__main__':
    # Standalone test for MandelbrotPlugin
    plugin = MandelbrotPlugin()
    print(f"Plugin Name: {plugin.name}")
    print(f"Parameter Definitions: {plugin.get_parameters_definition()}")
    print(f"Default View Parameters: {plugin.get_default_view_parameters()}")

    test_common_params = {
        'center_real': -0.5,
        'center_imag': 0.0,
        'width': 3.0,
        'height': 2.0, # Assuming width 3.0, aspect 800/600 -> height = 3.0 * (600/800) = 2.25. For test, use 2.0.
        'max_iterations': 60, # Reduced for faster test
        'escape_radius': 2.0
    }
    # Mandelbrot plugin has no specific parameters
    test_plugin_params = {}

    img_width_test, img_height_test = 160, 120 # Small size for quick test

    print(f"\nTesting compute_fractal ({img_width_test}x{img_height_test})...")
    result = plugin.compute_fractal(test_common_params, test_plugin_params, img_width_test, img_height_test)
    print(f"  Result shape: {result.shape}, dtype: {result.dtype}")

    # Basic check: center point of standard Mandelbrot set (-0.5, 0) should be in the set (max_iterations)
    # This requires precise mapping. For a simple check, just ensure it runs.
    if result[img_height_test // 2, img_width_test // 2] == test_common_params['max_iterations']:
        print(f"  Center point check: PASSED (Value: {result[img_height_test // 2, img_width_test // 2]})")
    else:
        print(f"  Center point check: FAILED or NOT MAX_ITER (Value: {result[img_height_test // 2, img_width_test // 2]}) - This might be ok for low iter counts or off-center views.")

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
        plt.title(f"{plugin.name} Test ({img_width_test}x{img_height_test})")
        plt.xlabel("Real")
        plt.ylabel("Imaginary")
        plt.show()
    except ImportError:
        print("  matplotlib not found. Skipping image display test.")

    print("\nMandelbrotPlugin test finished.")
