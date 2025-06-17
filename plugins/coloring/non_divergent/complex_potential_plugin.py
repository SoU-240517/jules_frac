import numpy as np
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
try:
    # プロジェクト標準のロガーをインポート
    from logger.custom_logger import CustomLogger
except ImportError:
    # CustomLoggerが見つからない場合のフォールバック (例: 単体テスト時など)
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    CustomLogger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg) if level == "INFO" else logging.warning(msg) if level == "WARNING" else logging.error(msg)})()

from numba import jit

logger = CustomLogger()

@jit(nopython=True)
def _calculate_potentials_jit(
    iterations: np.ndarray,
    last_zn_values: np.ndarray, # 複素数の最終Z値
    max_iterations: int
) -> tuple[np.ndarray, float, float, bool]:
    """
    ジュリア集合またはマンデルブロ集合の内部の点に対して複素ポテンシャルを計算します。
    ポテンシャルは log(|Z_n|) として定義されます。ここで Z_n は最大反復回数に達したときのZの値です。

    Args:
        iterations (np.ndarray): 各点の反復回数を格納した配列。
        last_zn_values (np.ndarray): 各点の最終的な複素数Zの値を格納した配列。
        max_iterations (int): 最大反復回数。

    Returns:
        tuple[np.ndarray, float, float, bool]: (ポテンシャルの配列, 計算された最小ポテンシャル, 計算された最大ポテンシャル, 有効なポテンシャル値が存在したかどうかのフラグ)
    """
    height, width = iterations.shape
    potentials = np.full((height, width), np.nan, dtype=np.float64)
    min_p = np.inf
    max_p = -np.inf
    has_valid = False

    for r in range(height):
        for c in range(width):
            if iterations[r, c] == max_iterations:
                abs_zn = np.abs(last_zn_values[r, c])
                if abs_zn > 1e-9: # log(0) を避けるための微小値チェック
                    potential_val = np.log(abs_zn)
                    potentials[r, c] = potential_val
                    min_p = min(min_p, potential_val)
                    max_p = max(max_p, potential_val)
                    has_valid = True
                else: # |Z_n| がほぼ0の場合の処理
                    potentials[r, c] = -np.inf # 非常に低いポテンシャルとしてマーク
                    min_p = min(min_p, -np.inf) # これにより min_p は -np.inf になる
                    has_valid = True # ポテンシャルが実質的に最小であっても、色付け対象の有効な点として扱う
    return potentials, min_p, max_p, has_valid

