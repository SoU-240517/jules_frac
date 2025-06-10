import numpy as np
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
# 異なる実行コンテキストでの堅牢性のために、CustomLoggerのインポートにtry-exceptブロックを使用
try:
    from logger.custom_logger import CustomLogger
except ImportError:
    # CustomLoggerが見つからない場合の最小限のフォールバックロガー（例：分離テスト中）
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    CustomLogger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg) if level == "INFO" else logging.warning(msg) if level == "WARNING" else logging.error(msg)})()

from numba import jit

logger = CustomLogger()

@jit(nopython=True)
def _apply_final_z_abs_coloring_jit(
    iterations: np.ndarray,
    last_zn_values: np.ndarray, # 複素数型 (complex128)
    max_iterations: int,
    escape_radius: float,
    gamma: float,
    img_array_rgb: np.ndarray, # RGB部分（高さx幅x3）のみを渡す
    color_map_array: np.ndarray | None, # カラーマップ用のNumPy配列、またはNone
    use_color_map: bool
) -> None:
    """最終Z値の絶対値に基づいて色を付けるJITコンパイル済み関数。

    非発散点に対して、最終的なZ値の絶対値を正規化し、ガンマ補正を適用した後、
    グレースケールまたは指定されたカラーマップに基づいて色を決定します。

    Args:
        iterations (np.ndarray): 各点の反復回数を格納した配列。
        last_zn_values (np.ndarray): 各点の最終Z値を格納した複素数型配列。
        max_iterations (int): 最大反復回数。
        escape_radius (float): 発散半径。正規化に使用されます。
        gamma (float): ガンマ補正値。
        img_array_rgb (np.ndarray): 色を書き込む先のRGB画像配列 (高さx幅x3)。
        color_map_array (np.ndarray | None): カラーマップとして使用するNumPy配列 (Nx3)。Noneの場合はグレースケール。
        use_color_map (bool): カラーマップを使用するかどうかのフラグ。
    """
    height, width = iterations.shape

    for r_idx in range(height):
        for c_idx in range(width):
            if iterations[r_idx, c_idx] == max_iterations: # 非発散点
                final_z = last_zn_values[r_idx, c_idx]
                abs_z = np.abs(final_z)

                # escape_radius を上限として [0, 1] に正規化
                norm_val = min(max(abs_z / escape_radius, 0.0), 1.0)

                # ガンマ補正
                # 0や負の数に対する (1.0/gamma) 乗を避けるため、norm_valが0より大きいことを確認
                if norm_val > 0:
                     corrected_val = norm_val ** (1.0 / gamma)
                else:
                    corrected_val = 0.0


                if not use_color_map: # グレースケール
                    gray_val = int(corrected_val * 255)
                    gray_val = max(0, min(gray_val, 255)) # 念のためクリッピング
                    img_array_rgb[r_idx, c_idx, 0] = gray_val
                    img_array_rgb[r_idx, c_idx, 1] = gray_val
                    img_array_rgb[r_idx, c_idx, 2] = gray_val
                else: # カラーマップを使用
                    if color_map_array is not None:
                        num_colors = color_map_array.shape[0]
                        if num_colors > 0:
                            # 浮動小数点インデックスを計算
                            float_idx = corrected_val * (num_colors - 1)

                            # 線形補間のためのインデックスと重みを計算
                            idx1 = int(float_idx)
                            idx2 = idx1 + 1

                            # 配列の境界チェック
                            if idx1 >= num_colors - 1:
                                idx1 = idx2 = num_colors - 1

                            # 補間係数 (小数部分)
                            interp_factor = float_idx - idx1

                            # 2つの色を取得
                            c1_r, c1_g, c1_b = color_map_array[idx1]
                            c2_r, c2_g, c2_b = color_map_array[idx2]

                            # 線形補間
                            r = c1_r * (1.0 - interp_factor) + c2_r * interp_factor
                            g = c1_g * (1.0 - interp_factor) + c2_g * interp_factor
                            b = c1_b * (1.0 - interp_factor) + c2_b * interp_factor

                            # 結果を代入
                            img_array_rgb[r_idx, c_idx, 0] = int(r)
                            img_array_rgb[r_idx, c_idx, 1] = int(g)
                            img_array_rgb[r_idx, c_idx, 2] = int(b)
                        else: # カラーマップが空の場合 (フォールバック)
                            img_array_rgb[r_idx, c_idx, 0] = 0
                            img_array_rgb[r_idx, c_idx, 1] = 0
                            img_array_rgb[r_idx, c_idx, 2] = 0
                    # else: カラーマップがNoneだがuse_color_mapがTrue (設計上発生しにくい) -> 黒のまま
            # else: 発散した点などはデフォルトの色（黒）のまま


