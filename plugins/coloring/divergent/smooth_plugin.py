import numpy as np
from numba import jit
import math

try:
    from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
except ImportError: # pragma: no cover
    # このプラグインファイルがプロジェクトのルートからではなく、
    # plugins/coloring/divergent ディレクトリから直接実行された場合など、
    # 相対インポートが失敗するケースのためのフォールバック。
    from plugins.base_coloring_plugin import ColoringAlgorithmPlugin

# CustomLoggerをインポートするためのパス設定
import sys
from pathlib import Path
_logger_path_finder = Path(__file__).resolve()
# このファイルの場所 (plugins/coloring/divergent) からプロジェクトルート (jules_frac) を特定
_project_root_for_logger = _logger_path_finder.parent.parent.parent
if str(_project_root_for_logger) not in sys.path:
    sys.path.insert(0, str(_project_root_for_logger))
try:
    from logger.custom_logger import CustomLogger
    logger = CustomLogger()
except ImportError: # pragma: no cover
    # CustomLogger のインポートに失敗した場合のフォールバック (例: 環境設定の問題)
    print("警告: smooth_coloring_plugin.py で CustomLogger をインポートできませんでした。標準のprintを使用します。")
    class PrintLogger: # シンプルなフォールバックロガー
        def log(self, message, level="INFO"): print(f"[{level}] {message}") # ログレベルとメッセージを出力
    logger = PrintLogger()

@jit(nopython=True, cache=False, fastmath=True) # Numba JITコンパイラを適用。キャッシュは一時的に無効 (ModuleNotFoundError回避のため)。fastmathを有効化。
def _apply_smooth_coloring_jit(
    iterations_array: np.ndarray,
    last_z_mod_sq_array: np.ndarray,
    max_iters: int,
    escape_radius_sq: float, # 現在の平滑化計算式では直接使用されていませんが、将来の拡張や他の平滑化手法との一貫性のために引数として保持しています。
    color_scale_factor: float,
    color_map: np.ndarray # カラーマップデータ。形状は (N, 3) で、各行がRGB値 (uint8) を表します。
) -> np.ndarray:
    """
    反復回数と最終的な|Z|^2値に基づいてスムーズカラーリングを適用するJITコンパイル済み関数。
    アルゴリズムは `iters + 1 - log(log(|Z|))/log(2)` に基づいています。

    Args:
        iterations_array (np.ndarray): 各点の反復回数を格納した配列。
        last_z_mod_sq_array (np.ndarray): 各点の最終的な|Z|^2値を格納した配列。
        max_iters (int): 最大反復回数。
        escape_radius_sq (float): 発散とみなす半径の2乗 (この関数では直接使用されませんが、インターフェースの一貫性のために存在)。
        color_scale_factor (float): 色の変化の速さを調整するスケールファクター。
        color_map (np.ndarray): 色補間に使用するカラーマップ (形状: (N,3), dtype: uint8)。

    Returns:
        np.ndarray: RGBA形式のカラーリング済み画像データ。
    """
    height, width = iterations_array.shape
    output_image_rgba = np.empty((height, width, 4), dtype=np.uint8)
    output_image_rgba[:, :, 3] = 255 # アルファチャンネルを完全に不透明に設定

    num_colors_in_map = color_map.shape[0]
    # 補間には少なくとも2色を確保してください。そうでない場合は黒にフォールバックします。
    # これは理想的には、color_map_data の呼び出し側Pythonコードのロジックによって保証されるべきです。
    if num_colors_in_map < 2: # カラーマップの色数が2未満の場合
        output_image_rgba[:, :, 0:3] = 0 # RGBを黒に設定
        return output_image_rgba

    log_2 = math.log(2.0) # log(2)を事前計算

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]

            if iters == max_iters: # 点が集合内に留まった場合
                output_image_rgba[r_idx, c_idx, 0:3] = 0 # 黒色で描画
            else:
                mod_sq = last_z_mod_sq_array[r_idx, c_idx]
                smooth_val: float
                try:
                    # 発散した点の場合、mod_sq は escape_radius_sq より大きくなるはずです (例: 半径2の場合 > 4.0)。
                    # これは mod_sq > 0 を意味します。
                    if mod_sq <= 0.0: # 通常、正しく発散した点では mod_sq > 0 となります。これはエッジケースの処理です。
                        smooth_val = float(iters)
                    else:
                        modulus = math.sqrt(mod_sq) # |Z|
                        # escape_radius > 1 (例: 2) の場合、modulus > 1 です。
                        if modulus <= 1.0: # 通常、発散した点では modulus > escape_radius (>1) となります。これもエッジケースの処理です。
                            # |Z| <= 1 の場合、log(|Z|) <= 0 となり、log(log(|Z|)) が問題になります。
                            smooth_val = float(iters)
                        else:
                            log_of_modulus = math.log(modulus) # log(|Z|)
                            # modulus > 1 なので、log_of_modulus > 0 です。
                            # これにより、log(log_of_modulus) の項は数学的に有効になります。
                            smooth_val = float(iters) + 1.0 - math.log(log_of_modulus) / log_2
                except Exception: # pragma: no cover ; 予期しない数学的エラー (例: 極端な値による domain error) をキャッチ
                    # 計算エラーが発生した場合は、単純な整数反復回数にフォールバックします
                    smooth_val = float(iters)

                # smooth_val をカラーインデックスにマッピングします
                color_idx_float = smooth_val * color_scale_factor

                # マップ内の2色間の線形補間
                idx0_floor = math.floor(color_idx_float)
                fraction = color_idx_float - idx0_floor # fraction は常に [0.0, 1.0) の範囲になります

                # 配列アクセス用にインデックスが整数であることを確認し、floor の負の結果を剰余で正しく処理します
                c1_idx = int(idx0_floor) % num_colors_in_map # 負のインデックスも正しく扱えるように剰余演算を使用
                c2_idx = (int(idx0_floor) + 1) % num_colors_in_map

                r_val = color_map[c1_idx, 0] * (1.0 - fraction) + color_map[c2_idx, 0] * fraction
                g_val = color_map[c1_idx, 1] * (1.0 - fraction) + color_map[c2_idx, 1] * fraction
                b_val = color_map[c1_idx, 2] * (1.0 - fraction) + color_map[c2_idx, 2] * fraction

                # uint8 に変換する前にカラー値を [0, 255] にクランプします
                output_image_rgba[r_idx, c_idx, 0] = np.uint8(max(0.0, min(255.0, r_val))) # R
                output_image_rgba[r_idx, c_idx, 1] = np.uint8(max(0.0, min(255.0, g_val)))
                output_image_rgba[r_idx, c_idx, 2] = np.uint8(max(0.0, min(255.0, b_val)))
    return output_image_rgba


