import numpy as np
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
# Use a try-except block for CustomLogger import for robustness in different execution contexts
try:
    from logger.custom_logger import CustomLogger
except ImportError:
    # Minimal fallback logger if CustomLogger is not found (e.g., during isolated testing)
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    CustomLogger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg) if level == "INFO" else logging.warning(msg) if level == "WARNING" else logging.error(msg)})()

from numba import jit

logger = CustomLogger()

# @jit(nopython=True, cache=True)
def _apply_iteration_speed_coloring_jit(
    iterations: np.ndarray,
    max_iterations: int,
    img_array_rgb: np.ndarray, # RGB部分（HxWx3）のみを渡す
    color_map_array: np.ndarray | None, # NumPy array for color map, or None
    use_color_map: bool
) -> None:
    height, width = iterations.shape

    for r_idx in range(height):
        for c_idx in range(width):
            iters_val = iterations[r_idx, c_idx]

            diff: int
            if iters_val < 0:
                diff = 0
            else:
                # Ensure diff is calculated based on positive max_iterations
                # max_iterations is already ensured to be >= 1 by the caller
                diff = max_iterations - iters_val
                diff = max(0, min(diff, max_iterations))

            if not use_color_map: # Grayscale
                # Ensure max_iterations is not zero to prevent division by zero
                # This should be guaranteed by the caller setting max_iterations >= 1
                gray_val = int(255 * (diff / max_iterations))
                # Numba doesn't like list comprehensions for array assignment easily
                img_array_rgb[r_idx, c_idx, 0] = gray_val
                img_array_rgb[r_idx, c_idx, 1] = gray_val
                img_array_rgb[r_idx, c_idx, 2] = gray_val
            else: # Use color map
                if color_map_array is not None: # Should always be true if use_color_map is true
                    num_colors = color_map_array.shape[0]
                    if num_colors == 0: # Should not happen if color_map_array is properly passed
                        img_array_rgb[r_idx, c_idx, 0] = 0
                        img_array_rgb[r_idx, c_idx, 1] = 0
                        img_array_rgb[r_idx, c_idx, 2] = 0
                        continue

                    # Ensure max_iterations is not zero
                    color_idx = int((diff / max_iterations) * (num_colors - 1))
                    color_idx = max(0, min(color_idx, num_colors - 1))

                    img_array_rgb[r_idx, c_idx, 0] = color_map_array[color_idx, 0]
                    img_array_rgb[r_idx, c_idx, 1] = color_map_array[color_idx, 1]
                    img_array_rgb[r_idx, c_idx, 2] = color_map_array[color_idx, 2]
                # else case: use_color_map is true but color_map_array is None (should not happen by design)


class IterationSpeedColoringPlugin(ColoringAlgorithmPlugin):
    """
    非発散領域（内部）の収束速度に基づいて色を付けるプラグイン。
    max_iterations との差分 `diff` を計算し、`diff` が小さいほど収束が速い（内側）とみなし、
    カラーマップの若いインデックスを割り当てる。
    """

    @property
    def name(self) -> str:
        return "反復収束速度"

    @property
    def target_type(self) -> str:
        return "non_divergent"

    def get_parameters_definition(self) -> list:
        """現時点ではパラメータなし。"""
        return []

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict, # 現時点では未使用
        color_map_data: list[tuple[int, int, int]] | None
    ) -> np.ndarray:
        """
        収束速度に基づいてカラーリングを適用します。
        'iterations' 配列内の値を評価し、max_iterations との差 (diff) を計算します。
        diff が小さい (つまり iterations が max_iterations に近い) ほど、
        カラーマップの初期の色を使用します。
        """
        iterations = fractal_data.get('iterations')

        height_param = common_fractal_params.get('height')
        width_param = common_fractal_params.get('width')

        if iterations is None:
            logger.log("apply_coloring: 'iterations' data not found in fractal_data.", level="ERROR")
            h = height_param if height_param is not None else 100 # Default height
            w = width_param if width_param is not None else 100   # Default width
            return np.zeros((h, w, 4), dtype=np.uint8)

        # Determine shape from iterations array if params are missing or inconsistent
        height, width = iterations.shape
        if height_param is not None and width_param is not None:
            if (height_param, width_param) != (height, width):
                logger.log(
                    f"apply_coloring: Shape mismatch. common_fractal_params: ({height_param},{width_param}), "
                    f"iterations.shape: ({height},{width}). Using shape from iterations array.",
                    level="WARNING"
                )
        # Else, if params are None, shape from iterations is already set.

        max_iterations = common_fractal_params.get('max_iterations', 100)
        if max_iterations <= 0: # Avoid division by zero or nonsensical behavior
            max_iterations = 1 # Set to a minimal positive value

        img_array = np.zeros((height, width, 4), dtype=np.uint8)
        img_array[:, :, 3] = 255  # Alpha channel to opaque
        img_array_rgb = img_array[:, :, :3] # Pass a view of RGB channels to JIT function

        use_color_map_flag = True
        color_map_np_array = None

        if not color_map_data or len(color_map_data) == 0:
            logger.log("apply_coloring: No color map provided or empty. Using grayscale.", level="WARNING")
            use_color_map_flag = False
        else:
            try:
                # Convert list of tuples to NumPy array for Numba
                # Ensure dtype is uint8 for colors 0-255
                color_map_np_array = np.array(color_map_data, dtype=np.uint8)
                if color_map_np_array.ndim != 2 or color_map_np_array.shape[1] != 3:
                    logger.log(f"apply_coloring: Invalid color_map_data structure. Expected Nx3. Got shape {color_map_np_array.shape}. Using grayscale.", level="ERROR")
                    use_color_map_flag = False
                    color_map_np_array = None # Ensure it's None if not valid
            except Exception as e:
                logger.log(f"apply_coloring: Error converting color_map_data to NumPy array: {e}. Using grayscale.", level="ERROR")
                use_color_map_flag = False
                color_map_np_array = None


        _apply_iteration_speed_coloring_jit(
            iterations,
            max_iterations, # Already ensured >= 1
            img_array_rgb,
            color_map_np_array, # Pass the np array or None
            use_color_map_flag
        )
        return img_array