class FinalZMagnitudeColoringPlugin(ColoringAlgorithmPlugin):
    """
    非発散領域（内部）の点の最終的なZ値の絶対値に基づいて色を付けるプラグイン。

    動作原理:
    1. 各点 (ピクセル) が最大反復回数に達した場合（非発散とみなされる）、その点の最終的な複素数Z値 (`final_z`) を取得します。
    2. `final_z` の絶対値 `abs_z = abs(final_z)` を計算します。
    3. `abs_z` を `escape_radius` を用いて `[0, 1]` の範囲に正規化します。
       `norm_val = min(max(abs_z / escape_radius, 0.0), 1.0)`
       通常、非発散点の `abs_z` は `escape_radius` 以下になることが期待されます。
    4. 正規化された値 `norm_val` に対してガンマ補正を適用します: `corrected_val = norm_val ** (1.0 / gamma)`。
       `gamma` パラメータにより、色のグラデーションの応答曲線を調整できます。
       - `gamma = 1.0`: 線形応答（補正なし）。
       - `gamma > 1.0`: 暗い部分が明るくなり、全体のコントラストが下がる傾向。
       - `gamma < 1.0`: 明るい部分がより明るくなり、暗い部分が強調され、コントラストが上がる傾向。
    5. `corrected_val` に基づいて色を決定します。
       - グレースケールの場合: `gray = int(corrected_val * 255)`。
       - カラーマップ使用の場合: `color_index = int(corrected_val * (num_colors - 1))`。

    必要なデータ:
    - `iterations`: 各ピクセルの反復回数を格納したNumpy配列。
    - `last_zn_values`: 各ピクセルの最終Z値を格納した複素数型Numpy配列。
    - `max_iterations`: 計算時の最大反復回数。
    - `escape_radius`: 計算時の発散半径。

    パラメータ:
    - `gamma`: ガンマ補正値 (float, デフォルト 1.0)。
    """

    @property
    def name(self) -> str:
        """カラーリングアルゴリズムの表示名を返します。"""
        return "最終Z絶対値"

    @property
    def target_type(self) -> str:
        """このプラグインが対象とする領域タイプ（非発散）を返します。"""
        return "non_divergent"

    def get_parameters_definition(self) -> list:
        """このカラーリングアルゴリズムのパラメータ定義リストを返します。"""
        return [
            {
                "name": "gamma",
                "label": "ガンマ",
                "type": "float",
                "default": 1.0,
                "range": (0.1, 5.0)
            }
        ]

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict,
        color_map_data: list[tuple[int, int, int]] | None
    ) -> np.ndarray:
        """提供されたデータに最終Z値の絶対値に基づくカラーリングを適用します。

        Args:
            fractal_data (dict): 'iterations' と 'last_zn_values' を含むフラクタルデータ。
            common_fractal_params (dict): 'max_iterations', 'escape_radius' などを含む共通パラメータ。
            algorithm_params (dict): 'gamma' を含むアルゴリズム固有パラメータ。
            color_map_data (list[tuple[int, int, int]] | None): 使用するカラーマップ。

        Returns:
            np.ndarray: RGBA形式のカラーリング済み画像データ (uint8)。
        """
        iterations = fractal_data.get('iterations')
        last_zn_values = fractal_data.get('last_zn_values')

        height_param = common_fractal_params.get('height')
        width_param = common_fractal_params.get('width')

        # 基本的な形状とデータ存在チェック
        h_fallback, w_fallback = (100, 100) # iterationsやパラメータがない場合のデフォルト
        if height_param is not None: h_fallback = height_param
        if width_param is not None: w_fallback = width_param

        if iterations is None:
            logger.log("fractal_data に 'iterations' データが見つかりません。", level="ERROR")
            return np.zeros((h_fallback, w_fallback, 4), dtype=np.uint8)
        if last_zn_values is None:
            logger.log("fractal_data に 'last_zn_values' データが見つかりません。", level="ERROR")
            return np.zeros((h_fallback, w_fallback, 4), dtype=np.uint8)

        height, width = iterations.shape
        if (height, width) != last_zn_values.shape:
            logger.log(
                f"形状が一致しません。iterations: ({height}, {width}), last_zn_values: {last_zn_values.shape}。"
                "処理を中止します。", level="ERROR"
            )
            return np.zeros((h_fallback, w_fallback, 4), dtype=np.uint8)


        if height_param is not None and width_param is not None:
            if (height_param, width_param) != (height, width):
                logger.log(
                    f"形状が一致しません。common_fractal_params のピクセルサイズ: ({height_param}, {width_param}), "
                    f"データ配列の形状: ({height}, {width})。データ配列からの形状を使用します。",
                    level="WARNING"
                )
        # それ以外の場合、パラメータがNoneであれば、iterationsからの形状が既に設定されている。

        max_iterations = common_fractal_params.get('max_iterations', 100)
        if max_iterations <= 0:
            max_iterations = 1

        escape_radius = common_fractal_params.get('escape_radius', 2.0)
        if escape_radius <= 0: # escape_radius は正であるべき
            logger.log(f"escape_radius ({escape_radius}) は正であるべきです。デフォルト値 2.0 を使用します。", level="WARNING")
            escape_radius = 2.0

        gamma = algorithm_params.get("gamma", 1.0)
        if gamma <= 0: # ガンマ値は正であるべき
            logger.log(f"ガンマ値 ({gamma}) は正であるべきです。デフォルト値 1.0 を使用します。", level="WARNING")
            gamma = 1.0


        img_array = np.zeros((height, width, 4), dtype=np.uint8)
        img_array[:, :, 3] = 255  # アルファチャンネルを不透明に
        img_array_rgb = img_array[:, :, :3]

        use_color_map_flag = True
        color_map_np_array = None

        if not color_map_data or len(color_map_data) == 0:
            logger.log("apply_coloring: カラーマップが提供されていないか空です。グレースケールを使用します。", level="WARNING")
            use_color_map_flag = False
        else:
            try:
                color_map_np_array = np.array(color_map_data, dtype=np.uint8)
                if color_map_np_array.ndim != 2 or color_map_np_array.shape[1] != 3:
                    logger.log(f"apply_coloring: 無効なcolor_map_data構造です。Nx3を期待しましたが、形状 {color_map_np_array.shape} を受け取りました。グレースケールを使用します。", level="ERROR")
                    use_color_map_flag = False
                    color_map_np_array = None
            except Exception as e:
                logger.log(f"apply_coloring: color_map_dataのNumPy配列への変換エラー: {e}。グレースケールを使用します。", level="ERROR")
                use_color_map_flag = False
                color_map_np_array = None

        _apply_final_z_abs_coloring_jit(
            iterations,
            last_zn_values,
            max_iterations,
            escape_radius,
            gamma,
            img_array_rgb,
            color_map_np_array,
            use_color_map_flag
        )
        return img_array


