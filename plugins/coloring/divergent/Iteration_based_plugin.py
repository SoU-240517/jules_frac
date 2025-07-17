import numpy as np
from numba import jit
import math

try:
    from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
except ImportError:
    # このフォールバックは、プロジェクト構造が一貫しており、
    # 実行ポイントが常にプロジェクトルートである場合は不要かもしれません。
    from base_coloring_plugin import ColoringAlgorithmPlugin

# CustomLoggerをインポート - プロジェクトルートのloggerディレクトリにあると仮定
import sys
from pathlib import Path
# このスクリプトが自身のフォルダから直接実行された場合、または
# 他の理由でpluginsフォルダがsys.pathに追加された場合にloggerが見つかるようにする
_logger_path_finder = Path(__file__).resolve()
# plugins/coloring -> plugins -> ルート (jules_frac) のように上位へ移動
_project_root_for_logger = _logger_path_finder.parent.parent.parent
if str(_project_root_for_logger) not in sys.path:
    sys.path.insert(0, str(_project_root_for_logger))
try:
    from logger.custom_logger import CustomLogger
    logger = CustomLogger()
except ImportError:
    # loggerをインポートできない場合のフォールバック (例: 特定の実行コンテキストでのパスの問題など)
    print("警告: Iteration_based_plugin.py で CustomLogger をインポートできませんでした。標準のprintを使用します。")
    class PrintLogger: # シンプルなフォールバックロガーを定義
        def log(self, message, level="INFO"): print(f"[{level}] {message}") # ログレベルとメッセージを出力
    logger = PrintLogger()


# Numba JITコンパイル済みヘルパー関数
@jit(nopython=True)
def _apply_iteration_based_coloring_jit(
    iterations_array: np.ndarray,
    max_iters: int,
    color_map: np.ndarray,
    color_scale_factor: float
) -> np.ndarray:
    """
    反復回数とカラーマップに基づいてカラーリングを適用するJITコンパイル済み関数。

    Args:
        iterations_array (np.ndarray): 各点の反復回数を格納した配列。
        max_iters (int): 最大反復回数。
        color_map (np.ndarray): 色補間に使用するカラーマップ (形状: (N,3), dtype: uint8)。
        color_scale_factor (float): 色の変化の速さを調整するスケールファクター。
    Returns:
        np.ndarray: RGBA形式のカラーリング済み画像データ。
    """
    height, width = iterations_array.shape
    colored_image_rgba = np.empty((height, width, 4), dtype=np.uint8)

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]
            colored_image_rgba[r_idx, c_idx, 3] = 255  # アルファチャンネル (完全に不透明に設定)

            if iters == max_iters:  # 点は集合内に存在します
                colored_image_rgba[r_idx, c_idx, 0] = 0  # R
                colored_image_rgba[r_idx, c_idx, 1] = 0  # G
                colored_image_rgba[r_idx, c_idx, 2] = 0  # B
            else: # 点は発散しました
                if color_map.shape[0] < 2: # カラーマップの色が不足している場合
                    # デフォルトのグレースケールのような動作（黒から白へ）
                    gray_value = int((1.0 - (iters / max_iters)) * 255)
                    gray_value = max(0, min(255, gray_value))
                    colored_image_rgba[r_idx, c_idx, 0] = np.uint8(gray_value)
                    colored_image_rgba[r_idx, c_idx, 1] = np.uint8(gray_value)
                    colored_image_rgba[r_idx, c_idx, 2] = np.uint8(gray_value)
                else:
                    # カラーマップを使用
                    # iters を [0, 1) の範囲に正規化し、スケールを適用
                    # iters が 0 から max_iters-1 の範囲で変化すると仮定
                    # (max_iters の場合は既に処理済み)
                    normalized_iter = iters / max_iters # 0に近いほど早く発散

                    # スムーズなカラーリングと同様のインデックス計算と補間
                    # (1.0 - normalized_iter) を使うと、早く発散する点がカラーマップの最初の色に近くなる
                    color_idx_float = (1.0 - normalized_iter) * (color_map.shape[0] -1) * color_scale_factor

                    idx0_floor = math.floor(color_idx_float)
                    fraction = color_idx_float - idx0_floor

                    c1_idx = int(idx0_floor) % color_map.shape[0]
                    c2_idx = (int(idx0_floor) + 1) % color_map.shape[0]

                    c1 = color_map[c1_idx]
                    c2 = color_map[c2_idx]
                    # RGBA対応: 4要素ならRGBのみ使う
                    if c1.shape[0] == 4:
                        c1_r, c1_g, c1_b = c1[0], c1[1], c1[2]
                        c2_r, c2_g, c2_b = c2[0], c2[1], c2[2]
                    else:
                        c1_r, c1_g, c1_b = c1[0], c1[1], c1[2]
                        c2_r, c2_g, c2_b = c2[0], c2[1], c2[2]

                    r_val = c1_r * (1.0 - fraction) + c2_r * fraction
                    g_val = c1_g * (1.0 - fraction) + c2_g * fraction
                    b_val = c1_b * (1.0 - fraction) + c2_b * fraction

                    colored_image_rgba[r_idx, c_idx, 0] = np.uint8(max(0.0, min(255.0, r_val)))
                    colored_image_rgba[r_idx, c_idx, 1] = np.uint8(max(0.0, min(255.0, g_val)))
                    colored_image_rgba[r_idx, c_idx, 2] = np.uint8(max(0.0, min(255.0, b_val)))
    return colored_image_rgba


