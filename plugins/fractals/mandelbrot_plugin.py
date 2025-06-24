import numpy as np
from numba import jit, prange
from plugins.base_fractal_plugin import FractalPlugin
from logger.custom_logger import CustomLogger # logger がプロジェクトルート/loggerにあると仮定

logger = CustomLogger()

@jit(nopython=True)
def _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq):
    """
    マンデルブロ集合の単一の点に対する計算をJITコンパイルで実行します。

    Args:
        c_real (float): 複素数cの実数部。
        c_imag (float): 複素数cの虚数部。
        max_iters (int): 最大反復回数。
        escape_radius_sq (float): 発散とみなすための半径の2乗。

    Returns:
        tuple[int, float, float]: (反復回数, 最後のzの実数部, 最後のzの虚数部)。
    """
    z_real = 0.0
    z_imag = 0.0
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        mod_sq = z_real_sq + z_imag_sq
        if mod_sq > escape_radius_sq:
            return i, z_real, z_imag # 反復回数、最後のz_real、最後のz_imagを返す

        new_z_imag = 2.0 * z_real * z_imag + c_imag
        z_real = z_real_sq - z_imag_sq + c_real
        z_imag = new_z_imag
    # 収束したか、最大反復回数に到達した
    return max_iters, z_real, z_imag

@jit(nopython=True, parallel=True)
def _compute_mandelbrot_grid_jit(width_px, height_px, min_x, max_x, min_y, max_y, max_iters, escape_radius_sq):
    """
    指定されたグリッドのマンデルブロ集合をJITコンパイルで並列計算します。

    Args:
        width_px (int): 画像の幅（ピクセル）。
        height_px (int): 画像の高さ（ピクセル）。
        min_x (float): 複素平面のx軸の最小値。
        max_x (float): 複素平面のx軸の最大値。
        min_y (float): 複素平面のy軸の最小値。
        max_y (float): 複素平面のy軸の最大値。
        max_iters (int): 最大反復回数。
        escape_radius_sq (float): 発散とみなすための半径の2乗。

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray]: (反復回数の配列, 最後のzの実数部の配列, 最後のzの虚数部の配列)。
    """
    iter_result = np.empty((height_px, width_px), dtype=np.int32)
    last_z_real_result = np.empty((height_px, width_px), dtype=np.float64)
    last_z_imag_result = np.empty((height_px, width_px), dtype=np.float64)

    pixel_width_complex = (max_x - min_x) / width_px
    pixel_height_complex = (max_y - min_y) / height_px

    for y_idx in prange(height_px): # prangeを使用して並列化を明示
        c_imag = min_y + y_idx * pixel_height_complex
        for x_idx in range(width_px):
            c_real = min_x + x_idx * pixel_width_complex
            iter_val, last_zr, last_zi = _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq)
            iter_result[y_idx, x_idx] = iter_val
            last_z_real_result[y_idx, x_idx] = last_zr
            last_z_imag_result[y_idx, x_idx] = last_zi
    return iter_result, last_z_real_result, last_z_imag_result


