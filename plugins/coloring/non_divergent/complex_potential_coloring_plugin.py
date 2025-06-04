import numpy as np
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
try:
    from logger.custom_logger import CustomLogger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    CustomLogger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg) if level == "INFO" else logging.warning(msg) if level == "WARNING" else logging.error(msg)})()

from numba import jit

logger = CustomLogger()

# @jit(nopython=True, cache=True)
def _calculate_potentials_jit(
    iterations: np.ndarray,
    last_zn_values: np.ndarray, # complex
    max_iterations: int
) -> tuple[np.ndarray, float, float, bool]:
    height, width = iterations.shape
    potentials = np.full((height, width), np.nan, dtype=np.float64)
    min_p = np.inf
    max_p = -np.inf
    has_valid = False

    for r in range(height):
        for c in range(width):
            if iterations[r, c] == max_iterations:
                abs_zn = np.abs(last_zn_values[r, c])
                if abs_zn > 1e-9: # Avoid log(0)
                    potential_val = np.log(abs_zn)
                    potentials[r, c] = potential_val
                    min_p = min(min_p, potential_val)
                    max_p = max(max_p, potential_val)
                    has_valid = True
                else: # Handle |Z_n| ~ 0
                    potentials[r, c] = -np.inf # Mark as very low potential
                    min_p = min(min_p, -np.inf) # This will make min_p -np.inf
                    has_valid = True # It's a valid point to color, even if its potential is effectively minimal
    return potentials, min_p, max_p, has_valid

# @jit(nopython=True, cache=True)
def _normalize_and_color_jit(
    potentials: np.ndarray,
    min_potential_norm: float, # Min potential to use for normalization
    max_potential_norm: float, # Max potential to use for normalization
    img_array_rgb: np.ndarray, # HxWx3 uint8 array
    color_map_array: np.ndarray | None, # Numba needs optional type or actual None
    use_color_map: bool,
    default_outside_color_r: np.uint8, # Make sure types are specific for Numba
    default_outside_color_g: np.uint8,
    default_outside_color_b: np.uint8
) -> None:
    height, width = potentials.shape
    potential_range_norm = max_potential_norm - min_potential_norm
    if potential_range_norm < 1e-9:
        potential_range_norm = 1e-9

    for r in range(height):
        for c in range(width):
            current_potential = potentials[r,c]
            if np.isnan(current_potential): # Points that escaped
                img_array_rgb[r,c,0] = default_outside_color_r
                img_array_rgb[r,c,1] = default_outside_color_g
                img_array_rgb[r,c,2] = default_outside_color_b
            else:
                norm_potential: float
                if current_potential == -np.inf:
                    norm_potential = 0.0
                else:
                    norm_potential = (current_potential - min_potential_norm) / potential_range_norm

                norm_potential = max(0.0, min(1.0, norm_potential))

                if not use_color_map:
                    gray_val = np.uint8(norm_potential * 255)
                    img_array_rgb[r,c,0] = gray_val
                    img_array_rgb[r,c,1] = gray_val
                    img_array_rgb[r,c,2] = gray_val
                else:
                    if color_map_array is not None and color_map_array.shape[0] > 0:
                        num_colors = color_map_array.shape[0]
                        color_idx = int(norm_potential * (num_colors - 1))
                        color_idx = max(0, min(color_idx, num_colors - 1))
                        img_array_rgb[r,c,0] = color_map_array[color_idx, 0]
                        img_array_rgb[r,c,1] = color_map_array[color_idx, 1]
                        img_array_rgb[r,c,2] = color_map_array[color_idx, 2]
                    else: # Fallback if color map is empty or None despite use_color_map=True
                        img_array_rgb[r,c,0] = 0; img_array_rgb[r,c,1] = 0; img_array_rgb[r,c,2] = 0;