@jit(nopython=True)
def _normalize_and_color_jit(
    potentials: np.ndarray,
    min_potential_norm: float, # 正規化に使用する最小ポテンシャル
    max_potential_norm: float, # 正規化に使用する最大ポテンシャル
    img_array_rgb: np.ndarray, # 色付け結果を格納する HxWx3 のuint8配列 (RGB部分)
    color_map_array: np.ndarray | None, # カラーマップ (Numpy配列)。Numbaのためにオプショナル型またはNoneを渡す
    use_color_map: bool,
    default_outside_color_r: np.uint8, # 集合外の点のデフォルト色 (R)。Numbaのために型を明示
    default_outside_color_g: np.uint8, # 集合外の点のデフォルト色 (G)
    default_outside_color_b: np.uint8, # 集合外の点のデフォルト色 (B)
    color_scale: float, # 色のスケール
    potential_offset: float, # ポテンシャルオフセット
    potential_scale: float # ポテンシャルスケール
) -> None:
    """
    ポテンシャル値を正規化し、カラーマップまたはグレースケールで色付けするJITコンパイル済み関数。

    Args:
        potentials (np.ndarray): 各点のポテンシャル値を格納した配列。
        min_potential_norm (float): 正規化に使用する最小ポテンシャル値。
        max_potential_norm (float): 正規化に使用する最大ポテンシャル値。
        img_array_rgb (np.ndarray): 色付け結果を格納する配列 (HxWx3)。
        color_map_array (np.ndarray | None): カラーマップ配列 (Nx3) またはNone。
        use_color_map (bool): カラーマップを使用するかどうか。
        default_outside_color_r (np.uint8): 集合外の点のR値。
        default_outside_color_g (np.uint8): 集合外の点のG値。
        default_outside_color_b (np.uint8): 集合外の点のB値。
        color_scale (float): 色のスケール。
        potential_offset (float): ポテンシャル値に加算するオフセット。
        potential_scale (float): ポテンシャル値のスケール。
    """
    height, width = potentials.shape
    potential_range_norm = max_potential_norm - min_potential_norm

    for r in range(height):
        for c in range(width):
            current_potential = potentials[r,c]
            if np.isnan(current_potential): # 発散した点 (ポテンシャルがNaN)
                img_array_rgb[r,c,0] = default_outside_color_r
                img_array_rgb[r,c,1] = default_outside_color_g
                img_array_rgb[r,c,2] = default_outside_color_b
            else:
                norm_potential: float
                if current_potential == -np.inf: # ポテンシャルが-infinityの場合 (log(|Z_n|~0))
                    norm_potential = 0.0
                else:
                    # ポテンシャル値にオフセットとスケールを適用
                    adjusted_potential = (current_potential + potential_offset) * potential_scale
                    norm_potential = (adjusted_potential - min_potential_norm) / potential_range_norm

                norm_potential = max(0.0, min(1.0, norm_potential)) # [0, 1] の範囲にクランプ

                # 色のスケールを適用
                norm_potential = norm_potential * color_scale

                if not use_color_map: # グレースケール
                    gray_val = np.uint8(min(255.0, norm_potential * 255.0))
                    img_array_rgb[r,c,0] = gray_val
                    img_array_rgb[r,c,1] = gray_val
                    img_array_rgb[r,c,2] = gray_val
                else: # カラーマップを使用
                    if color_map_array is not None and color_map_array.shape[0] > 0:
                        # カラーマップのインデックスを計算
                        color_idx = norm_potential * (color_map_array.shape[0] - 1)
                        idx1 = int(color_idx)
                        idx2 = min(idx1 + 1, color_map_array.shape[0] - 1)
                        fraction = color_idx - idx1

                        # 2つの色を取得して補間
                        c1 = color_map_array[idx1]
                        c2 = color_map_array[idx2]

                        # 線形補間
                        r_val = c1[0] * (1.0 - fraction) + c2[0] * fraction
                        g_val = c1[1] * (1.0 - fraction) + c2[1] * fraction
                        b_val = c1[2] * (1.0 - fraction) + c2[2] * fraction

                        # 結果を代入（色のスケールは既にnorm_potentialに適用済み）
                        img_array_rgb[r,c,0] = np.uint8(min(255.0, r_val))
                        img_array_rgb[r,c,1] = np.uint8(min(255.0, g_val))
                        img_array_rgb[r,c,2] = np.uint8(min(255.0, b_val))
                    else: # use_color_map=True であってもカラーマップが空またはNoneの場合のフォールバック
                        img_array_rgb[r,c,0] = 0; img_array_rgb[r,c,1] = 0; img_array_rgb[r,c,2] = 0;


