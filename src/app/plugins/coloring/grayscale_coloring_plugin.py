import numpy as np
from numba import jit

try:
    from ..base_coloring_plugin import ColoringAlgorithmPlugin
except ImportError:
    # Fallback for testing or direct script execution
    # This assumes 'base_coloring_plugin.py' might be in a discoverable path.
    # For robust project structure, ensure PYTHONPATH is set correctly or use absolute imports.
    from src.app.plugins.base_coloring_plugin import ColoringAlgorithmPlugin


# Numba JIT-compiled helper function (formerly in FractalEngine or similar)
@jit(nopython=True)
def _apply_grayscale_coloring_jit(iterations_array: np.ndarray, max_iters: int) -> np.ndarray:
    height, width = iterations_array.shape
    colored_image_rgba = np.empty((height, width, 4), dtype=np.uint8)

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]
            if iters == max_iters:  # Point is in the set
                colored_image_rgba[r_idx, c_idx, 0] = 0  # R
                colored_image_rgba[r_idx, c_idx, 1] = 0  # G
                colored_image_rgba[r_idx, c_idx, 2] = 0  # B
            else: # Point escaped
                # Linear grayscale: 0 iterations -> black, max_iters-1 -> white (or near white)
                # To make faster escaping points darker:
                gray_value = int((iters / max_iters) * 255)
                # To make faster escaping points brighter (often preferred for detail):
                # gray_value = int((1.0 - (iters / max_iters)) * 255)

                gray_value = max(0, min(255, gray_value)) # Clamp value

                colored_image_rgba[r_idx, c_idx, 0] = np.uint8(gray_value)
                colored_image_rgba[r_idx, c_idx, 1] = np.uint8(gray_value)
                colored_image_rgba[r_idx, c_idx, 2] = np.uint8(gray_value)
            colored_image_rgba[r_idx, c_idx, 3] = 255  # Alpha channel (fully opaque)
    return colored_image_rgba


class GrayscaleColoringPlugin(ColoringAlgorithmPlugin):
    """
    A simple coloring plugin that applies grayscale based on escape times.
    """

    @property
    def name(self) -> str:
        return "グレースケール (標準)"

    def get_parameters_definition(self) -> list:
        """This algorithm has no specific adjustable parameters."""
        return []

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict,  # Not used by this plugin
        color_map_data: list[tuple[int, int, int]] | None # Not used by this plugin
    ) -> np.ndarray:
        """
        Applies grayscale coloring based on the iteration counts.
        """
        iterations = fractal_data.get('iterations')
        if iterations is None:
            # Fallback: if 'iterations' data is missing, return a black image.
            # This should ideally be handled by the caller ensuring valid fractal_data.
            height_px = fractal_data.get('height_px', 100) # Attempt to get dimensions
            width_px = fractal_data.get('width_px', 100)
            print("GrayscaleColoringPlugin Warning: 'iterations' data not found. Returning black image.")
            fallback_image = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_image[:, :, 3] = 255 # Set alpha to opaque
            return fallback_image

        max_iters = common_fractal_params.get('max_iterations', 100) # Default if not provided

        # print(f"GrayscaleColoringPlugin: Applying grayscale coloring. Max iterations: {max_iters}.") # Verbose

        colored_image = _apply_grayscale_coloring_jit(iterations, max_iters)

        # print(f"GrayscaleColoringPlugin: Coloring complete. Output shape: {colored_image.shape}") # Verbose
        return colored_image

if __name__ == '__main__':
    print("Testing GrayscaleColoringPlugin...")
    plugin = GrayscaleColoringPlugin()
    print(f"Plugin Name: {plugin.name}")
    print(f"Parameter Definitions: {plugin.get_parameters_definition()}")

    # Test data
    test_iterations_data = np.array([
        [50, 10, 0],   # Row 0
        [5, 50, 20],   # Row 1
        [0, 15, 50]    # Row 2
    ], dtype=np.int32)

    # Add height/width to fractal_data for the fallback case in apply_coloring
    test_fractal_data = {'iterations': test_iterations_data,
                         'height_px': test_iterations_data.shape[0],
                         'width_px': test_iterations_data.shape[1]}

    test_common_fractal_params = {'max_iterations': 50}
    test_algorithm_params = {} # No specific params for this plugin
    test_color_map = None      # This plugin does not use a color map

    print("\nRunning apply_coloring test...")
    result_image_data = plugin.apply_coloring(
        test_fractal_data,
        test_common_fractal_params,
        test_algorithm_params,
        test_color_map
    )
    print(f"  Generated image shape: {result_image_data.shape}")
    assert result_image_data.shape == (3, 3, 4) # Height, Width, RGBA

    print("  Generated image data (RGB components):")
    expected_values = {
        (0,0): int(50/50*255), # iter=50 (max_iters) -> black (0,0,0) due to 'if iters == max_iters'
        (0,1): int(10/50*255), # iter=10 -> gray value
        (0,2): int(0/50*255),  # iter=0 -> gray value (black)
        (1,0): int(5/50*255),
        (1,1): int(50/50*255), # black
        (1,2): int(20/50*255),
        (2,0): int(0/50*255),  # black
        (2,1): int(15/50*255),
        (2,2): int(50/50*255)  # black
    }

    for r in range(test_iterations_data.shape[0]):
        for c in range(test_iterations_data.shape[1]):
            iter_val = test_iterations_data[r,c]
            rgb_val = result_image_data[r,c,:3]
            alpha_val = result_image_data[r,c,3]

            if iter_val == test_common_fractal_params['max_iterations']:
                expected_rgb = np.array([0,0,0], dtype=np.uint8)
            else:
                val = int((iter_val / test_common_fractal_params['max_iterations']) * 255)
                val = max(0, min(255, val))
                expected_rgb = np.array([val, val, val], dtype=np.uint8)

            print(f"    Pixel({r},{c}): Iter={iter_val}, RGBA={result_image_data[r,c]}, ExpectedRGB={expected_rgb}")
            assert np.array_equal(rgb_val, expected_rgb), f"Mismatch at ({r},{c})"
            assert alpha_val == 255, f"Alpha incorrect at ({r},{c})"

    print("  All pixel checks passed.")
    print("\nGrayscaleColoringPlugin tests completed.")
