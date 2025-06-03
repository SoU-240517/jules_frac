import numpy as np
from numba import jit

try:
    from ..base_coloring_plugin import ColoringAlgorithmPlugin
except ImportError:
    # テストまたは直接スクリプト実行のためのフォールバック
    # これは 'base_coloring_plugin.py' が探索可能なパスにあることを前提としています。
    # 堅牢なプロジェクト構造のためには、PYTHONPATH が正しく設定されていることを確認するか、絶対インポートを使用してください。
    from src.app.plugins.base_coloring_plugin import ColoringAlgorithmPlugin


# Numba JITコンパイル済みヘルパー関数 (以前はFractalEngineなどにありました)
@jit(nopython=True)
def _apply_grayscale_coloring_jit(iterations_array: np.ndarray, max_iters: int) -> np.ndarray:
    height, width = iterations_array.shape
    colored_image_rgba = np.empty((height, width, 4), dtype=np.uint8)

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]
            if iters == max_iters:  # 点は集合内にあります
                colored_image_rgba[r_idx, c_idx, 0] = 0  # R
                colored_image_rgba[r_idx, c_idx, 1] = 0  # G
                colored_image_rgba[r_idx, c_idx, 2] = 0  # B
            else: # 点は発散しました
                # 線形グレースケール: 0反復 -> 黒, max_iters-1 -> 白 (または白に近い)
                # より速く発散する点を暗くする場合:
                gray_value = int((iters / max_iters) * 255)
                # より速く発散する点を明るくする場合 (詳細表示でよく好まれます):
                # gray_value = int((1.0 - (iters / max_iters)) * 255)

                gray_value = max(0, min(255, gray_value)) # 値をクランプ

                colored_image_rgba[r_idx, c_idx, 0] = np.uint8(gray_value)
                colored_image_rgba[r_idx, c_idx, 1] = np.uint8(gray_value)
                colored_image_rgba[r_idx, c_idx, 2] = np.uint8(gray_value)
            colored_image_rgba[r_idx, c_idx, 3] = 255  # アルファチャンネル (完全に不透明)
    return colored_image_rgba


class GrayscaleColoringPlugin(ColoringAlgorithmPlugin):
    """
    エスケープ時間に基づいてグレースケールを適用するシンプルなカラーリングプラグインです。
    """

    @property
    def name(self) -> str:
        return "グレースケール (標準)"

    def get_parameters_definition(self) -> list:
        """このアルゴリズムには固有の調整可能なパラメータはありません。"""
        return []

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict,  # このプラグインでは使用されません
        color_map_data: list[tuple[int, int, int]] | None # このプラグインでは使用されません
    ) -> np.ndarray:
        """
        反復回数に基づいてグレースケールカラーリングを適用します。
        """
        iterations = fractal_data.get('iterations')
        if iterations is None:
            # フォールバック: 'iterations' データがない場合は黒い画像を返します。
            # これは理想的には、呼び出し元が有効な fractal_data を保証することで処理されるべきです。
            height_px = fractal_data.get('height_px', 100) # 寸法を取得しようとします
            width_px = fractal_data.get('width_px', 100)
            print("GrayscaleColoringPlugin 警告: 'iterations' データが見つかりません。黒い画像を返します。")
            fallback_image = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_image[:, :, 3] = 255 # アルファを不透明に設定
            return fallback_image

        max_iters = common_fractal_params.get('max_iterations', 100) # 提供されない場合のデフォルト

        # print(f"GrayscaleColoringPlugin: グレースケールカラーリングを適用中。最大反復回数: {max_iters}。") # 詳細ログ

        colored_image = _apply_grayscale_coloring_jit(iterations, max_iters)

        # print(f"GrayscaleColoringPlugin: カラーリング完了。出力形状: {colored_image.shape}") # 詳細ログ
        return colored_image

if __name__ == '__main__':
    print("GrayscaleColoringPlugin のテスト中...")
    plugin = GrayscaleColoringPlugin()
    print(f"プラグイン名: {plugin.name}")
    print(f"パラメータ定義: {plugin.get_parameters_definition()}")

    # テストデータ
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
    test_algorithm_params = {} # このプラグインには固有のパラメータはありません
    test_color_map = None      # このプラグインはカラーマップを使用しません

    print("\napply_coloring テストを実行中...")
    result_image_data = plugin.apply_coloring(
        test_fractal_data,
        test_common_fractal_params,
        test_algorithm_params,
        test_color_map
    )
    print(f"  生成された画像の形状: {result_image_data.shape}")
    assert result_image_data.shape == (3, 3, 4) # 高さ, 幅, RGBA

    print("  生成された画像データ (RGBコンポーネント):")
    expected_values = {
        (0,0): int(50/50*255), # iter=50 (max_iters) -> 'if iters == max_iters' のため黒 (0,0,0)
        (0,1): int(10/50*255), # iter=10 -> グレー値
        (0,2): int(0/50*255),  # iter=0 -> グレー値 (黒)
        (1,0): int(5/50*255),
        (1,1): int(50/50*255), # 黒
        (1,2): int(20/50*255),
        (2,0): int(0/50*255),  # 黒
        (2,1): int(15/50*255),
        (2,2): int(50/50*255)  # 黒
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

            print(f"    ピクセル({r},{c}): Iter={iter_val}, RGBA={result_image_data[r,c]}, 期待RGB={expected_rgb}")
            assert np.array_equal(rgb_val, expected_rgb), f"({r},{c}) で不一致"
            assert alpha_val == 255, f"({r},{c}) でアルファが不正"

    print("  すべてのピクセルチェックが成功しました。")
    print("\nGrayscaleColoringPlugin のテストが完了しました。")