class ComplexPotentialColoringPlugin(ColoringAlgorithmPlugin):
    """
    複素ポテンシャルに基づいてフラクタル集合の内部を色付けするプラグイン。
    ポテンシャルは log(|Z_n|) で計算され、正規化後にカラーマップまたはグレースケールで表示されます。
    発散した点はデフォルト色（通常は黒）で描画されます。
    """
    DEFAULT_OUTSIDE_COLOR = (np.uint8(0), np.uint8(0), np.uint8(0)) # 集合外の点のデフォルト色 (黒)

    @property
    def name(self) -> str:
        """カラーリングアルゴリズムの名前を返します。"""
        return "複素ポテンシャル"

    @property
    def target_type(self) -> str:
        """このカラーリングアルゴリズムが対象とする領域の種類 ("divergent" または "non_divergent") を返します。"""
        return "non_divergent"

    def get_parameters_definition(self) -> list:
        """このカラーリングアルゴリズムに固有の調整可能なパラメータのリストを返します。"""
        return [
            {
                "name": "color_scale",
                "label": "色のスケール",
                "type": "float",
                "default": 1.0,
                "range": (0.1, 5.0),
                "step": 0.1,
                "tooltip": "色の変化の速さを調整します。大きいほど色が細かく変化します。"
            },
            {
                "name": "potential_offset",
                "label": "ポテンシャルオフセット",
                "type": "float",
                "default": 0.0,
                "range": (-10.0, 10.0),
                "step": 0.1,
                "tooltip": "ポテンシャル値に加算するオフセット値です。色の分布を全体的にシフトさせます。"
            },
            {
                "name": "potential_scale",
                "label": "ポテンシャルスケール",
                "type": "float",
                "default": 1.0,
                "range": (0.1, 10.0),
                "step": 0.1,
                "tooltip": "ポテンシャル値のスケールを調整します。値が大きいほどポテンシャルの変化が強調されます。"
            }
        ]

    def apply_coloring(
        self, fractal_data: dict, common_fractal_params: dict,
        algorithm_params: dict, color_map_data: list[tuple[int, int, int]] | None
    ) -> np.ndarray:
        """
        フラクタルデータに複素ポテンシャルカラーリングを適用します。

        Args:
            fractal_data (dict): フラクタル計算結果。'iterations' と 'last_zn_values' が必要です。
            common_fractal_params (dict): フラクタル計算の共通パラメータ。'max_iterations', 'height', 'width' が使用されます。
            algorithm_params (dict): このアルゴリズム固有のパラメータ (現在は未使用)。
            color_map_data (list[tuple[int, int, int]] | None): 使用するカラーマップ。Noneの場合はグレースケール。

        Returns:
            np.ndarray: RGBA形式のカラーリング済み画像データ。
        """
        iterations = fractal_data.get('iterations')
        last_zn_values = fractal_data.get('last_zn_values')

        height_param = common_fractal_params.get('height')
        width_param = common_fractal_params.get('width')

        if iterations is None or last_zn_values is None:
            logger.log("apply_coloring: 必須データ 'iterations' または 'last_zn_values' が見つかりません。", level="ERROR")
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
            logger.log(f"apply_coloring: 形状の不一致またはlast_zn_valuesの形状エラー。反復回数配列: {iterations.shape}, 最終Z値配列: {last_zn_values.shape}, パラメータ指定サイズ: ({height_param},{width_param})。反復回数配列の形状を使用します。", level="WARNING")
            if last_zn_values.shape != (height,width): # 形状が一致しない場合はエラー処理を試みる
                 logger.log("apply_coloring: last_zn_values の形状が iterations の形状と一致しません。エラー画像 (赤) を返します。", level="ERROR")
                 err_img = np.zeros((height, width, 4), dtype=np.uint8); err_img[:,:,0]=255; err_img[:,:,3]=255; return err_img # 赤いエラー画像


        max_iterations = common_fractal_params.get('max_iterations', 100)
        img_array = np.zeros((height, width, 4), dtype=np.uint8)
        img_array[:, :, 3] = 255
        img_array_rgb = img_array[:,:,:3]

        potentials, min_p_raw, max_p_raw, has_valid = _calculate_potentials_jit(
            iterations, last_zn_values, max_iterations
        )

        if not has_valid:
            logger.log("apply_coloring: 有効なポテンシャル値が見つかりませんでした。集合外のデフォルト色で出力します。", level="WARNING")
            for r_idx in range(height):
                for c_idx in range(width):
                    img_array_rgb[r_idx, c_idx, 0] = self.DEFAULT_OUTSIDE_COLOR[0]
                    img_array_rgb[r_idx, c_idx, 1] = self.DEFAULT_OUTSIDE_COLOR[1]
                    img_array_rgb[r_idx, c_idx, 2] = self.DEFAULT_OUTSIDE_COLOR[2]
            return img_array

        min_potential_for_norm = min_p_raw
        max_potential_for_norm = max_p_raw

        if min_p_raw == -np.inf: # 最小ポテンシャルが -inf の場合 (log(|Z|~0) の点が存在)
            finite_potentials = potentials[np.isfinite(potentials)]
            if finite_potentials.size > 0:
                # 有限なポテンシャルの最小値より少し小さい値を正規化の最小値とする
                min_potential_for_norm = np.min(finite_potentials) - 1.0
            else:
                # すべてのポテンシャルが -inf または NaN の場合 (後者は通常発生しないはず)
                min_potential_for_norm = -1.0
            if max_p_raw == -np.inf: # すべての有効なポテンシャルが -inf だった場合
                 max_potential_for_norm = 0.0

        if max_potential_for_norm <= min_potential_for_norm: # ポテンシャルの範囲が非常に狭いか無効な場合
             max_potential_for_norm = min_potential_for_norm + 1.0

        # 色のスケールを取得
        color_scale = algorithm_params.get("color_scale", 1.0)
        if color_scale <= 0:
            logger.log(f"色のスケール ({color_scale}) は正であるべきです。デフォルト値 1.0 を使用します。", level="WARNING")
            color_scale = 1.0

        # カラーマップの準備
        use_color_map = False
        color_map_np = None
        if color_map_data and len(color_map_data) > 0:
            try:
                color_map_np = np.array(color_map_data, dtype=np.uint8)
                if color_map_np.shape[1] == 3:  # RGB形式であることを確認
                    use_color_map = True
            except Exception as e:
                logger.log(f"カラーマップの変換中にエラーが発生しました: {e}", level="WARNING")

        # JITコンパイル済み関数を呼び出して色付けを実行
        _normalize_and_color_jit(
            potentials,
            min_potential_for_norm,
            max_potential_for_norm,
            img_array_rgb,
            color_map_np if use_color_map else None,
            use_color_map,
            self.DEFAULT_OUTSIDE_COLOR[0],
            self.DEFAULT_OUTSIDE_COLOR[1],
            self.DEFAULT_OUTSIDE_COLOR[2],
            color_scale,  # 色のスケールを渡す
            algorithm_params.get("potential_offset", 0.0),  # ポテンシャルオフセットを渡す
            algorithm_params.get("potential_scale", 1.0)  # ポテンシャルスケールを渡す
        )
        return img_array

