import numpy as np
from numba import jit

from plugins.base_fractal_plugin import FractalPlugin
from logger.custom_logger import CustomLogger # logger がプロジェクトルート/loggerにあると仮定

logger = CustomLogger()

    # @jit(nopython=True, cache=True) # Numba JITを一時的に無効化
def _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq):
    z_real = 0.0
    z_imag = 0.0
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        mod_sq = z_real_sq + z_imag_sq
        if mod_sq > escape_radius_sq:
            return i, mod_sq # 発散時に反復回数と|Z|^2を返す

        new_z_imag = 2.0 * z_real * z_imag + c_imag
        z_real = z_real_sq - z_imag_sq + c_real
        z_imag = new_z_imag
    # 収束したか最大反復回数に達した場合は、|Z|^2に0.0を返す (または必要に応じて別の指標)
    return max_iters, 0.0

    # @jit(nopython=True, cache=True, parallel=True) # Numba JITを一時的に無効化
def _compute_mandelbrot_grid_jit(width_px, height_px, min_x, max_x, min_y, max_y, max_iters, escape_radius_sq):
    iter_result = np.empty((height_px, width_px), dtype=np.int32)
    mod_sq_result = np.empty((height_px, width_px), dtype=np.float64) # |Z|^2用

    pixel_width_complex = (max_x - min_x) / width_px
    pixel_height_complex = (max_y - min_y) / height_px

    for y_idx in range(height_px):
        c_imag = min_y + y_idx * pixel_height_complex
        for x_idx in range(width_px):
            c_real = min_x + x_idx * pixel_width_complex
            iter_val, mod_sq_val = _calculate_mandelbrot_point_jit(c_real, c_imag, max_iters, escape_radius_sq)
            iter_result[y_idx, x_idx] = iter_val
            mod_sq_result[y_idx, x_idx] = mod_sq_val
    return iter_result, mod_sq_result


class MandelbrotPlugin(FractalPlugin):
    @property
    def name(self) -> str:
        return "Mandelbrot"

    def get_parameters_definition(self) -> list:
        return []

    def get_default_view_parameters(self) -> dict:
        return {
            'center_real': -0.5,
            'center_imag': 0.0,
            'width': 3.0,
        }

    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> dict:
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
              f"最大反復回数: {max_iterations}", level="DEBUG")

        iter_array, mod_sq_array = _compute_mandelbrot_grid_jit(
            image_width_px, image_height_px,
            min_x, max_x, min_y, max_y,
            max_iterations, escape_radius_sq
        )

        logger.log(f"計算完了。反復回数配列形状: {iter_array.shape}, ModSq形状: {mod_sq_array.shape}", level="DEBUG")
        return {'iterations': iter_array, 'last_z_modulus_sq': mod_sq_array}

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
    mod_sq_result_array = fractal_result_data['last_z_modulus_sq']

    logger.log(f"  反復回数配列形状: {iter_result_array.shape}, dtype: {iter_result_array.dtype}", level="DEBUG")
    logger.log(f"  |Z|^2 配列形状: {mod_sq_result_array.shape}, dtype: {mod_sq_result_array.dtype}", level="DEBUG")

    center_y, center_x = img_height_test // 2, img_width_test // 2
    if iter_result_array[center_y, center_x] == test_common_params['max_iterations']:
        logger.log(f"  中心点の反復回数チェック: 成功 (値: {iter_result_array[center_y, center_x]})", level="INFO")
        logger.log(f"  中心点の|Z|^2値: {mod_sq_result_array[center_y, center_x]}", level="DEBUG")
    else:
        logger.log(f"  中心点の反復回数チェック: 失敗または最大反復回数ではない (値: {iter_result_array[center_y, center_x]})", level="WARNING")

    try:
        import matplotlib.pyplot as plt
        plt.imshow(iter_result_array, cmap='magma', extent=(
            test_common_params['center_real'] - test_common_params['width']/2,
            test_common_params['center_real'] + test_common_params['width']/2,
            test_common_params['center_imag'] - test_common_params['height']/2,
            test_common_params['center_imag'] + test_common_params['height']/2
        ))
        plt.colorbar(label="Iterations")
        plt.title(f"{plugin.name} Iterations Test ({img_width_test}x{img_height_test})")
        plt.xlabel("Real")
        plt.ylabel("Imaginary")
        plt.show()
    except ImportError:
        logger.log("matplotlibが見つかりません。画像表示テストをスキップします。", level="INFO")

    logger.log("\nMandelbrotPlugin のテストが完了しました。", level="INFO")