class SmoothColoringPlugin(ColoringAlgorithmPlugin):
    """発散領域に対してスムーズなカラーグラデーションを適用するカラーリングプラグインです。

    このプラグインは、フラクタル計算結果の反復回数と最終的な|Z|^2値を使用して、
    連続的な色の変化を生成し、段階的な色の境界を滑らかにします。
    """
    @property
    def name(self) -> str:
        """カラーリングアルゴリズムの名前を返します。"""
        return "スムーズカラー"

    def get_parameters_definition(self) -> list:
        """このカラーリングアルゴリズムに固有の調整可能なパラメータのリストを返します。"""
        return [
            {'name': 'color_scale', 'label': '色のスケール',
             'type': 'float', 'default': 1.0, 'range': (0.01, 100.0), 'step': 0.01, # 範囲とステップサイズを調整
             'tooltip': '色の変化の速さを調整します。大きいほど色が細かく変化します。'}
        ]

    def apply_coloring(self, fractal_data: dict, common_fractal_params: dict,
                       algorithm_params: dict, color_map_data: list[tuple[int,int,int]] | None) -> np.ndarray:
        """
        フラクタルデータにスムーズカラーリングを適用します。

        Args:
            fractal_data (dict): フラクタル計算結果を含む辞書。
                                 'iterations' と 'last_z_modulus_sq' キーが期待されます。
            common_fractal_params (dict): フラクタル計算の共通パラメータ。
                                        'max_iterations', 'escape_radius', 'image_height_px', 'image_width_px' が期待されます。
            algorithm_params (dict): このカラーリングアルゴリズム固有のパラメータ。
                                   'color_scale' が期待されます。
            color_map_data (list[tuple[int,int,int]] | None): 使用するカラーマップのリスト。Noneまたは色数が少ない場合はデフォルトを使用。

        Returns:
            np.ndarray: RGBA形式のカラーリング済み画像データ。
        """

        iterations = fractal_data.get('iterations')
        last_z_mod_sq = fractal_data.get('last_z_modulus_sq')

        # --- ここからデバッグ情報追加 ---
        # print(f"SmoothColoringPlugin: カラーリング適用中...")
        # print(f"  共通パラメータ: max_iters={common_fractal_params.get('max_iterations', 'N/A')}, escape_radius={common_fractal_params.get('escape_radius', 'N/A')}")
        # print(f"  アルゴリズムパラメータ: color_scale={algorithm_params.get('color_scale', '該当なし')}")
        # print(f"  受信した fractal_data のキー: {list(fractal_data.keys())}")

        # if iterations is not None:
        #     print(f"  反復回数データ: 形状={iterations.shape}, 型={iterations.dtype}, 最小={np.min(iterations)}, 最大={np.max(iterations)}, 平均={np.mean(iterations):.2f}")
        #     points_in_set = np.sum(iterations == common_fractal_params.get('max_iterations', 100))
        #     print(f"  集合内の点の数 (iter == max_iter): {points_in_set} / {iterations.size} ({points_in_set/iterations.size*100:.2f}%)")
        # else:
        #     print("  反復回数データがありません。")

        # if last_z_mod_sq is not None:
        #     print(f"  最終|Z|^2データ: 形状={last_z_mod_sq.shape}, 型={last_z_mod_sq.dtype}, 最小={np.min(last_z_mod_sq):.2e}, 最大={np.max(last_z_mod_sq):.2e}, 平均={np.mean(last_z_mod_sq):.2e}")
        #     if iterations is not None and np.any(iterations < common_fractal_params.get('max_iterations', 100)):
        #         escaped_mask = iterations < common_fractal_params.get('max_iterations', 100)
        #         print(f"    発散した点の|Z|^2: 最小={np.min(last_z_mod_sq[escaped_mask]):.2e}, 最大={np.max(last_z_mod_sq[escaped_mask]):.2e}, 平均={np.mean(last_z_mod_sq[escaped_mask]):.2e}")
        # else:
        #     print("  最終|Z|^2データがありません。")
        # --- デバッグ情報追加ここまで ---

        if iterations is None or last_z_mod_sq is None:
            # 必須データがない場合は、共通パラメータから画像の次元を取得しようと試みる
            height_px = common_fractal_params.get('image_height_px', 100) # デフォルトは100
            width_px = common_fractal_params.get('image_width_px', 100)   # デフォルトは100
            logger.log("スムーズカラーリングに必要なデータ ('iterations' または 'last_z_modulus_sq') が見つかりません。黒い画像を返します。", level="WARNING")
            fallback_img = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_img[:,:,3] = 255 # アルファチャンネルを不透明に設定
            return fallback_img

        max_iters = common_fractal_params.get('max_iterations', 100)
        escape_radius = common_fractal_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius # JIT関数に渡されます

        color_scale_from_plugin = algorithm_params.get('color_scale', 1.0)

        if not color_map_data or len(color_map_data) < 2: # 補間には少なくとも2色が必要です
            # logger.log("SmoothColoringPlugin 警告: 提供されたカラーマップの色数が不足しているため (2色未満)、デフォルトのグレースケールマップを使用します。", level="WARNING")
            # カラーマップが提供されていないか、色数が補間に不足している場合は、単純なグレースケールマップをデフォルトとして使用します。
            color_map_np = np.array([(i,i,i) for i in range(256)], dtype=np.uint8)
        else:
            color_map_np = np.array(color_map_data, dtype=np.uint8)

        colored_image = _apply_smooth_coloring_jit(
            iterations, last_z_mod_sq, max_iters, escape_radius_sq,
            color_scale_from_plugin,
            color_map_np
        )

        return colored_image