if __name__ == '__main__':
    import sys
    from pathlib import Path
    # plugins.base_coloring_pluginのようなインポートのためにプロジェクトルートがsys.pathに含まれていることを確認する
    # このスクリプトがplugins/coloring/non_divergent/にあることを前提としています
    project_root_candidate = Path(__file__).resolve().parents[3]
    # 構造が変更された場合、プロジェクトルートを見つけるためのより堅牢な方法が必要になるかもしれません
    # 現時点では、これは一般的な構造です: project_root/src/app/plugins/.... または project_root/plugins/...
    # 構造がproject_root/pluginsの場合、parents[2]
    # 構造がproject_root/src/pluginsの場合、parents[3]（ここでは'src'が'app'のようなものと仮定）
    # このテストコンテキストでは、pluginsディレクトリがproject_rootの直下にあると仮定しましょう
    project_root = project_root_candidate
    # 現在のproject_rootのサブディレクトリに'plugins'があるかどうかを確認し、なければ調整する。
    # このロジックは、このテストがどこから実行されるかによって、より洗練される必要があるかもしれません。
    # 現時点では、このパスが開発環境にとって正しいと仮定します。
    if (project_root / "plugins").is_dir() and (project_root / "logger").is_dir():
         if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
    else: # 上記の構造が見つからない場合のフォールバック（例：異なる深さから実行する場合）
        # 'plugins'と'logger'の両方を含むディレクトリを探す試み
        current_path = Path(__file__).resolve()
        for i in range(5): # 最大5レベル上までチェック
            p_root = current_path.parents[i]
            if (p_root / "plugins").is_dir() and (p_root / "logger").is_dir():
                if str(p_root) not in sys.path:
                    sys.path.insert(0, str(p_root))
                project_root = p_root
                break
        else:
            print("警告: sys.path変更のためのプロジェクトルートを確実には特定できませんでした。", file=sys.stderr)


    try:
        from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
        # CustomLoggerが先頭でインポートされなかった場合、これはそのインポートまたはフォールバックを再トリガーします
        if 'CustomLogger' not in globals() or globals()['CustomLogger'] is None:
            from logger.custom_logger import CustomLogger as GlobalCustomLogger
            logger = GlobalCustomLogger()

    except ImportError as e:
        print(f"エラー: スタンドアロンテストのための依存関係をインポートできませんでした: {e}", file=sys.stderr)
        # インポートが失敗した場合の最小限のモックを定義する
        class ColoringAlgorithmPlugin: pass
        if 'logger' not in globals() or logger is None: # loggerがフォールバックでさえなかった場合
            import logging
            logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
            logger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg)})()
        logger.log(f"テストセットアップ中のImportError: {e}", level="ERROR")


    logger.log("FinalZMagnitudeColoringPlugin スタンドアロンテスト開始", level="INFO")

    plugin = FinalZMagnitudeColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}, ターゲットタイプ: {plugin.target_type}", level="INFO")
    assert plugin.target_type == "non_divergent", "ターゲットタイプのチェックに失敗しました"
    parameters = plugin.get_parameters_definition()
    logger.log(f"パラメータ定義: {parameters}", level="INFO")
    assert any(param['name'] == 'gamma' for param in parameters), "ガンマパラメータの定義が見つかりません"

    def calculate_expected_color(abs_z_val: float, escape_radius: float, gamma: float,
                                 is_divergent: bool, max_iters_val: int, current_iters_val: int,
                                 color_map: list[tuple[int, int, int]] | None) -> tuple[int, int, int]:
        """テスト用の期待色計算ヘルパー"""
        if is_divergent or current_iters_val < max_iters_val : # 発散点またはmax_iterに達していない
            return (0, 0, 0)

        norm_val = min(max(abs_z_val / escape_radius, 0.0), 1.0)

        if norm_val > 0:
            corrected_val = norm_val ** (1.0 / gamma)
        else:
            corrected_val = 0.0

        corrected_val = min(max(corrected_val, 0.0), 1.0) # ガンマ補正後もクリッピング

        if color_map:
            num_colors = len(color_map)
            if num_colors == 0: # 空のカラーマップは黒
                 return (0,0,0)
            color_idx = int(corrected_val * (num_colors - 1))
            color_idx = max(0, min(color_idx, num_colors - 1))
            return color_map[color_idx]
        else: # グレースケール
            gray_val = int(corrected_val * 255)
            gray_val = max(0, min(gray_val, 255))
            return (gray_val, gray_val, gray_val)

    # --- Test Case 1: 基本的なグレースケールとガンマ補正 ---
    logger.log("\n--- Test Case 1: 基本的なグレースケールとガンマ補正 ---", level="INFO")
    tc1_height, tc1_width = 1, 5
    tc1_max_iters = 50
    tc1_escape_radius = 2.0
    tc1_iters = np.full((tc1_height, tc1_width), tc1_max_iters, dtype=np.int32)
    # abs(z) 値: 0.0, 0.5, 1.0, 1.5, 2.0 (escape_radius と同じ), 2.5 (escape_radius 超過)
    # last_zn は複素数なので、絶対値が上記になるように設定
    tc1_last_zn = np.array([[0.0+0j, 0.5+0j, 1.0+0j, 1.5+0j, 2.0+0j, 2.5+0j]], dtype=np.complex128)
    # tc1_iters を tc1_last_zn の形状に合わせる
    tc1_height, tc1_width = tc1_last_zn.shape
    tc1_iters = np.full((tc1_height, tc1_width), tc1_max_iters, dtype=np.int32)


    tc1_common_params = {'max_iterations': tc1_max_iters, 'height': tc1_height, 'width': tc1_width, 'escape_radius': tc1_escape_radius}

    # ログ記録および計算用のz_abs値
    z_abs_values = [np.abs(z) for z in tc1_last_zn[0]]

    gammas_to_test = [0.5, 1.0, 2.0]
    for gamma_val in gammas_to_test:
        logger.log(f"Test 1.{['0.5', '1.0', '2.0'].index(str(gamma_val)) + 1}: グレースケール, gamma={gamma_val}", level="INFO")
        tc1_algo_params = {"gamma": gamma_val}
        img_gray = plugin.apply_coloring(
            {'iterations': tc1_iters, 'last_zn_values': tc1_last_zn},
            tc1_common_params, tc1_algo_params, None
        )
        assert img_gray.shape == (tc1_height, tc1_width, 4)
        for c_idx, abs_z in enumerate(z_abs_values):
            expected_color = calculate_expected_color(abs_z, tc1_escape_radius, gamma_val, False, tc1_max_iters, tc1_iters[0,c_idx], None)
            actual_color = img_gray[0, c_idx, :3]
            assert np.array_equal(actual_color, expected_color), \
                f"Gamma={gamma_val}, Z_abs={abs_z}: Expected gray {expected_color}, got {actual_color}"
        logger.log(f"Test 1.{['0.5', '1.0', '2.0'].index(str(gamma_val)) + 1}: グレースケール (gamma={gamma_val}) テスト合格", level="INFO")

    # --- Test Case 2: カラーマップ適用とガンマ補正 ---
    logger.log("\n--- Test Case 2: カラーマップ適用とガンマ補正 ---", level="INFO")
    tc2_color_map = [(0,0,0), (128,128,128), (255,255,255)] # シンプルな3色カラーマップ
    for gamma_val in gammas_to_test:
        logger.log(f"Test 2.{['0.5', '1.0', '2.0'].index(str(gamma_val)) + 1}: カラーマップ, gamma={gamma_val}", level="INFO")
        tc2_algo_params = {"gamma": gamma_val}
        img_cmap = plugin.apply_coloring(
            {'iterations': tc1_iters, 'last_zn_values': tc1_last_zn}, # tc1のデータを使用
            tc1_common_params, tc2_algo_params, tc2_color_map
        )
        assert img_cmap.shape == (tc1_height, tc1_width, 4)
        for c_idx, abs_z in enumerate(z_abs_values):
            expected_color = calculate_expected_color(abs_z, tc1_escape_radius, gamma_val, False, tc1_max_iters, tc1_iters[0,c_idx], tc2_color_map)
            actual_color = img_cmap[0, c_idx, :3]
            assert np.array_equal(actual_color, expected_color), \
                f"Gamma={gamma_val}, Z_abs={abs_z}: Expected color {expected_color}, got {actual_color} from map"
        logger.log(f"Test 2.{['0.5', '1.0', '2.0'].index(str(gamma_val)) + 1}: カラーマップ (gamma={gamma_val}) テスト合格", level="INFO")

    # --- Test Case 3: 正規化 (escape_radius変更) ---
    logger.log("\n--- Test Case 3: 正規化 (escape_radius変更) ---", level="INFO")
    tc3_escape_radius = 4.0 # tc1_escape_radius (2.0) の倍
    tc3_common_params = {'max_iterations': tc1_max_iters, 'height': tc1_height, 'width': tc1_width, 'escape_radius': tc3_escape_radius}
    tc3_gamma = 1.0
    tc3_algo_params = {"gamma": tc3_gamma}

    img_norm_test = plugin.apply_coloring(
        {'iterations': tc1_iters, 'last_zn_values': tc1_last_zn}, tc3_common_params, tc3_algo_params, None
    )
    logger.log(f"Test 3.1: グレースケール, escape_radius={tc3_escape_radius}, gamma={tc3_gamma}", level="INFO")
    for c_idx, abs_z in enumerate(z_abs_values): # tc1_last_znのz_abs値を使用
        expected_color = calculate_expected_color(abs_z, tc3_escape_radius, tc3_gamma, False, tc1_max_iters, tc1_iters[0,c_idx], None)
        actual_color = img_norm_test[0, c_idx, :3]
        assert np.array_equal(actual_color, expected_color), \
            f"EscapeRadius={tc3_escape_radius}, Z_abs={abs_z}: Expected gray {expected_color}, got {actual_color}"
    logger.log(f"Test 3.1: 正規化テスト (escape_radius={tc3_escape_radius}) 合格", level="INFO")

    # --- Test Case 4: 発散点と非発散点の混合 ---
    logger.log("\n--- Test Case 4: 発散点と非発散点の混合 ---", level="INFO")
    tc4_height, tc4_width = 1, 4
    tc4_max_iters = 50
    tc4_escape_radius = 2.0
    # P0: 非発散, z=1.0; P1: 発散; P2: 非発散, z=0.0; P3: 発散
    tc4_iters = np.array([[tc4_max_iters, tc4_max_iters - 10, tc4_max_iters, 1]], dtype=np.int32)
    tc4_last_zn = np.array([[1.0+0j, 10.0+0j, 0.0+0j, 20.0+0j]], dtype=np.complex128) # 発散点のZ値は無視される
    tc4_common_params = {'max_iterations': tc4_max_iters, 'height': tc4_height, 'width': tc4_width, 'escape_radius': tc4_escape_radius}
    tc4_gamma = 1.0
    tc4_algo_params = {"gamma": tc4_gamma}

    img_mix = plugin.apply_coloring(
        {'iterations': tc4_iters, 'last_zn_values': tc4_last_zn}, tc4_common_params, tc4_algo_params, None
    )
    logger.log(f"Test 4.1: グレースケール, 混合点, gamma={tc4_gamma}", level="INFO")
    expected_colors_mix = [
        calculate_expected_color(np.abs(tc4_last_zn[0,0]), tc4_escape_radius, tc4_gamma, False, tc4_max_iters, tc4_iters[0,0], None), # 非発散
        calculate_expected_color(np.abs(tc4_last_zn[0,1]), tc4_escape_radius, tc4_gamma, True, tc4_max_iters, tc4_iters[0,1], None),  # 発散
        calculate_expected_color(np.abs(tc4_last_zn[0,2]), tc4_escape_radius, tc4_gamma, False, tc4_max_iters, tc4_iters[0,2], None), # 非発散
        calculate_expected_color(np.abs(tc4_last_zn[0,3]), tc4_escape_radius, tc4_gamma, True, tc4_max_iters, tc4_iters[0,3], None)   # 発散
    ]
    for c_idx in range(tc4_width):
        actual_color = img_mix[0, c_idx, :3]
        assert np.array_equal(actual_color, expected_colors_mix[c_idx]), \
            f"Mixed P{c_idx}: Expected {expected_colors_mix[c_idx]}, got {actual_color}"
    logger.log("Test 4.1: 混合点テスト合格", level="INFO")

    # --- Test Case 5: エッジケース ---
    logger.log("\n--- Test Case 5: エッジケース ---", level="INFO")
    # Test 5.1: 全て発散
    logger.log("Test 5.1: 全てのピクセルが発散", level="INFO")
    tc5_1_iters = np.array([[10, 20], [5, 15]], dtype=np.int32)
    tc5_1_last_zn = np.zeros_like(tc5_1_iters, dtype=np.complex128)
    tc5_1_h, tc5_1_w = tc5_1_iters.shape
    tc5_1_common = {'max_iterations': 25, 'height': tc5_1_h, 'width': tc5_1_w, 'escape_radius': 2.0}
    img_all_divergent = plugin.apply_coloring(
        {'iterations': tc5_1_iters, 'last_zn_values': tc5_1_last_zn}, tc5_1_common, {"gamma": 1.0}, None
    )
    assert np.all(img_all_divergent[:,:,:3] == 0), "全てのピクセルが発散する場合、RGBは黒のはず"
    logger.log("Test 5.1: 全て発散テスト合格", level="INFO")

    # Test 5.2: 全て非発散、同じabs(z)
    logger.log("Test 5.2: 全て非発散、同じabs(z)値", level="INFO")
    tc5_2_iters = np.full((2,2), 50, dtype=np.int32)
    tc5_2_last_zn = np.full((2,2), 1.0+0j, dtype=np.complex128) # abs(z) = 1.0
    tc5_2_h, tc5_2_w = tc5_2_iters.shape
    tc5_2_common = {'max_iterations': 50, 'height': tc5_2_h, 'width': tc5_2_w, 'escape_radius': 2.0}
    img_same_z = plugin.apply_coloring(
        {'iterations': tc5_2_iters, 'last_zn_values': tc5_2_last_zn}, tc5_2_common, {"gamma": 1.0}, None
    )
    expected_color_same_z = calculate_expected_color(1.0, 2.0, 1.0, False, 50, 50, None)
    for r in range(tc5_2_h):
        for c in range(tc5_2_w):
            assert np.array_equal(img_same_z[r,c,:3], expected_color_same_z), f"P({r},{c}) Same Z: Expected {expected_color_same_z}, got {img_same_z[r,c,:3]}"
    logger.log("Test 5.2: 全て非発散、同じabs(z)値テスト合格", level="INFO")

    # Test 5.3: last_zn_values がない
    logger.log("Test 5.3: fractal_data に 'last_zn_values' がない", level="INFO")
    tc5_3_iters = np.array([[50]], dtype=np.int32)
    tc5_3_h, tc5_3_w = tc5_3_iters.shape
    tc5_3_common = {'max_iterations': 50, 'height': tc5_3_h, 'width': tc5_3_w, 'escape_radius': 2.0}
    # `last_zn_values` を意図的に含めない
    img_no_zn = plugin.apply_coloring({'iterations': tc5_3_iters}, tc5_3_common, {"gamma": 1.0}, None)
    assert img_no_zn.shape == (tc5_3_h, tc5_3_w, 4)
    assert np.all(img_no_zn == 0), "'last_zn_values' が欠損している場合、画像はすべてゼロであるべき"
    logger.log("Test 5.3: 'last_zn_values' なしテスト合格 (エラーログと黒画像を期待)", level="INFO")

    # Test 5.4: max_iterations = 1
    logger.log("Test 5.4: max_iterations = 1", level="INFO")
    tc5_4_max_iters = 1
    # P0: 非発散 (iters=1), z=0.5; P1: 発散 (iters=0), z=0.0 (無視される)
    tc5_4_iters = np.array([[tc5_4_max_iters, 0]], dtype=np.int32)
    tc5_4_last_zn = np.array([[0.5+0j, 0.0+0j]], dtype=np.complex128)
    tc5_4_h, tc5_4_w = tc5_4_iters.shape
    tc5_4_common = {'max_iterations': tc5_4_max_iters, 'height': tc5_4_h, 'width': tc5_4_w, 'escape_radius': 2.0}
    img_max_iter_1 = plugin.apply_coloring(
        {'iterations': tc5_4_iters, 'last_zn_values': tc5_4_last_zn}, tc5_4_common, {"gamma": 1.0}, None
    )
    expected_colors_max_iter_1 = [
        calculate_expected_color(0.5, 2.0, 1.0, False, tc5_4_max_iters, tc5_4_iters[0,0], None),
        calculate_expected_color(0.0, 2.0, 1.0, True, tc5_4_max_iters, tc5_4_iters[0,1], None)
    ]
    for c_idx in range(tc5_4_w):
        assert np.array_equal(img_max_iter_1[0,c_idx,:3], expected_colors_max_iter_1[c_idx]), \
            f"MaxIter=1, P{c_idx}: Expected {expected_colors_max_iter_1[c_idx]}, got {img_max_iter_1[0,c_idx,:3]}"
    logger.log("Test 5.4: max_iterations = 1 テスト合格", level="INFO")

    # --- Test Case 6: カラーマップのフォールバック ---
    logger.log("\n--- Test Case 6: カラーマップのフォールバック ---", level="INFO")
    tc6_iters = np.array([[50]], dtype=np.int32) # 単一ピクセル、非発散
    tc6_last_zn = np.array([[1.0+0j]], dtype=np.complex128) # abs(z)=1.0
    tc6_h, tc6_w = tc6_iters.shape
    tc6_common = {'max_iterations': 50, 'height': tc6_h, 'width': tc6_w, 'escape_radius': 2.0}
    tc6_algo_params = {"gamma": 1.0}

    # Test 6.1: 空のカラーマップ
    logger.log("Test 6.1: 空のカラーマップ []", level="INFO")
    img_empty_map = plugin.apply_coloring(
        {'iterations': tc6_iters, 'last_zn_values': tc6_last_zn}, tc6_common, tc6_algo_params, []
    )
    # 空のカラーマップの場合、JIT関数内で黒 (0,0,0) になる
    expected_empty_map_color = (0,0,0)
    assert np.array_equal(img_empty_map[0,0,:3], expected_empty_map_color), \
        f"Empty CM: Expected {expected_empty_map_color}, got {img_empty_map[0,0,:3]}"
    logger.log("Test 6.1: 空のカラーマップテスト合格 (黒を期待)", level="INFO")

    # Test 6.2: 不正な形式のカラーマップ (apply_coloring内でグレースケールにフォールバック)
    logger.log("Test 6.2: 不正な形式のカラーマップ (例: [(255,0)])", level="INFO")
    invalid_color_map = [(255,0)]
    img_invalid_map = plugin.apply_coloring(
        {'iterations': tc6_iters, 'last_zn_values': tc6_last_zn}, tc6_common, tc6_algo_params, invalid_color_map
    )
    # apply_coloring で use_color_map_flag が False になるため、グレースケールで計算される
    expected_invalid_map_color = calculate_expected_color(1.0, 2.0, 1.0, False, 50, 50, None) # グレースケール期待値
    assert np.array_equal(img_invalid_map[0,0,:3], expected_invalid_map_color), \
        f"無効な CM: {expected_invalid_map_color} が必要ですが、{img_invalid_map[0,0,:3]} を取得しました"
    logger.log("Test 6.2: 不正な形式のカラーマップテスト合格 (グレースケールフォールバックを期待)", level="INFO")


    logger.log("\nFinalZMagnitudeColoringPlugin スタンドアロンテスト完了", level="INFO")

    file_location_marker = Path(__file__).resolve().parent.name
    logger.log(f"このファイルは '{file_location_marker}' フォルダにあります。期待値: non_divergent", level="INFO")
    assert file_location_marker == "non_divergent", f"ファイル場所チェック: 期待値 'non_divergent', 実際 '{file_location_marker}'"