if __name__ == '__main__':
    import sys
    from pathlib import Path
    # Ensure project root is in sys.path for imports like plugins.base_coloring_plugin
    # This assumes the script is in plugins/coloring/non_divergent/
    project_root_candidate = Path(__file__).resolve().parents[3]
    # A more robust way to find project root might be needed if structure changes
    # For now, this is a common structure: project_root/src/app/plugins/.... or project_root/plugins/...
    # If your structure is project_root/plugins, then parents[2]
    # If your structure is project_root/src/plugins, then parents[3] (assuming 'src' is like 'app' here)
    # Let's assume the plugins directory is directly under project_root for this test context
    project_root = project_root_candidate
    # Check if 'plugins' is a subdir of current project_root, if not, adjust.
    # This logic might need to be more sophisticated depending on where this test is run from.
    # For now, let's assume this path is correct for the dev environment.
    if (project_root / "plugins").is_dir() and (project_root / "logger").is_dir():
         if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
    else: # Fallback if the above structure isn't found (e.g. running from a different depth)
        # Try to find a dir that contains both 'plugins' and 'logger'
        current_path = Path(__file__).resolve()
        for i in range(5): # Check up to 5 levels up
            p_root = current_path.parents[i]
            if (p_root / "plugins").is_dir() and (p_root / "logger").is_dir():
                if str(p_root) not in sys.path:
                    sys.path.insert(0, str(p_root))
                project_root = p_root
                break
        else:
            print("Warning: Could not reliably determine project root for sys.path modification.", file=sys.stderr)


    try:
        from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
        # If CustomLogger was not imported at the top, this will re-trigger its import or fallback
        if 'CustomLogger' not in globals() or globals()['CustomLogger'] is None:
            from logger.custom_logger import CustomLogger as GlobalCustomLogger
            logger = GlobalCustomLogger()

    except ImportError as e:
        print(f"Error: Could not import dependencies for standalone test: {e}", file=sys.stderr)
        # Define minimal mocks if imports fail
        class ColoringAlgorithmPlugin: pass
        if 'logger' not in globals() or logger is None: # if logger wasn't even the fallback
            import logging
            logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
            logger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg)})()
        logger.log(f"ImportError during test setup: {e}", level="ERROR")


    logger.log("IterationSpeedColoringPlugin スタンドアロンテスト", level="INFO")

    plugin = IterationSpeedColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}")
    logger.log(f"ターゲットタイプ: {plugin.target_type}")
    assert plugin.target_type == "non_divergent", "Target type check failed"
    logger.log(f"パラメータ定義: {plugin.get_parameters_definition()}")

    # --- Test Case 1: Basic Grayscale and Color Map Test (as before) ---
    logger.log("\n--- Test Case 1: Basic Functionality ---", level="INFO")
    height1, width1 = 4, 5
    test_iters1 = np.array([
        [0, 10, 20, 30, 50],    # diffs (max_iters=50): 50, 40, 30, 20, 0
        [50, 40, 30, 20, 0],    # diffs: 0, 10, 20, 30, 50
        [25, 25, 25, 25, 25],   # diffs: 25, 25, 25, 25, 25
        [-1, 30, 50, 10, -1]    # diffs: 0, 20, 0, 40, 0
    ], dtype=np.int32)
    max_iters_test1 = 50
    test_fractal_data1 = {'iterations': test_iters1, 'last_zn_values': np.zeros_like(test_iters1, dtype=np.complex128)} # Add dummy last_zn_values
    test_common_params1 = {'max_iterations': max_iters_test1, 'height': height1, 'width': width1}
    test_algo_params1 = {}

    logger.log("Test 1.1: カラーマップなし (グレースケール)", level="INFO")
    img_no_map1 = plugin.apply_coloring(test_fractal_data1, test_common_params1, test_algo_params1, None)
    assert img_no_map1.shape == (height1, width1, 4), f"Shape mismatch: expected ({height1},{width1},4), got {img_no_map1.shape}"
    assert img_no_map1.dtype == np.uint8, "dtype mismatch"
    # Expected grays (diff = max_iters - iters, gray = 255 * diff / max_iters)
    expected_grays1 = np.array([[255,204,153,102,0], [0,51,102,153,255], [127,127,127,127,127], [0,102,0,204,0]], dtype=np.uint8)
    for r in range(height1):
        for c in range(width1):
            assert np.array_equal(img_no_map1[r,c,:3], [expected_grays1[r,c]]*3), f"P({r},{c}) gray got {img_no_map1[r,c,:3]}, exp {[expected_grays1[r,c]]*3}"
    logger.log("Test 1.1: グレースケールテスト合格", level="INFO")

    logger.log("Test 1.2: カラーマップあり", level="INFO")
    test_color_map1 = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (255,0,255)] # R,G,B,Y,M
    img_with_map1 = plugin.apply_coloring(test_fractal_data1, test_common_params1, test_algo_params1, test_color_map1)
    assert img_with_map1.shape == (height1, width1, 4)
    # Expected indices (idx = int((diff/max_iters)*(num_colors-1)))
    expected_indices_map1 = [[4,3,2,1,0], [0,0,1,2,4], [2,2,2,2,2], [0,1,0,3,0]]
    for r in range(height1):
        for c in range(width1):
            assert np.array_equal(img_with_map1[r,c,:3], test_color_map1[expected_indices_map1[r][c]]), f"P({r},{c}) color got {img_with_map1[r,c,:3]}, exp {test_color_map1[expected_indices_map1[r][c]]}"
    logger.log("Test 1.2: カラーマップテスト合格", level="INFO")

    # --- Test Case 2: Edge cases for max_iterations ---
    logger.log("\n--- Test Case 2: max_iterations Edge Cases ---", level="INFO")
    height2, width2 = 1, 3
    max_iters_test2 = 1
    test_iters2 = np.array([[0, 1, -1]], dtype=np.int32) # diffs (max_iters=1): 1, 0, 0
    test_fractal_data2 = {'iterations': test_iters2}
    test_common_params2 = {'max_iterations': max_iters_test2, 'height': height2, 'width': width2}

    logger.log("Test 2.1: max_iterations = 1 (グレースケール)", level="INFO")
    img_max_iter_1_gray = plugin.apply_coloring(test_fractal_data2, test_common_params2, test_algo_params1, None)
    assert img_max_iter_1_gray.shape == (height2,width2,4)
    # P(0,0): iters=0, diff=1. gray = 255 * 1/1 = 255
    assert np.array_equal(img_max_iter_1_gray[0,0,:3], [255,255,255]), f"max_iter=1, P(0,0) gray got {img_max_iter_1_gray[0,0,:3]}"
    # P(0,1): iters=1, diff=0. gray = 255 * 0/1 = 0
    assert np.array_equal(img_max_iter_1_gray[0,1,:3], [0,0,0]), f"max_iter=1, P(0,1) gray got {img_max_iter_1_gray[0,1,:3]}"
    # P(0,2): iters=-1, diff=0. gray = 0
    assert np.array_equal(img_max_iter_1_gray[0,2,:3], [0,0,0]), f"max_iter=1, P(0,2) gray got {img_max_iter_1_gray[0,2,:3]}"
    logger.log("Test 2.1: max_iterations=1 グレースケールテスト合格", level="INFO")

    logger.log("Test 2.2: max_iterations = 1 (カラーマップあり - 3色 R,G,B)", level="INFO")
    test_color_map2 = [(255,0,0), (0,255,0), (0,0,255)] # R,G,B
    img_max_iter_1_map = plugin.apply_coloring(test_fractal_data2, test_common_params2, test_algo_params1, test_color_map2)
    # P(0,0): iters=0, diff=1. idx = int((1/1)*(2)) = 2 (Blue)
    assert np.array_equal(img_max_iter_1_map[0,0,:3], test_color_map2[2]), f"max_iter=1, P(0,0) color got {img_max_iter_1_map[0,0,:3]}"
    # P(0,1): iters=1, diff=0. idx = int((0/1)*(2)) = 0 (Red)
    assert np.array_equal(img_max_iter_1_map[0,1,:3], test_color_map2[0]), f"max_iter=1, P(0,1) color got {img_max_iter_1_map[0,1,:3]}"
    # P(0,2): iters=-1, diff=0. idx = 0 (Red)
    assert np.array_equal(img_max_iter_1_map[0,2,:3], test_color_map2[0]), f"max_iter=1, P(0,2) color got {img_max_iter_1_map[0,2,:3]}"
    logger.log("Test 2.2: max_iterations=1 カラーマップテスト合格", level="INFO")

    # --- Test Case 3: iterations == max_iterations (non-converged points by this metric) ---
    logger.log("\n--- Test Case 3: iterations == max_iterations ---", level="INFO")
    height3, width3 = 1, 2
    max_iters_test3 = 30
    test_iters3 = np.array([[10, 30]], dtype=np.int32) # diffs (max_iters=30): 20, 0
    test_fractal_data3 = {'iterations': test_iters3}
    test_common_params3 = {'max_iterations': max_iters_test3, 'height': height3, 'width': width3}

    logger.log("Test 3.1: iterations == max_iterations (グレースケール)", level="INFO")
    img_iter_eq_max_gray = plugin.apply_coloring(test_fractal_data3, test_common_params3, test_algo_params1, None)
    # P(0,0): iters=10, diff=20. gray = 255 * 20/30 = 170
    assert np.array_equal(img_iter_eq_max_gray[0,0,:3], [170,170,170]), f"iter=max_iter, P(0,0) gray got {img_iter_eq_max_gray[0,0,:3]}"
    # P(0,1): iters=30, diff=0. gray = 0
    assert np.array_equal(img_iter_eq_max_gray[0,1,:3], [0,0,0]), f"iter=max_iter, P(0,1) gray got {img_iter_eq_max_gray[0,1,:3]}"
    logger.log("Test 3.1: iterations == max_iterations グレースケールテスト合格", level="INFO")

    # --- Test Case 4: Invalid/Missing data ---
    logger.log("\n--- Test Case 4: Invalid/Missing Data ---", level="INFO")
    logger.log("Test 4.1: 'iterations' データがない場合", level="INFO")
    img_no_iters = plugin.apply_coloring({}, test_common_params1, test_algo_params1, test_color_map1) # common_params1 has h/w
    assert img_no_iters.shape == (height1, width1, 4), f"No iters shape: expected ({height1},{width1},4), got {img_no_iters.shape}"
    assert np.all(img_no_iters == 0), "Image should be all zeros if iterations are missing" # Alpha also 0
    logger.log("Test 4.1: Iterationsデータなしテスト合格", level="INFO")

    logger.log("Test 4.2: max_iterations = 0 (will be set to 1 by plugin)", level="INFO")
    edge_common_params_zero = {'max_iterations': 0, 'height': 1, 'width': 1}
    edge_iters_zero = np.array([[0]], dtype=np.int32) # diff will be 1 (max_iters_internal=1 - 0)
    img_edge_zero = plugin.apply_coloring({'iterations': edge_iters_zero}, edge_common_params_zero, test_algo_params1, test_color_map1)
    # max_iters=1, iters=0, diff=1. idx = int((1/1)*(4)) = 4 (Magenta from test_color_map1)
    assert np.array_equal(img_edge_zero[0,0,:3], test_color_map1[4]), "max_iterations=0 failed"
    logger.log("Test 4.2: max_iterations=0 テスト合格", level="INFO")

    logger.log("\nIterationSpeedColoringPlugin スタンドアロンテスト完了", level="INFO")

    file_location_marker = Path(__file__).resolve().parent.name
    logger.log(f"このファイルは '{file_location_marker}' フォルダにあります。期待値: non_divergent", level="INFO")
    assert file_location_marker == "non_divergent", f"File location check: expected 'non_divergent', got '{file_location_marker}'"