class ComplexPotentialColoringPlugin(ColoringAlgorithmPlugin):
    DEFAULT_OUTSIDE_COLOR = (np.uint8(0), np.uint8(0), np.uint8(0)) # Black

    @property
    def name(self) -> str:
        return "複素ポテンシャル"

    @property
    def target_type(self) -> str:
        return "non_divergent"

    def get_parameters_definition(self) -> list:
        return []

    def apply_coloring(
        self, fractal_data: dict, common_fractal_params: dict,
        algorithm_params: dict, color_map_data: list[tuple[int, int, int]] | None
    ) -> np.ndarray:
        iterations = fractal_data.get('iterations')
        last_zn_values = fractal_data.get('last_zn_values')

        height_param = common_fractal_params.get('height')
        width_param = common_fractal_params.get('width')

        if iterations is None or last_zn_values is None:
            logger.log("apply_coloring: 'iterations' or 'last_zn_values' data not found.", level="ERROR")
            h = height_param if height_param is not None else 100
            w = width_param if width_param is not None else 100
            img = np.zeros((h, w, 4), dtype=np.uint8)
            img[:,:,0] = self.DEFAULT_OUTSIDE_COLOR[0]
            img[:,:,1] = self.DEFAULT_OUTSIDE_COLOR[1]
            img[:,:,2] = self.DEFAULT_OUTSIDE_COLOR[2]
            img[:,:,3] = 255
            return img

        height, width = iterations.shape
        if (height_param is not None and width_param is not None and \
            ((height_param, width_param) != (height, width) or last_zn_values.shape != (height, width))):
            logger.log(f"apply_coloring: Shape mismatch or last_zn_values shape error. Iterations: {iterations.shape}, LastZn: {last_zn_values.shape}, Params: ({height_param},{width_param}). Using shape from iterations.", level="WARNING")
            if last_zn_values.shape != (height,width): # Attempt to gracefully handle or error
                 logger.log("apply_coloring: last_zn_values shape does not match iterations shape. Returning error image.", level="ERROR")
                 err_img = np.zeros((height, width, 4), dtype=np.uint8); err_img[:,:,0]=255; err_img[:,:,3]=255; return err_img


        max_iterations = common_fractal_params.get('max_iterations', 100)
        img_array = np.zeros((height, width, 4), dtype=np.uint8)
        img_array[:, :, 3] = 255
        img_array_rgb = img_array[:,:,:3]

        potentials, min_p_raw, max_p_raw, has_valid = _calculate_potentials_jit(
            iterations, last_zn_values, max_iterations
        )

        if not has_valid:
            logger.log("apply_coloring: No valid potential values found. Outputting default outside color.", level="WARNING")
            for r_idx in range(height):
                for c_idx in range(width):
                    img_array_rgb[r_idx, c_idx, 0] = self.DEFAULT_OUTSIDE_COLOR[0]
                    img_array_rgb[r_idx, c_idx, 1] = self.DEFAULT_OUTSIDE_COLOR[1]
                    img_array_rgb[r_idx, c_idx, 2] = self.DEFAULT_OUTSIDE_COLOR[2]
            return img_array

        min_potential_for_norm = min_p_raw
        max_potential_for_norm = max_p_raw

        if min_p_raw == -np.inf:
            finite_potentials = potentials[np.isfinite(potentials)]
            if finite_potentials.size > 0:
                min_potential_for_norm = np.min(finite_potentials) - 1.0
            else:
                min_potential_for_norm = -1.0
            if max_p_raw == -np.inf:
                 max_potential_for_norm = 0.0

        if max_potential_for_norm <= min_potential_for_norm:
             max_potential_for_norm = min_potential_for_norm + 1.0

        use_color_map_flag = True
        color_map_np_array = None
        if not color_map_data or len(color_map_data) == 0:
            use_color_map_flag = False
        else:
            try:
                color_map_np_array = np.array(color_map_data, dtype=np.uint8)
                if color_map_np_array.ndim != 2 or color_map_np_array.shape[1] != 3:
                    logger.log(f"apply_coloring: Invalid color_map_data. Expected Nx3. Got {color_map_np_array.shape}. Using grayscale.", level="ERROR")
                    use_color_map_flag = False; color_map_np_array = None
            except Exception as e:
                logger.log(f"apply_coloring: Error converting color_map to NumPy array: {e}. Using grayscale.", level="ERROR")
                use_color_map_flag = False; color_map_np_array = None

        _normalize_and_color_jit(
            potentials, min_potential_for_norm, max_potential_for_norm,
            img_array_rgb, color_map_np_array, use_color_map_flag,
            self.DEFAULT_OUTSIDE_COLOR[0], self.DEFAULT_OUTSIDE_COLOR[1], self.DEFAULT_OUTSIDE_COLOR[2]
        )
        return img_array

