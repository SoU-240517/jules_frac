import numpy as np
from numba import jit

from src.app.plugins.base_plugin import FractalPlugin

    # @jit(nopython=True, cache=True) # Numba JITを一時的に無効化
def _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq):
    z_real = 0.0
    z_imag = 0.0
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        mod_sq = z_real_sq + z_imag_sq
        if mod_sq > escape_radius_sq:
            return i, mod_sq # Return iterations and |Z|^2 upon escape

        new_z_imag = 2.0 * z_real * z_imag + c_imag
        z_real = z_real_sq - z_imag_sq + c_real
        z_imag = new_z_imag
    # Converged or max_iters reached, return 0.0 for |Z|^2 (or another indicator if needed)
    return max_iters, 0.0

    # @jit(nopython=True, cache=True, parallel=True) # Numba JITを一時的に無効化
def _compute_mandelbrot_grid_jit(width_px, height_px, min_x, max_x, min_y, max_y, max_iters, escape_radius_sq):
    iter_result = np.empty((height_px, width_px), dtype=np.int32)
    mod_sq_result = np.empty((height_px, width_px), dtype=np.float64) # For |Z|^2

    pixel_width_complex = (max_x - min_x) / width_px
    pixel_height_complex = (max_y - min_y) / height_px

    for y_idx in range(height_px):
        c_imag = min_y + y_idx * pixel_height_complex
        for x_idx in range(width_px):
            c_real = min_x + x_idx * pixel_width_complex
            iter_val, mod_sq_val = _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq)
            iter_result[y_idx, x_idx] = iter_val
            mod_sq_result[y_idx, x_idx] = mod_sq_val
    return iter_result, mod_sq_result


class MandelbrotPlugin(FractalPlugin):
    @property
    def name(self) -> str:
        return "Mandelbrot"

    def get_parameters_definition(self) -> list:
        return []

    def get_default_view_parameters(self) -> dict:
        return {
            'center_real': -0.5,
            'center_imag': 0.0,
            'width': 3.0,
        }

    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> dict:
        center_real = common_params['center_real']
        center_imag = common_params['center_imag']
        width = common_params['width']
        height = common_params['height']
        max_iterations = common_params['max_iterations']
        escape_radius = common_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        min_x = center_real - width / 2.0
        max_x = center_real + width / 2.0
        min_y = center_imag - height / 2.0
        max_y = center_imag + height / 2.0

        print(f"MandelbrotPlugin: Starting computation - Image: {image_width_px}x{image_height_px}px, "
              f"Complex area: Real ({min_x:.4f} to {max_x:.4f}), Imag ({min_y:.4f} to {max_y:.4f}), "
              f"Max Iter: {max_iterations}")

        iter_array, mod_sq_array = _compute_mandelbrot_grid_jit(
            image_width_px, image_height_px,
            min_x, max_x, min_y, max_y,
            max_iterations, escape_radius_sq
        )

        print(f"MandelbrotPlugin: Computation complete. Iterations shape: {iter_array.shape}, ModSq shape: {mod_sq_array.shape}")
        return {'iterations': iter_array, 'last_z_modulus_sq': mod_sq_array}

if __name__ == '__main__':
    plugin = MandelbrotPlugin()
    print(f"Plugin Name: {plugin.name}")
    print(f"Parameter Definitions: {plugin.get_parameters_definition()}")
    print(f"Default View Parameters: {plugin.get_default_view_parameters()}")

    test_common_params = {
        'center_real': -0.5,
        'center_imag': 0.0,
        'width': 3.0,
        'height': 2.0,
        'max_iterations': 60,
        'escape_radius': 2.0
    }
    test_plugin_params = {}

    img_width_test, img_height_test = 160, 120

    print(f"\nTesting compute_fractal ({img_width_test}x{img_height_test})...")
    fractal_result_data = plugin.compute_fractal(test_common_params, test_plugin_params, img_width_test, img_height_test)

    iter_result_array = fractal_result_data['iterations']
    mod_sq_result_array = fractal_result_data['last_z_modulus_sq']

    print(f"  Iterations array shape: {iter_result_array.shape}, dtype: {iter_result_array.dtype}")
    print(f"  |Z|^2 array shape: {mod_sq_result_array.shape}, dtype: {mod_sq_result_array.dtype}")

    center_y, center_x = img_height_test // 2, img_width_test // 2
    if iter_result_array[center_y, center_x] == test_common_params['max_iterations']:
        print(f"  Center point iteration check: PASSED (Value: {iter_result_array[center_y, center_x]})")
        print(f"  Center point |Z|^2 value: {mod_sq_result_array[center_y, center_x]}")
    else:
        print(f"  Center point iteration check: FAILED or NOT MAX_ITER (Value: {iter_result_array[center_y, center_x]})")

    try:
        import matplotlib.pyplot as plt
        plt.imshow(iter_result_array, cmap='magma', extent=(
            test_common_params['center_real'] - test_common_params['width']/2,
            test_common_params['center_real'] + test_common_params['width']/2,
            test_common_params['center_imag'] - test_common_params['height']/2,
            test_common_params['center_imag'] + test_common_params['height']/2
        ))
        plt.colorbar(label="Iterations")
        plt.title(f"{plugin.name} Iterations Test ({img_width_test}x{img_height_test})")
        plt.xlabel("Real")
        plt.ylabel("Imaginary")
        plt.show()
    except ImportError:
        print("  matplotlib not found. Skipping image display test.")

    print("\nMandelbrotPlugin test finished.")
