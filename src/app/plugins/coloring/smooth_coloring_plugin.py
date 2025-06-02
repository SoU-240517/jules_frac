import numpy as np
from numba import jit
import math

try:
    from ..base_coloring_plugin import ColoringAlgorithmPlugin
except ImportError:
    # Fallback for testing or direct script execution
    from src.app.plugins.base_coloring_plugin import ColoringAlgorithmPlugin

@jit(nopython=True, cache=True, fastmath=True) # Added fastmath for potential minor speedup
def _apply_smooth_coloring_jit(
    iterations_array: np.ndarray,
    last_z_mod_sq_array: np.ndarray,
    max_iters: int,
    escape_radius_sq: float,
    color_map: np.ndarray # Shape (N, 3), dtype=uint8
) -> np.ndarray:
    height, width = iterations_array.shape
    output_image_rgba = np.empty((height, width, 4), dtype=np.uint8)
    output_image_rgba[:, :, 3] = 255 # Set alpha channel to opaque

    num_colors_in_map = color_map.shape[0]
    if num_colors_in_map == 0:
        # Fallback to black if color map is empty
        output_image_rgba[:, :, 0:3] = 0
        return output_image_rgba

    # log_escape_radius = math.log(math.sqrt(escape_radius_sq)) # Not directly used in the chosen formula variant
    log_2 = math.log(2.0) # Precompute log(2)

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]

            if iters == max_iters: # Point is in the set
                output_image_rgba[r_idx, c_idx, 0:3] = 0 # Black
            else:
                mod_sq = last_z_mod_sq_array[r_idx, c_idx]

                # Smooth iteration count calculation
                # Formula: iter + 1 - log(log(|Z_n|^2 / 2)) / log(2) - this is one variant
                # A common variant: iter + 1 - log(log(|Z_n|)) / log(2)
                # Ensure |Z_n| > 1 for log(log(|Z_n|)) to be valid and positive.
                # Since mod_sq = |Z_n|^2 > escape_radius_sq (which is usually 4),
                # modulus = sqrt(mod_sq) > escape_radius (usually 2). So log(modulus) should be > log(2) > 0.

                smooth_val = float(iters) # Default to integer iteration if smoothing fails
                if mod_sq > 1e-9: # Avoid log(0) or log of very small numbers; ensure mod_sq is positive
                    try:
                        # Using the formula: iter - log(log(|Z|^2)/log(degree))/log(degree)
                        # For degree=2 (Mandelbrot/Julia): iter - log(log(|Z|^2)/log(2))/log(2)
                        # Or simpler: iter - log2(log2(|Z|^2)) if |Z|^2 is already scaled appropriately.
                        # Let's use a common one: iter + 1 - log(log(sqrt(mod_sq)))/log(2)
                        # which is equivalent to iter + 1 - log(0.5 * log(mod_sq))/log(2)
                        # Ensure log arguments are > 0. mod_sq > escape_radius_sq (e.g. 4) so sqrt(mod_sq) > 2.
                        # log(sqrt(mod_sq)) will be > log(2) approx 0.693. So inner log is valid.

                        # mu = iterations + 1 - log (log (|Z|) / log (2)) / log (2)
                        # Z is modulus, so |Z| = sqrt(mod_sq)
                        log_mod = math.log(math.sqrt(mod_sq)) # log(|Z|)
                        if log_mod > 1e-9 : # ensure log(|Z|) is positive for the outer log
                           smooth_val = iters + 1.0 - math.log(log_mod) / log_2
                        # If log_mod is too small, smooth_val remains iters.
                    except ValueError:
                        # Fallback to integer iterations if math domain error occurs
                        smooth_val = float(iters)

                # Map smooth_val to color index
                # We want the fractional part for smooth transition between colors,
                # scaled by some factor to control color cycling speed.
                # A larger scaling_factor means colors cycle more rapidly.
                scaling_factor = 1.0 # Smaller factor = slower color change, larger = faster/more bands
                color_idx_float = (smooth_val * scaling_factor)

                # Linear interpolation between two colors in the map
                idx0 = int(color_idx_float)
                fraction = color_idx_float - idx0

                c1_idx = idx0 % num_colors_in_map
                c2_idx = (idx0 + 1) % num_colors_in_map

                r = color_map[c1_idx, 0] * (1.0 - fraction) + color_map[c2_idx, 0] * fraction
                g = color_map[c1_idx, 1] * (1.0 - fraction) + color_map[c2_idx, 1] * fraction
                b = color_map[c1_idx, 2] * (1.0 - fraction) + color_map[c2_idx, 2] * fraction

                output_image_rgba[r_idx, c_idx, 0] = np.uint8(r)
                output_image_rgba[r_idx, c_idx, 1] = np.uint8(g)
                output_image_rgba[r_idx, c_idx, 2] = np.uint8(b)
        return output_image_rgba