if __name__ == '__main__':
    import sys
    from pathlib import Path
    project_root_candidate = Path(__file__).resolve().parents[3]
    if (project_root_candidate / "plugins").is_dir() and (project_root_candidate / "logger").is_dir():
         if str(project_root_candidate) not in sys.path:
            sys.path.insert(0, str(project_root_candidate))
    else:
        current_path = Path(__file__).resolve()
        for i in range(5):
            p_root = current_path.parents[i]
            if (p_root / "plugins").is_dir() and (p_root / "logger").is_dir():
                if str(p_root) not in sys.path: sys.path.insert(0, str(p_root))
                project_root_candidate = p_root; break
        else: print("Warning: Could not reliably determine project root for sys.path modification.", file=sys.stderr)

    try:
        from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
        if 'CustomLogger' not in globals() or globals()['CustomLogger'] is None:
            from logger.custom_logger import CustomLogger as GlobalCustomLogger
            logger = GlobalCustomLogger()
    except ImportError as e:
        print(f"Error: Could not import dependencies for standalone test: {e}", file=sys.stderr)
        class ColoringAlgorithmPlugin: pass
        if 'logger' not in globals() or logger is None:
            import logging
            logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
            logger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg)})()
        logger.log(f"ImportError during test setup: {e}", level="ERROR")

    logger.log("ComplexPotentialColoringPlugin スタンドアロンテスト開始", level="INFO")
    plugin = ComplexPotentialColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}, ターゲットタイプ: {plugin.target_type}", level="INFO")
    assert plugin.target_type == "non_divergent", "Target type check failed"
    test_algo_params = {}

    # --- Test Case 1: Basic functionality ---
    logger.log("\n--- Test Case 1: Basic Functionality ---", level="INFO")
    h1, w1, max_it1 = 3, 4, 100
    iters1 = np.array([[10, 20, 90, max_it1], [max_it1, 50, max_it1, 60], [max_it1, max_it1, max_it1, max_it1]], dtype=np.int32)
    last_zn1 = np.array([[0j,0j,0j,1e-11j], [0.1+0.1j,0j,0.5+0.5j,0j], [1+1j,2+2j,0.01+0j,1e-10j]], dtype=np.complex128)
    dummy_zn_trajectory = np.zeros((h1,w1,10,2), dtype=np.float64) # Dummy, unused by this plugin
    fractal_data1 = {'iterations': iters1, 'last_zn_values': last_zn1, 'zn_values': dummy_zn_trajectory}
    common_params1 = {'max_iterations': max_it1, 'height': h1, 'width': w1}

    logger.log("Test 1.1: Grayscale", level="INFO")
    img1_gray = plugin.apply_coloring(fractal_data1, common_params1, test_algo_params, None)
    assert img1_gray.shape == (h1,w1,4), f"Test 1.1 Shape: Exp ({h1},{w1},4), Got {img1_gray.shape}"
    exp_grays1 = {(0,3):0, (1,0):140, (1,2):201, (2,0):228, (2,1):255, (2,2):38, (2,3):0}
    for r_idx in range(h1):
        for c_idx in range(w1):
            if iters1[r_idx, c_idx] == max_it1:
                assert np.array_equal(img1_gray[r_idx,c_idx,:3], [exp_grays1[(r_idx,c_idx)]]*3), f"Test 1.1 P({r_idx},{c_idx}) gray: Exp {exp_grays1[(r_idx,c_idx)]}, Got {img1_gray[r_idx,c_idx,0]}"
            else:
                assert np.array_equal(img1_gray[r_idx,c_idx,:3], plugin.DEFAULT_OUTSIDE_COLOR), f"Test 1.1 P({r_idx},{c_idx}) outside: Exp {plugin.DEFAULT_OUTSIDE_COLOR}, Got {img1_gray[r_idx,c_idx,:3]}"
    logger.log("Test 1.1: Grayscale assertions passed.", level="INFO")

    logger.log("Test 1.2: Color Map", level="INFO")
    cmap1 = [(0,0,255),(0,255,0),(255,0,0)] # B,G,R
    img1_map = plugin.apply_coloring(fractal_data1, common_params1, test_algo_params, cmap1)
    exp_colors1 = {(0,3):cmap1[0], (1,0):cmap1[1], (1,2):cmap1[1], (2,0):cmap1[1], (2,1):cmap1[2], (2,2):cmap1[0], (2,3):cmap1[0]}
    for r_idx in range(h1):
        for c_idx in range(w1):
            if iters1[r_idx, c_idx] == max_it1:
                 assert np.array_equal(img1_map[r_idx,c_idx,:3], exp_colors1[(r_idx,c_idx)]), f"Test 1.2 P({r_idx},{c_idx}) color: Exp {exp_colors1[(r_idx,c_idx)]}, Got {img1_map[r_idx,c_idx,:3]}"
            else:
                 assert np.array_equal(img1_map[r_idx,c_idx,:3], plugin.DEFAULT_OUTSIDE_COLOR), f"Test 1.2 P({r_idx},{c_idx}) outside: Exp {plugin.DEFAULT_OUTSIDE_COLOR}, Got {img1_map[r_idx,c_idx,:3]}"
    logger.log("Test 1.2: Color map assertions passed.", level="INFO")

    # --- Test Case 2: All points outside ---
    logger.log("\n--- Test Case 2: All Points Outside ---", level="INFO")
    h2,w2,max_it2 = 2,2,50; iters2=np.array([[10,20],[30,40]],dtype=np.int32); last_zn2=np.zeros((h2,w2),dtype=np.complex128)
    img2 = plugin.apply_coloring({'iterations':iters2,'last_zn_values':last_zn2}, {'max_iterations':max_it2,'height':h2,'width':w2}, {}, None)
    for r in range(h2):
        for c in range(w2): assert np.array_equal(img2[r,c,:3], plugin.DEFAULT_OUTSIDE_COLOR), f"Test 2 P({r},{c})"
    logger.log("Test 2: All outside points test passed.", level="INFO")

    # --- Test Case 3: Small max_iterations ---
    logger.log("\n--- Test Case 3: Small max_iterations (max_iters=1) ---", level="INFO")
    h3,w3,max_it3=1,2,1; iters3=np.array([[0,1]],dtype=np.int32); last_zn3=np.array([[0j, 0.5+0j]],dtype=np.complex128)
    img3_gray = plugin.apply_coloring({'iterations':iters3,'last_zn_values':last_zn3}, {'max_iterations':max_it3,'height':h3,'width':w3}, {}, None)
    assert np.array_equal(img3_gray[0,0,:3], plugin.DEFAULT_OUTSIDE_COLOR), "Test 3 P(0,0) outside"
    assert np.array_equal(img3_gray[0,1,:3], [0,0,0]), f"Test 3 P(0,1) gray: Exp [0,0,0], Got {img3_gray[0,1,:3]}"
    logger.log("Test 3: Small max_iterations (grayscale) test passed.", level="INFO")

    cmap3 = [(255,0,0),(0,255,0)] # R,G. num_colors-1 = 1
    img3_map = plugin.apply_coloring({'iterations':iters3,'last_zn_values':last_zn3}, {'max_iterations':max_it3,'height':h3,'width':w3}, {}, cmap3)
    assert np.array_equal(img3_map[0,1,:3], cmap3[0]), f"Test 3 P(0,1) color: Exp {cmap3[0]}, Got {img3_map[0,1,:3]}"
    logger.log("Test 3: Small max_iterations (colormap) test passed.", level="INFO")

    # --- Test Case 4: Varying last_zn_values (complex, small, large magnitudes) ---
    logger.log("\n--- Test Case 4: Varying last_zn_values ---", level="INFO")
    h4,w4,max_it4=1,4,20; iters4=np.array([[max_it4]*4],dtype=np.int32)
    last_zn4=np.array([[1e-12+0j, 0.01-0.01j, 1+0j, 100+100j]],dtype=np.complex128)
    img4_gray = plugin.apply_coloring({'iterations':iters4,'last_zn_values':last_zn4}, {'max_iterations':max_it4,'height':h4,'width':w4}, {}, None)
    assert np.array_equal(img4_gray[0,0,:3], [0,0,0]), f"Test 4 P(0,0) gray: Exp 0, Got {img4_gray[0,0,0]}"
    assert np.array_equal(img4_gray[0,1,:3], [24,24,24]), f"Test 4 P(0,1) gray: Exp 24, Got {img4_gray[0,1,0]}" # Corrected assertion
    assert np.array_equal(img4_gray[0,2,:3], [131,131,131]), f"Test 4 P(0,2) gray: Exp 131, Got {img4_gray[0,2,0]}"
    assert np.array_equal(img4_gray[0,3,:3], [255,255,255]), f"Test 4 P(0,3) gray: Exp 255, Got {img4_gray[0,3,0]}"
    logger.log("Test 4: Varying last_zn_values (grayscale) test passed.", level="INFO")

    cmap4 = [(0,0,255),(0,128,0),(255,255,0)] # B, DarkGreen, Yellow (3 colors, num_colors-1 = 2)
    img4_map = plugin.apply_coloring({'iterations':iters4,'last_zn_values':last_zn4}, {'max_iterations':max_it4,'height':h4,'width':w4}, {}, cmap4)
    assert np.array_equal(img4_map[0,0,:3], cmap4[0]), f"Test 4 P(0,0) color: Exp {cmap4[0]}, Got {img4_map[0,0,:3]}"
    assert np.array_equal(img4_map[0,1,:3], cmap4[0]), f"Test 4 P(0,1) color: Exp {cmap4[0]}, Got {img4_map[0,1,:3]}"
    assert np.array_equal(img4_map[0,2,:3], cmap4[1]), f"Test 4 P(0,2) color: Exp {cmap4[1]}, Got {img4_map[0,2,:3]}"
    assert np.array_equal(img4_map[0,3,:3], cmap4[2]), f"Test 4 P(0,3) color: Exp {cmap4[2]}, Got {img4_map[0,3,:3]}"
    logger.log("Test 4: Varying last_zn_values (colormap) test passed.", level="INFO")

    logger.log("\nComplexPotentialColoringPlugin スタンドアロンテスト完了", level="INFO")
    file_location_marker = Path(__file__).resolve().parent.name
    assert file_location_marker == "non_divergent", f"File location check: expected 'non_divergent', got '{file_location_marker}'"