class IterationBasedColoringPlugin(ColoringAlgorithmPlugin):
    """
    エスケープ時間に基づいてグレースケールを適用するシンプルなカラーリングプラグインです。
    """

    @property
    def name(self) -> str:
        """カラーリングアルゴリズムの名前を返します。"""
        return "反復回数ベース" # 名前を変更して機能を反映

    def get_parameters_definition(self) -> list:
        """このカラーリングアルゴリズムに固有の調整可能なパラメータのリストを返します。"""
        return [
            {'name': 'color_scale', 'label': '色のスケール',
             'type': 'float', 'default': 1.0, 'range': (0.01, 100.0), 'step': 0.01,
             'tooltip': '色の変化の速さを調整します。大きいほど色が細かく変化します。'}
        ]

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict,
        color_map_data: list[tuple[int, int, int]] | None
    ) -> np.ndarray:
        """
        反復回数と提供されたカラーマップに基づいてカラーリングを適用します。
        カラーマップが提供されない場合、または色数が不十分な場合は、
        デフォルトのグレースケール（黒から白）で描画します。
        """
        iterations = fractal_data.get('iterations')
        if iterations is None:
            # フォールバック: 'iterations' データが存在しない場合は、黒い画像を返します。
            # 本来は、呼び出し側が有効な fractal_data を提供することを保証すべきです。
            height_px = common_fractal_params.get('image_height_px', 100) # デフォルトは100
            width_px = common_fractal_params.get('image_width_px', 100)   # デフォルトは100
            logger.log("必須データ 'iterations' が見つかりません。黒い画像を返します。", level="WARNING")
            fallback_image = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_image[:, :, 3] = 255 # アルファチャンネルを不透明に設定
            return fallback_image

        max_iters = common_fractal_params.get('max_iterations', 100) # max_iterations が提供されない場合のデフォルト値

        color_scale_from_plugin = algorithm_params.get('color_scale', 1.0)

        if not color_map_data or len(color_map_data) < 2:
            logger.log(f"{self.name}: カラーマップが不十分なため、デフォルトのグレースケールマップを使用します。", level="DEBUG")
            # デフォルトのグレースケールマップ (黒から白へ)
            # JIT関数内でこのケースを処理するため、ここでは単純な2色マップを渡すか、
            # JIT関数が color_map.shape[0] < 2 をチェックするようにします。
            # ここでは、JIT関数が処理しやすいように、有効な（ただし最小限の）グレースケールマップを作成します。
            # または、JIT関数内で color_map.shape[0] < 2 の場合のフォールバックロジックを強化します。
            # 現在のJIT関数は color_map.shape[0] < 2 の場合にグレースケール処理を行うため、
            # ここでは空の配列ではなく、それをトリガーするようなものを渡すか、明示的なフラグを渡す必要があります。
            # 簡単のため、JIT関数に渡す color_map_np は常に有効な形状とし、JIT内で色数をチェックします。
            color_map_np = np.array([[0,0,0],[255,255,255]], dtype=np.uint8) # JITが扱う最小限のマップ
        else:
            color_map_np = np.array(color_map_data, dtype=np.uint8)
            # RGBA(4要素)にも対応: shape[1]が3または4ならOK
            if color_map_np.ndim == 2 and (color_map_np.shape[1] == 3 or color_map_np.shape[1] == 4):
                pass # OK
            else:
                # それ以外は強制的にRGB2色にする
                color_map_np = np.array([[0,0,0],[255,255,255]], dtype=np.uint8)
        colored_image = _apply_iteration_based_coloring_jit(iterations, max_iters, color_map_np, color_scale_from_plugin)
        return colored_image