if __name__ == '__main__':
    import sys
    # スタンドアロンテスト実行のために、プロジェクトルートをsys.pathに追加する試み
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
        # 警告: sys.path変更のためのプロジェクトルートを確実には特定できませんでした。

    try:
        from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
        if 'CustomLogger' not in globals() or globals()['CustomLogger'] is None: # ロガーが未定義の場合
            from logger.custom_logger import CustomLogger as GlobalCustomLogger
            logger = GlobalCustomLogger()
    except ImportError as e:
        print(f"Error: Could not import dependencies for standalone test: {e}", file=sys.stderr)
        class ColoringAlgorithmPlugin: pass
        if 'logger' not in globals() or logger is None:
            import logging
            logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
            logger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg)})()
        logger.log(f"テストセットアップ中のImportError: {e}", level="ERROR")

    logger.log("ComplexPotentialColoringPlugin スタンドアロンテスト開始", level="INFO")
    plugin = ComplexPotentialColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}, ターゲットタイプ: {plugin.target_type}", level="INFO")
    assert plugin.target_type == "non_divergent", "Target type check failed"
    test_algo_params = {}

    # --- テストケース 1: 基本機能 ---
    logger.log("\n--- テストケース 1: 基本機能 ---", level="INFO")
    h1, w1, max_it1 = 3, 4, 100
    iters1 = np.array([[10, 20, 90, max_it1], [max_it1, 50, max_it1, 60], [max_it1, max_it1, max_it1, max_it1]], dtype=np.int32)
    last_zn1 = np.array([[0j,0j,0j,1e-11j], [0.1+0.1j,0j,0.5+0.5j,0j], [1+1j,2+2j,0.01+0j,1e-10j]], dtype=np.complex128)
    dummy_zn_trajectory = np.zeros((h1,w1,10,2), dtype=np.float64) # ダミーデータ、このプラグインでは未使用
    fractal_data1 = {'iterations': iters1, 'last_zn_values': last_zn1, 'zn_values': dummy_zn_trajectory}
    common_params1 = {'max_iterations': max_it1, 'height': h1, 'width': w1}

    logger.log("テスト 1.1: グレースケール", level="INFO")
    img1_gray = plugin.apply_coloring(fractal_data1, common_params1, test_algo_params, None)
    assert img1_gray.shape == (h1,w1,4), f"テスト 1.1 形状: 期待値 ({h1},{w1},4), 実際 {img1_gray.shape}"
    exp_grays1 = {(0,3):0, (1,0):140, (1,2):201, (2,0):228, (2,1):255, (2,2):38, (2,3):0}
    for r_idx in range(h1):
        for c_idx in range(w1):
            if iters1[r_idx, c_idx] == max_it1:
                assert np.array_equal(img1_gray[r_idx,c_idx,:3], [exp_grays1[(r_idx,c_idx)]]*3), f"テスト 1.1 ピクセル({r_idx},{c_idx}) グレースケール: 期待値 {exp_grays1[(r_idx,c_idx)]}, 実際 {img1_gray[r_idx,c_idx,0]}"
            else:
                assert np.array_equal(img1_gray[r_idx,c_idx,:3], plugin.DEFAULT_OUTSIDE_COLOR), f"テスト 1.1 ピクセル({r_idx},{c_idx}) 集合外: 期待値 {plugin.DEFAULT_OUTSIDE_COLOR}, 実際 {img1_gray[r_idx,c_idx,:3]}"
    logger.log("テスト 1.1: グレースケールのアサーション成功", level="INFO")

    logger.log("テスト 1.2: カラーマップ", level="INFO")
    cmap1 = [(0,0,255),(0,255,0),(255,0,0)] # 青, 緑, 赤
    img1_map = plugin.apply_coloring(fractal_data1, common_params1, test_algo_params, cmap1)
    exp_colors1 = {(0,3):cmap1[0], (1,0):cmap1[1], (1,2):cmap1[1], (2,0):cmap1[1], (2,1):cmap1[2], (2,2):cmap1[0], (2,3):cmap1[0]}
    for r_idx in range(h1):
        for c_idx in range(w1):
            if iters1[r_idx, c_idx] == max_it1:
                 assert np.array_equal(img1_map[r_idx,c_idx,:3], exp_colors1[(r_idx,c_idx)]), f"テスト 1.2 ピクセル({r_idx},{c_idx}) 色: 期待値 {exp_colors1[(r_idx,c_idx)]}, 実際 {img1_map[r_idx,c_idx,:3]}"
            else:
                 assert np.array_equal(img1_map[r_idx,c_idx,:3], plugin.DEFAULT_OUTSIDE_COLOR), f"テスト 1.2 ピクセル({r_idx},{c_idx}) 集合外: 期待値 {plugin.DEFAULT_OUTSIDE_COLOR}, 実際 {img1_map[r_idx,c_idx,:3]}"
    logger.log("テスト 1.2: カラーマップのアサーション成功", level="INFO")

    # --- テストケース 2: 全ての点が集合外 ---
    logger.log("\n--- テストケース 2: 全ての点が集合外 ---", level="INFO")
    h2,w2,max_it2 = 2,2,50; iters2=np.array([[10,20],[30,40]],dtype=np.int32); last_zn2=np.zeros((h2,w2),dtype=np.complex128)
    img2 = plugin.apply_coloring({'iterations':iters2,'last_zn_values':last_zn2}, {'max_iterations':max_it2,'height':h2,'width':w2}, {}, None)
    for r_idx in range(h2):
        for c_idx in range(w2): assert np.array_equal(img2[r_idx,c_idx,:3], plugin.DEFAULT_OUTSIDE_COLOR), f"テスト 2 ピクセル({r_idx},{c_idx})"
    logger.log("テスト 2: 全ての点が集合外のテスト成功", level="INFO")

    # --- テストケース 3: 小さな最大反復回数 ---
    logger.log("\n--- テストケース 3: 小さな最大反復回数 (max_iters=1) ---", level="INFO")
    h3,w3,max_it3=1,2,1; iters3=np.array([[0,1]],dtype=np.int32); last_zn3=np.array([[0j, 0.5+0j]],dtype=np.complex128)
    img3_gray = plugin.apply_coloring({'iterations':iters3,'last_zn_values':last_zn3}, {'max_iterations':max_it3,'height':h3,'width':w3}, {}, None)
    assert np.array_equal(img3_gray[0,0,:3], plugin.DEFAULT_OUTSIDE_COLOR), "テスト 3 ピクセル(0,0) 集合外"
    assert np.array_equal(img3_gray[0,1,:3], [0,0,0]), f"テスト 3 ピクセル(0,1) グレースケール: 期待値 [0,0,0], 実際 {img3_gray[0,1,:3]}"
    logger.log("テスト 3: 小さな最大反復回数 (グレースケール) テスト成功", level="INFO")

    cmap3 = [(255,0,0),(0,255,0)] # 赤, 緑. num_colors-1 = 1
    img3_map = plugin.apply_coloring({'iterations':iters3,'last_zn_values':last_zn3}, {'max_iterations':max_it3,'height':h3,'width':w3}, {}, cmap3)
    assert np.array_equal(img3_map[0,1,:3], cmap3[0]), f"テスト 3 ピクセル(0,1) 色: 期待値 {cmap3[0]}, 実際 {img3_map[0,1,:3]}"
    logger.log("テスト 3: 小さな最大反復回数 (カラーマップ) テスト成功", level="INFO")

    # --- テストケース 4: 様々な最終Z値 (複素数、小さい絶対値、大きい絶対値) ---
    logger.log("\n--- テストケース 4: 様々な最終Z値 ---", level="INFO")
    h4,w4,max_it4=1,4,20; iters4=np.array([[max_it4]*4],dtype=np.int32)
    last_zn4=np.array([[1e-12+0j, 0.01-0.01j, 1+0j, 100+100j]],dtype=np.complex128)
    img4_gray = plugin.apply_coloring({'iterations':iters4,'last_zn_values':last_zn4}, {'max_iterations':max_it4,'height':h4,'width':w4}, {}, None)
    assert np.array_equal(img4_gray[0,0,:3], [0,0,0]), f"テスト 4 ピクセル(0,0) グレースケール: 期待値 0, 実際 {img4_gray[0,0,0]}"
    assert np.array_equal(img4_gray[0,1,:3], [24,24,24]), f"テスト 4 ピクセル(0,1) グレースケール: 期待値 24, 実際 {img4_gray[0,1,0]}"
    assert np.array_equal(img4_gray[0,2,:3], [131,131,131]), f"テスト 4 ピクセル(0,2) グレースケール: 期待値 131, 実際 {img4_gray[0,2,0]}"
    assert np.array_equal(img4_gray[0,3,:3], [255,255,255]), f"テスト 4 ピクセル(0,3) グレースケール: 期待値 255, 実際 {img4_gray[0,3,0]}"
    logger.log("テスト 4: 様々な最終Z値 (グレースケール) テスト成功", level="INFO")

    cmap4 = [(0,0,255),(0,128,0),(255,255,0)] # 青, 暗緑, 黄 (3色, num_colors-1 = 2)
    img4_map = plugin.apply_coloring({'iterations':iters4,'last_zn_values':last_zn4}, {'max_iterations':max_it4,'height':h4,'width':w4}, {}, cmap4)
    assert np.array_equal(img4_map[0,0,:3], cmap4[0]), f"テスト 4 ピクセル(0,0) 色: 期待値 {cmap4[0]}, 実際 {img4_map[0,0,:3]}"
    assert np.array_equal(img4_map[0,1,:3], cmap4[0]), f"テスト 4 ピクセル(0,1) 色: 期待値 {cmap4[0]}, 実際 {img4_map[0,1,:3]}"
    assert np.array_equal(img4_map[0,2,:3], cmap4[1]), f"テスト 4 ピクセル(0,2) 色: 期待値 {cmap4[1]}, 実際 {img4_map[0,2,:3]}"
    assert np.array_equal(img4_map[0,3,:3], cmap4[2]), f"テスト 4 ピクセル(0,3) 色: 期待値 {cmap4[2]}, 実際 {img4_map[0,3,:3]}"
    logger.log("テスト 4: 様々な最終Z値 (カラーマップ) テスト成功", level="INFO")

    logger.log("\nComplexPotentialColoringPlugin スタンドアロンテスト完了", level="INFO")
    file_location_marker = Path(__file__).resolve().parent.name
    assert file_location_marker == "non_divergent", f"ファイル場所チェック: 期待値 'non_divergent', 実際 '{file_location_marker}'"