if __name__ == '__main__':
    logger.log("SmoothColoringPlugin のテストを開始します...", level="INFO")
    plugin = SmoothColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}", level="INFO")
    logger.log(f"パラメータ定義: {plugin.get_parameters_definition()}", level="INFO")

    # テストデータ
    h, w = 60, 80
    max_i = 200
    test_iters = np.random.randint(0, max_i + 1, size=(h, w), dtype=np.int32)
    # 集合内にある点をいくつかシミュレート (反復回数が最大値)
    test_iters[h//2 - 5 : h//2 + 5, w//2 - 5 : w//2 + 5] = max_i
    # 様々な|Z|^2値を持つ発散した点をいくつかシミュレート
    # 発散した点の場合、last_z_mod_sq は escape_radius_sq より大きくなるはずです
    er_val = 2.0 # テスト用の escape_radius
    er_sq = er_val * er_val
    test_mod_sq = np.random.uniform(er_sq + 0.001, er_sq + 1000.0, size=(h,w)).astype(np.float64) # |Z|^2 が escape_radius^2 より大きいことを保証
    test_mod_sq[test_iters == max_i] = 0.0 # 集合内の点の場合、|Z|^2 はしばしば0または未定義です

    test_fractal_data = {'iterations': test_iters, 'last_z_modulus_sq': test_mod_sq, 'height_px':h, 'width_px':w}
    test_common_params = {'max_iterations': max_i, 'escape_radius': er_val, 'image_height_px':h, 'image_width_px':w}

    # デフォルトのアルゴリズムパラメータを取得
    default_algo_params = {}
    for param_def in plugin.get_parameters_definition():
        default_algo_params[param_def['name']] = param_def['default']

    # カラーマップでテスト
    test_color_map = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255), (255,0,255)]

    logger.log("\n指定したカラーマップを使用してカラーリングを適用するテスト...", level="INFO")
    colored_img = plugin.apply_coloring(test_fractal_data, test_common_params, default_algo_params, test_color_map)
    logger.log(f"  生成されたカラー画像の形状: {colored_img.shape}", level="INFO")
    assert colored_img.shape == (h,w,4)

    # カラーマップなしでテスト (デフォルトのグレースケールを使用するはずです)
    logger.log("\nカラーマップなし (None) でカラーリングを適用するテスト (デフォルトのグレースケールが使用されるはずです)...", level="INFO")
    colored_img_no_map = plugin.apply_coloring(test_fractal_data, test_common_params, default_algo_params, None)
    logger.log(f"  生成されたカラー画像 (マップなし) の形状: {colored_img_no_map.shape}", level="INFO")
    assert colored_img_no_map.shape == (h,w,4)

    # 集合内の点 (中央に配置した点) が黒色であるかを確認
    assert np.array_equal(colored_img[h//2, w//2, :3], [0,0,0]), "集合内の中心点が黒色ではありません。"

    # 最小限のカラーマップ (長さ2) でテスト
    min_color_map = [(255,0,0), (0,0,255)]
    logger.log("\n最小限のカラーマップ (2色) を使用してカラーリングを適用するテスト...", level="INFO")
    colored_img_min_map = plugin.apply_coloring(test_fractal_data, test_common_params, default_algo_params, min_color_map)
    logger.log(f"  生成されたカラー画像 (最小マップ) の形状: {colored_img_min_map.shape}", level="INFO")
    assert colored_img_min_map.shape == (h,w,4)

    # 問題のある last_z_mod_sq 値 (例: 非常に小さい、または係数が <= 1) でテスト
    # これは smooth_val 計算の堅牢性をテストします
    logger.log("\n潜在的に問題のある |Z|^2 値 (例: <= 1.0) を使用してカラーリングを適用するテスト...", level="INFO")
    problem_mod_sq = np.copy(test_mod_sq)
    # |Z|^2 が <= 1.0 となるような値をいくつか導入 (これにより log(log(|Z|)) が未定義になる可能性がある)
    problem_mod_sq[0,0] = 0.5 # |Z|^2 < 1
    problem_mod_sq[0,1] = 0.0 # |Z|^2 = 0
    test_iters[0,0] = 10 # これらの点が発散した点であることを確認 (max_i より小さい)
    test_iters[0,1] = 10
    problem_fractal_data = {'iterations': test_iters, 'last_z_modulus_sq': problem_mod_sq, 'height_px':h, 'width_px':w}
    colored_img_problem = plugin.apply_coloring(problem_fractal_data, test_common_params, default_algo_params, test_color_map)
    logger.log(f"  生成されたカラー画像 (問題のある|Z|^2値) の形状: {colored_img_problem.shape}", level="INFO")
    assert colored_img_problem.shape == (h,w,4)
    # 主な確認事項は、これらの値でクラッシュせずに画像を生成できることです。
    # ピクセル (0,0) と (0,1) は、smooth_val が float(iters) にフォールバックするため、整数反復に基づいた色になるはずです。

    logger.log("\nSmoothColoringPlugin のテストが正常に完了しました。", level="INFO")