if __name__ == '__main__':
    logger.log("IterationBasedColoringPlugin のテストを開始します...", level="INFO")
    plugin = IterationBasedColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}", level="INFO")
    logger.log(f"パラメータ定義: {plugin.get_parameters_definition()}", level="INFO")

    default_algo_params = {}
    for param_def in plugin.get_parameters_definition():
        default_algo_params[param_def['name']] = param_def['default']

    # テスト用の反復回数データ
    test_iterations_data = np.array([
        [50, 10, 0],   # 行 0
        [5, 50, 20],   # 行 1
        [0, 15, 50]    # 行 2
    ], dtype=np.int32)

    # apply_coloring のフォールバックケースのために fractal_data に高さ/幅を追加
    test_fractal_data = {'iterations': test_iterations_data,
                         'height_px': test_iterations_data.shape[0],
                         'width_px': test_iterations_data.shape[1]}

    test_common_fractal_params = {'max_iterations': 50}

    # 1. カラーマップなし (デフォルトのグレースケール動作を期待)
    logger.log("\napply_coloring メソッドのテスト (カラーマップなし)...", level="INFO")
    result_image_data_no_map = plugin.apply_coloring(
        test_fractal_data,
        test_common_fractal_params,
        default_algo_params, # color_scale = 1.0
        None # カラーマップなし
    )
    logger.log(f"  生成された画像の形状 (カラーマップなし): {result_image_data_no_map.shape}", level="INFO")
    assert result_image_data_no_map.shape == (3, 3, 4)
    # (50, 50, 50) が max_iters なので黒 [0,0,0]
    # (10, 50, ?) -> (1 - 10/50)*255 = (1 - 0.2)*255 = 0.8*255 = 204. [204,204,204]
    # (0, 50, ?) -> (1 - 0/50)*255 = 1.0*255 = 255. [255,255,255]
    assert np.array_equal(result_image_data_no_map[0,0,:3], [0,0,0]) # iters = 50 (max_iters)
    assert np.array_equal(result_image_data_no_map[0,1,:3], [204,204,204]) # iters = 10
    assert np.array_equal(result_image_data_no_map[0,2,:3], [255,255,255]) # iters = 0
    logger.log("  カラーマップなしのテスト完了。", level="INFO")

    # 2. カラーマップあり
    test_color_map_data = [(255,0,0), (0,255,0), (0,0,255)] # R, G, B
    logger.log(f"\napply_coloring メソッドのテスト (カラーマップ: {test_color_map_data})...", level="INFO")
    result_image_data = plugin.apply_coloring(
        test_fractal_data,
        test_common_fractal_params,
        default_algo_params, # color_scale = 1.0
        test_color_map_data
    )
    logger.log(f"  生成された画像の形状: {result_image_data.shape}", level="INFO")
    assert result_image_data.shape == (3, 3, 4) # 高さ, 幅, RGBA

    # 検証 (color_scale = 1.0, num_colors = 3)
    # iters = 50 (max_iters) -> 黒 [0,0,0]
    # iters = 10 (max_iters=50). normalized_iter = 10/50 = 0.2.
    #   color_idx_float = (1.0 - 0.2) * (3-1) * 1.0 = 0.8 * 2 = 1.6
    #   idx0 = 1, fraction = 0.6. c1_idx=1 (G), c2_idx=2 (B)
    #   Color = G*(1-0.6) + B*0.6 = (0,255,0)*0.4 + (0,0,255)*0.6 = (0, 102, 0) + (0,0,153) = (0,102,153) (四捨五入で調整)
    #   (0, round(255*0.4), round(255*0.6)) = (0, 102, 153)
    # iters = 0. normalized_iter = 0.0
    #   color_idx_float = (1.0 - 0.0) * (3-1) * 1.0 = 1.0 * 2 = 2.0
    #   idx0 = 2, fraction = 0.0. c1_idx=2 (B), c2_idx=0 (R) (剰余のため)
    #   Color = B*(1-0) + R*0 = B = (0,0,255)

    logger.log(f"    ピクセル(0,0) iters=50: {result_image_data[0,0,:3]} (期待値: [0,0,0])", level="DEBUG")
    assert np.array_equal(result_image_data[0,0,:3], [0,0,0])

    logger.log(f"    ピクセル(0,1) iters=10: {result_image_data[0,1,:3]} (期待値に近いか: [0,102,153])", level="DEBUG")
    assert np.allclose(result_image_data[0,1,:3], [0,102,153], atol=1) # 浮動小数点計算の誤差を許容

    logger.log(f"    ピクセル(0,2) iters=0: {result_image_data[0,2,:3]} (期待値: [0,0,255])", level="DEBUG")
    assert np.array_equal(result_image_data[0,2,:3], [0,0,255])

    logger.log("  カラーマップありのテスト完了。", level="INFO")
    logger.log("\nIterationBasedColoringPlugin のテストが正常に完了しました。", level="INFO")
