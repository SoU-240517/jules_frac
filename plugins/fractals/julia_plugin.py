import numpy as np
from numba import jit

from plugins.base_fractal_plugin import FractalPlugin
from logger.custom_logger import CustomLogger # logger がプロジェクトルート/loggerにあると仮定

logger = CustomLogger()
@jit(nopython=True) # cache=True を削除しました
def _calculate_julia_point_jit(z_real_start, z_imag_start, c_real_const, c_imag_const, max_iters, escape_radius_sq):
    z_real = z_real_start
    z_imag = z_imag_start
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        mod_sq = z_real_sq + z_imag_sq
        if mod_sq > escape_radius_sq:
            return i, mod_sq # 反復回数と|Z|^2を返します

        new_z_imag = 2.0 * z_real * z_imag + c_imag_const
        z_real = z_real_sq - z_imag_sq + c_real_const
        z_imag = new_z_imag
    return max_iters, 0.0 # 収束したか、最大反復回数に達しました

@jit(nopython=True) # cache=True を削除しました
def _compute_julia_grid_jit(width_px, height_px, min_x, max_x, min_y, max_y,
                            c_real_const, c_imag_const, max_iters, escape_radius_sq):
    iter_result = np.empty((height_px, width_px), dtype=np.int32)
    mod_sq_result = np.empty((height_px, width_px), dtype=np.float64)

    pixel_width_complex = (max_x - min_x) / width_px
    pixel_height_complex = (max_y - min_y) / height_px

    for y_idx in range(height_px):
        z_imag_start = min_y + y_idx * pixel_height_complex
        for x_idx in range(width_px):
            z_real_start = min_x + x_idx * pixel_width_complex
            iter_val, mod_sq_val = _calculate_julia_point_jit(
                z_real_start, z_imag_start,
                c_real_const, c_imag_const,
                max_iters, escape_radius_sq
            )
            iter_result[y_idx, x_idx] = iter_val
            mod_sq_result[y_idx, x_idx] = mod_sq_val
    return iter_result, mod_sq_result


class JuliaPlugin(FractalPlugin):
    @property
    def name(self) -> str:
        return "Julia"

    def get_parameters_definition(self) -> list:
        return [
            {
                'name': 'c_real',
                'label': 'C (実部)',
                'type': 'float',
                'default': -0.745,
                'range': (-2.0, 2.0),
                'step': 1e-6,  # ステップサイズをより細かく
                'decimals': 7, # 表示する小数点以下の桁数を指定
                'tooltip': 'Julia定数Cの実部'
            },
            {
                'name': 'c_imag',
                'label': 'C (虚部)',
                'type': 'float',
                'default': 0.113,
                'range': (-2.0, 2.0),
                'step': 1e-6,  # ステップサイズをより細かく
                'decimals': 7, # 表示する小数点以下の桁数を指定
                'tooltip': 'Julia定数Cの虚部'
            }
        ]

    def get_default_view_parameters(self) -> dict:
        return {
            'center_real': 0.0,
            'center_imag': 0.0,
            'width': 3.0,
            'max_iterations': 100
        }

    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> dict:
        center_real = common_params['center_real']
        center_imag = common_params['center_imag']
        width = common_params['width']
        height = common_params['height']
        max_iterations = common_params['max_iterations']
        escape_radius = common_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        c_real_const = plugin_params.get('c_real', self.get_parameters_definition()[0]['default'])
        c_imag_const = plugin_params.get('c_imag', self.get_parameters_definition()[1]['default'])

        min_x = center_real - width / 2.0
        max_x = center_real + width / 2.0
        min_y = center_imag - height / 2.0
        max_y = center_imag + height / 2.0

        logger.log(f"計算開始 - C=({c_real_const:.4f} + {c_imag_const:.4f}i), "
              f"画像: {image_width_px}x{image_height_px}px, "
              f"複素領域: 実数部 ({min_x:.4f} から {max_x:.4f}), 虚数部 ({min_y:.4f} から {max_y:.4f}), "
              f"最大反復回数: {max_iterations}", level="DEBUG")

        iter_array, mod_sq_array = _compute_julia_grid_jit(
            image_width_px, image_height_px,
            min_x, max_x, min_y, max_y,
            c_real_const, c_imag_const,
            max_iterations, escape_radius_sq
        )
        logger.log(f"計算完了。反復回数配列形状: {iter_array.shape}, ModSq形状: {mod_sq_array.shape}", level="DEBUG")
        return {'iterations': iter_array, 'last_z_modulus_sq': mod_sq_array}

    def get_presets(self) -> dict | None:
        return {
            "クラシックビューティー": {"c_real": -0.745, "c_imag": 0.113},
            "ファイゲンバウム点": {"c_real": -1.401155, "c_imag": 0.0},
            "シーホース": {"c_real": -0.75, "c_imag": 0.1},
            "ドラゴンテール": {"c_real": -0.8, "c_imag": 0.156},
            "電気ウナギ": {"c_real": -0.162, "c_imag": 1.04},
            "雪の結晶": {"c_real": 0.285, "c_imag": 0.01},
            "スパイラル": {"c_real": -0.778, "c_imag": -0.136},
        }