class MandelbrotPlugin(FractalPlugin):
    """マンデルブロ集合を計算するためのフラクタルプラグイン。"""
    @property
    def name(self) -> str:
        """プラグインの名前を返します。"""
        return "Mandelbrot"

    def get_parameters_definition(self) -> list:
        """このフラクタルに固有のパラメータ定義を返します。"""
        return []

    def get_default_view_parameters(self) -> dict:
        """デフォルトのビューパラメータを返します。"""
        return {
            'center_real': -0.5,
            'center_imag': 0.0,
            'width': 3.0,
        }

    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> dict:
        """
        指定されたパラメータに基づいてマンデルブロ集合を計算します。

        Args:
            common_params (dict): すべてのフラクタルに共通のパラメータ。
            plugin_params (dict): このフラクタルに固有のパラメータ。
            image_width_px (int): 生成する画像の幅（ピクセル）。
            image_height_px (int): 生成する画像の高さ（ピクセル）。

        Returns:
            dict: 計算結果。'iterations', 'last_zn_values', 'last_z_modulus_sq', 'is_diverged' を含みます。
        """
        center_real = common_params['center_real']
        center_imag = common_params['center_imag']
        width = common_params['width']
        height = common_params['height']
        max_iterations = common_params['max_iterations']
        escape_radius = common_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        min_x = center_real - width / 2.0
        max_x = center_real + width / 2.0
        min_y = center_imag - height / 2.0
        max_y = center_imag + height / 2.0

        logger.log(f"計算開始 - 画像: {image_width_px}x{image_height_px}px, "
              f"複素領域: 実数部 ({min_x:.4f} から {max_x:.4f}), 虚数部 ({min_y:.4f} から {max_y:.4f}), "
              f"最大反復回数: {max_iterations}", level="INFO")

        iter_array, last_z_real_array, last_z_imag_array = _compute_mandelbrot_grid_jit(
            image_width_px, image_height_px,
            min_x, max_x, min_y, max_y,
            max_iterations, escape_radius_sq
        )

        last_zn_values_complex = last_z_real_array + 1j * last_z_imag_array
        last_z_modulus_sq = np.abs(last_zn_values_complex)**2 # |Z|^2 を計算

        is_diverged = iter_array < max_iterations

        logger.log(f"計算完了。反復回数配列形状: {iter_array.shape}, last_zn_values形状: {last_zn_values_complex.shape}", level="DEBUG")
        return {
            'iterations': iter_array,
            'last_zn_values': last_zn_values_complex, # 他の用途や互換性のために保持
            'last_z_modulus_sq': last_z_modulus_sq,    # スムーズな色付けのために追加
            'is_diverged': is_diverged
        }

if __name__ == '__main__':
    plugin = MandelbrotPlugin()
    logger.log(f"プラグイン名: {plugin.name}", level="INFO")
    logger.log(f"パラメータ定義: {plugin.get_parameters_definition()}", level="INFO")
    logger.log(f"デフォルトビューパラメータ: {plugin.get_default_view_parameters()}", level="INFO")

    test_common_params = {
        'center_real': -0.5,
        'center_imag': 0.0,
        'width': 3.0,
        'height': 2.0,
        'max_iterations': 60,
        'escape_radius': 2.0
    }
    test_plugin_params = {}

    img_width_test, img_height_test = 160, 120

    logger.log(f"\ncompute_fractal ({img_width_test}x{img_height_test}) をテスト中...", level="INFO")
    fractal_result_data = plugin.compute_fractal(test_common_params, test_plugin_params, img_width_test, img_height_test)

    iter_result_array = fractal_result_data['iterations']
    last_zn_values_array = fractal_result_data['last_zn_values']

    logger.log(f"  反復回数配列形状: {iter_result_array.shape}, dtype: {iter_result_array.dtype}", level="DEBUG")
    logger.log(f"  last_zn_values 配列形状: {last_zn_values_array.shape}, dtype: {last_zn_values_array.dtype}", level="DEBUG")

    center_y, center_x = img_height_test // 2, img_width_test // 2
    if iter_result_array[center_y, center_x] == test_common_params['max_iterations']:
        logger.log(f"  中心点の反復回数チェック: 成功 (値: {iter_result_array[center_y, center_x]})", level="INFO")
        logger.log(f"  中心点のlast_zn値: {last_zn_values_array[center_y, center_x]}", level="DEBUG")
    else:
        logger.log(f"  中心点の反復回数チェック: 失敗または最大反復回数ではない (値: {iter_result_array[center_y, center_x]}), last_zn: {last_zn_values_array[center_y, center_x]}", level="WARNING")

    try:
        import matplotlib.pyplot as plt
        plt.imshow(iter_result_array, cmap='magma', extent=(
            test_common_params['center_real'] - test_common_params['width']/2,
            test_common_params['center_real'] + test_common_params['width']/2,
            test_common_params['center_imag'] - test_common_params['height']/2,
            test_common_params['center_imag'] + test_common_params['height']/2
        ))
        plt.colorbar(label="反復回数")
        plt.title(f"{plugin.name} 反復回数テスト ({img_width_test}x{img_height_test})")
        plt.xlabel("実数部")
        plt.ylabel("虚数部")
        plt.show()
    except ImportError:
        logger.log("matplotlibが見つかりません。画像表示テストをスキップします。", level="INFO")

    logger.log("\nMandelbrotPlugin のテストが完了しました。", level="INFO")