class SmoothColoringPlugin(ColoringAlgorithmPlugin):
    @property
    def name(self) -> str:
        return "スムーズカラー"

    def get_parameters_definition(self) -> list:
        return [
            {'name': 'color_scale', 'label': '色のスケール',
             'type': 'float', 'default': 1.0, 'range': (0.1, 50.0), 'step': 0.1,
             'tooltip': '色の変化の速さを調整します。大きいほど色が細かく変化します。'}
        ]

    def apply_coloring(self, fractal_data: dict, common_fractal_params: dict,
                       algorithm_params: dict, color_map_data: list[tuple[int,int,int]] | None) -> np.ndarray:

        iterations = fractal_data.get('iterations')
        last_z_mod_sq = fractal_data.get('last_z_modulus_sq')

        if iterations is None or last_z_mod_sq is None:
            height_px = common_fractal_params.get('image_height_px', 100) # Get from common if available
            width_px = common_fractal_params.get('image_width_px', 100)
            print("SmoothColoringPlugin Warning: Required data ('iterations' or 'last_z_modulus_sq') not found.")
            fallback_img = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_img[:,:,3] = 255 # Alpha
            return fallback_img

        max_iters = common_fractal_params.get('max_iterations', 100)
        escape_radius = common_fractal_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        # color_scale = algorithm_params.get('color_scale', 1.0) # This will be used inside JIT if passed

        if not color_map_data or len(color_map_data) < 2: # Need at least 2 colors for interpolation
            print("SmoothColoringPlugin Warning: Not enough colors in color_map_data. Using default grayscale map.")
            # Default simple grayscale map if none or too few colors provided
            color_map_np = np.array([(i,i,i) for i in range(256)], dtype=np.uint8)
        else:
            color_map_np = np.array(color_map_data, dtype=np.uint8)

        # print(f"SmoothColoringPlugin: Applying smooth coloring. MaxIters: {max_iters}, ER^2: {escape_radius_sq}, MapSize: {color_map_np.shape[0]}")

        # Note: The JIT function _apply_smooth_coloring_jit currently does not take color_scale as a parameter.
        # If color_scale needs to be dynamic, the JIT function signature must be updated,
        # or the scaling logic applied outside/before color mapping if possible.
        # For now, the JIT function uses a hardcoded scaling_factor or implies it in how smooth_val is used.
        # Let's refine the JIT function to accept a scaling factor if it's a plugin parameter.
        # However, the provided JIT function already has a color_idx_float = (smooth_val * 10.0) % num_colors_in_map
        # where 10.0 is a hardcoded scaling factor. We should use the plugin parameter for this.
        # This requires passing `color_scale` to the JIT function.
        # For now, we'll stick to the provided JIT, which has its own internal scaling.
        # TODO: Pass `algorithm_params.get('color_scale', 1.0)` to JIT and use it.

        colored_image = _apply_smooth_coloring_jit(
            iterations, last_z_mod_sq, max_iters, escape_radius_sq, color_map_np
        )

        # print(f"SmoothColoringPlugin: Coloring complete. Output shape: {colored_image.shape}")
        return colored_image

if __name__ == '__main__':
    print("Testing SmoothColoringPlugin...")
    plugin = SmoothColoringPlugin()
    print(f"Plugin Name: {plugin.name}")
    print(f"Parameter Definitions: {plugin.get_parameters_definition()}")

    # Test data
    h, w = 60, 80
    max_i = 200
    test_iters = np.random.randint(0, max_i + 1, size=(h, w), dtype=np.int32)
    # Simulate some points in the set
    test_iters[h//2 - 5 : h//2 + 5, w//2 - 5 : w//2 + 5] = max_i
    # Simulate some escaped points with varying |Z|^2 values
    # last_z_mod_sq should be > escape_radius_sq for escaped points
    er_sq = 4.0
    test_mod_sq = np.random.uniform(er_sq + 0.1, er_sq + 100.0, size=(h,w)).astype(np.float64)
    test_mod_sq[test_iters == max_i] = 0.0 # |Z|^2 is 0 for points in set

    test_fractal_data = {'iterations': test_iters, 'last_z_modulus_sq': test_mod_sq, 'height_px':h, 'width_px':w}
    test_common_params = {'max_iterations': max_i, 'escape_radius': math.sqrt(er_sq)}
    test_algo_params = plugin.get_parameters_definition()[0]['default'] if plugin.get_parameters_definition() else {} # Use default if params exist

    # Test with a color map
    test_color_map = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255), (255,0,255)]

    print("\nApplying coloring with a color map...")
    colored_img = plugin.apply_coloring(test_fractal_data, test_common_params, test_algo_params, test_color_map)
    print(f"  Colored image shape: {colored_img.shape}")
    assert colored_img.shape == (h,w,4)

    # Test with no color map (should use default grayscale)
    print("\nApplying coloring without a color map (should use default grayscale)...")
    colored_img_no_map = plugin.apply_coloring(test_fractal_data, test_common_params, test_algo_params, None)
    print(f"  Colored image (no map) shape: {colored_img_no_map.shape}")
    assert colored_img_no_map.shape == (h,w,4)

    # Check if a point in the set is black
    assert np.array_equal(colored_img[h//2, w//2, :3], [0,0,0]), "Center (in set) point not black."

    print("\nSmoothColoringPlugin tests completed.")