if __name__ == '__main__':
    plugin = JuliaPlugin()
    logger.log(f"Plugin Name: {plugin.name}", level="INFO")
    param_defs = plugin.get_parameters_definition()
    logger.log(f"Parameter Definitions: {param_defs}", level="INFO")
    logger.log(f"Default View Parameters: {plugin.get_default_view_parameters()}", level="INFO")

    presets = plugin.get_presets()
    logger.log(f"利用可能なプリセット: {list(presets.keys()) if presets else 'なし'}", level="INFO")

    test_common_params = {
        'center_real': 0.0,
        'center_imag': 0.0,
        'width': 3.0,
        'height': 2.25,
        'max_iterations': 150,
        'escape_radius': 2.0
    }

    test_plugin_params = {}
    if presets:
        first_preset_name = list(presets.keys())[0]
        test_plugin_params = presets[first_preset_name]
        logger.log(f"\n計算テストにプリセット '{first_preset_name}' を使用: {test_plugin_params}", level="INFO")
    else:
        for p_def in param_defs:
            test_plugin_params[p_def['name']] = p_def['default']
        logger.log(f"\n計算テストにデフォルトのプラグインパラメータを使用: {test_plugin_params}", level="INFO")

    img_width_test, img_height_test = 160, 120

    logger.log(f"compute_fractal ({img_width_test}x{img_height_test}) をテスト中...", level="INFO")
    fractal_result_data = plugin.compute_fractal(test_common_params, test_plugin_params, img_width_test, img_height_test)

    iter_result_array = fractal_result_data['iterations']
    mod_sq_result_array = fractal_result_data['last_z_modulus_sq']
    logger.log(f"  反復回数配列形状: {iter_result_array.shape}, dtype: {iter_result_array.dtype}", level="DEBUG")
    logger.log(f"  |Z|^2 配列形状: {mod_sq_result_array.shape}, dtype: {mod_sq_result_array.dtype}", level="DEBUG")


    try:
        import matplotlib.pyplot as plt
        plt.imshow(iter_result_array, cmap='magma', extent=(
            test_common_params['center_real'] - test_common_params['width']/2,
            test_common_params['center_real'] + test_common_params['width']/2,
            test_common_params['center_imag'] - test_common_params['height']/2,
            test_common_params['center_imag'] + test_common_params['height']/2
        ))
        plt.colorbar(label="Iterations")
        c_text = f"C=({test_plugin_params.get('c_real',0):.3f} + {test_plugin_params.get('c_imag',0):.3f}i)"
        plt.title(f"{plugin.name} Iterations Test ({img_width_test}x{img_height_test})\n{c_text}")
        plt.xlabel("Real")
        plt.ylabel("Imaginary")
        plt.show()
    except ImportError:
        logger.log("matplotlibが見つかりません。画像表示テストをスキップします。", level="INFO")

    logger.log("\nJuliaPlugin のテストが完了しました。", level="INFO")
