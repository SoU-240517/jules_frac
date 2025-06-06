import numpy as np
from numba import jit

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
    print("警告: grayscale_coloring_plugin.py で CustomLogger をインポートできませんでした。標準のprintを使用します。")
    class PrintLogger: # シンプルなフォールバックロガーを定義
        def log(self, message, level="INFO"): print(f"[{level}] {message}") # ログレベルとメッセージを出力
    logger = PrintLogger()


# Numba JITコンパイル済みヘルパー関数
@jit(nopython=True)
def _apply_grayscale_coloring_jit(iterations_array: np.ndarray, max_iters: int) -> np.ndarray:
    """
    反復回数に基づいてグレースケールカラーリングを適用するJITコンパイル済み関数。

    Args:
        iterations_array (np.ndarray): 各点の反復回数を格納した配列。
        max_iters (int): 最大反復回数。

    Returns:
        np.ndarray: RGBA形式のカラーリング済み画像データ。
    """
    height, width = iterations_array.shape
    colored_image_rgba = np.empty((height, width, 4), dtype=np.uint8)

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]
            if iters == max_iters:  # 点は集合内に存在します
                colored_image_rgba[r_idx, c_idx, 0] = 0  # R
                colored_image_rgba[r_idx, c_idx, 1] = 0  # G
                colored_image_rgba[r_idx, c_idx, 2] = 0  # B
            else: # 点は発散しました
                # 線形グレースケール: 0反復 -> 黒, max_iters-1 -> 白 (または白に近い)
                # より速く発散する点を暗くする場合:
                # gray_value = int((iters / max_iters) * 255)
                # より速く発散する点を明るくする場合 (詳細表示でよく好まれます):
                gray_value = int((1.0 - (iters / max_iters)) * 255)

                gray_value = max(0, min(255, gray_value)) # 値を [0, 255] の範囲にクランプします

                colored_image_rgba[r_idx, c_idx, 0] = np.uint8(gray_value)
                colored_image_rgba[r_idx, c_idx, 1] = np.uint8(gray_value)
                colored_image_rgba[r_idx, c_idx, 2] = np.uint8(gray_value)
            colored_image_rgba[r_idx, c_idx, 3] = 255  # アルファチャンネル (完全に不透明に設定)
    return colored_image_rgba


class GrayscaleColoringPlugin(ColoringAlgorithmPlugin):
    """
    エスケープ時間に基づいてグレースケールを適用するシンプルなカラーリングプラグインです。
    """

    @property
    def name(self) -> str:
        """カラーリングアルゴリズムの名前を返します。"""
        return "グレースケール (標準)"

    def get_parameters_definition(self) -> list:
        """このカラーリングアルゴリズムに固有の調整可能なパラメータのリストを返します。"""
        return []

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict,  # このプラグインでは現在使用されていません
        color_map_data: list[tuple[int, int, int]] | None # このプラグインでは使用されません
    ) -> np.ndarray:
        """
        反復回数に基づいてグレースケールカラーリングを適用します。
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

        # logger.log(f"GrayscaleColoringPlugin: グレースケールカラーリングを適用中。最大反復回数: {max_iters}。", level="DEBUG") # 詳細ログ用

        colored_image = _apply_grayscale_coloring_jit(iterations, max_iters)

        # logger.log(f"GrayscaleColoringPlugin: カラーリング完了。出力画像の形状: {colored_image.shape}", level="DEBUG") # 詳細ログ用
        return colored_image

if __name__ == '__main__':
    logger.log("GrayscaleColoringPlugin のテストを開始します...", level="INFO")
    plugin = GrayscaleColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}", level="INFO")
    logger.log(f"パラメータ定義: {plugin.get_parameters_definition()}", level="INFO")

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
    test_algorithm_params = {} # このプラグインには固有のアルゴリズムパラメータはありません
    test_color_map = None      # このプラグインはカラーマップを使用しません

    logger.log("\napply_coloring メソッドのテストを実行中...", level="INFO")
    result_image_data = plugin.apply_coloring(
        test_fractal_data,
        test_common_fractal_params,
        test_algorithm_params,
        test_color_map
    )
    logger.log(f"  生成された画像の形状: {result_image_data.shape}", level="INFO")
    assert result_image_data.shape == (3, 3, 4) # 高さ, 幅, RGBA

    logger.log("  生成された画像データのピクセル値を検証中 (RGBコンポーネント):", level="INFO")

    for r in range(test_iterations_data.shape[0]):
        for c in range(test_iterations_data.shape[1]):
            iter_val = test_iterations_data[r,c]
            rgb_val = result_image_data[r,c,:3]
            alpha_val = result_image_data[r,c,3]

            if iter_val == test_common_fractal_params['max_iterations']:
                expected_rgb = np.array([0,0,0], dtype=np.uint8)
            else:
                # テスト対象のロジックは `(1.0 - (iters / max_iters)) * 255` なので、それに合わせる
                val = int((1.0 - (iter_val / test_common_fractal_params['max_iterations'])) * 255)
                val = max(0, min(255, val))
                expected_rgb = np.array([val, val, val], dtype=np.uint8)

            logger.log(f"    ピクセル({r},{c}): 反復回数={iter_val}, RGBA={result_image_data[r,c]}, 期待RGB={expected_rgb}", level="DEBUG")
            assert np.array_equal(rgb_val, expected_rgb), f"ピクセル ({r},{c}) のRGB値が期待値と一致しません。"
            assert alpha_val == 255, f"ピクセル ({r},{c}) のアルファ値が255ではありません。"

    logger.log("  すべてのピクセルチェックが成功しました。", level="INFO")
    logger.log("\nGrayscaleColoringPlugin のテストが正常に完了しました。", level="INFO")
