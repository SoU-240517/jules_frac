import numpy as np
from numba import jit
import math

try:
    from ..base_coloring_plugin import ColoringAlgorithmPlugin
except ImportError:
    # テストまたは直接スクリプト実行のためのフォールバック
    from src.app.plugins.base_coloring_plugin import ColoringAlgorithmPlugin

@jit(nopython=True, cache=False, fastmath=True) # ModuleNotFoundErrorに対処するため一時的にキャッシュを無効化
def _apply_smooth_coloring_jit(
    iterations_array: np.ndarray,
    last_z_mod_sq_array: np.ndarray,
    max_iters: int,
    escape_radius_sq: float, # この式では直接使用されていませんが、将来の使用または一貫性のためにパラメータは保持されています
    color_scale_factor: float,
    color_map: np.ndarray # Shape (N, 3), dtype=uint8
) -> np.ndarray:
    height, width = iterations_array.shape
    output_image_rgba = np.empty((height, width, 4), dtype=np.uint8)
    output_image_rgba[:, :, 3] = 255 # アルファチャンネルを完全に不透明に設定

    num_colors_in_map = color_map.shape[0]
    # 補間には少なくとも2色を確保してください。そうでない場合は黒にフォールバックします。
    # これは理想的には、color_map_data の呼び出し側Pythonコードのロジックによって保証されるべきです。
    if num_colors_in_map < 2:
        output_image_rgba[:, :, 0:3] = 0
        return output_image_rgba

    log_2 = math.log(2.0) # log(2)を事前計算

    for r_idx in range(height):
        for c_idx in range(width):
            iters = iterations_array[r_idx, c_idx]

            if iters == max_iters: # 点は集合内にあります
                output_image_rgba[r_idx, c_idx, 0:3] = 0 # 黒
            else:
                mod_sq = last_z_mod_sq_array[r_idx, c_idx]
                smooth_val: float
                try:
                    # 発散した点の場合、mod_sq は escape_radius_sq より大きくなるはずです (例: 半径2の場合 > 4.0)。
                    # これは mod_sq > 0 を意味します。
                    if mod_sq <= 0.0: # 正しく発散した点では発生しないはずです
                        smooth_val = float(iters)
                    else:
                        modulus = math.sqrt(mod_sq) # |Z|
                        # escape_radius > 1 (例: 2) の場合、modulus > 1 です。
                        if modulus <= 1.0: # escape_radius > 1 の場合は発生しないはずです
                            # |Z| <= 1 の場合、log(|Z|) <= 0 となり、log(log(|Z|)) が問題になります。
                            smooth_val = float(iters)
                        else:
                            log_of_modulus = math.log(modulus) # log(|Z|)
                            # modulus > 1 なので、log_of_modulus > 0 です。
                            # log(log_of_modulus) の項は有効です。
                            smooth_val = float(iters) + 1.0 - math.log(log_of_modulus) / log_2
                except Exception: # 数学エラー (予期しない極端な値など) をキャッチします
                    # 計算エラーが発生した場合は整数反復にフォールバックします
                    smooth_val = float(iters)

                # smooth_val をカラーインデックスにマッピングします
                color_idx_float = smooth_val * color_scale_factor

                # マップ内の2色間の線形補間
                idx0_floor = math.floor(color_idx_float)
                fraction = color_idx_float - idx0_floor # fraction は常に [0, 1) の範囲になります

                # 配列アクセス用にインデックスが整数であることを確認し、floor の負の結果を剰余で正しく処理します
                c1_idx = int(idx0_floor) % num_colors_in_map
                c2_idx = (int(idx0_floor) + 1) % num_colors_in_map

                r_val = color_map[c1_idx, 0] * (1.0 - fraction) + color_map[c2_idx, 0] * fraction
                g_val = color_map[c1_idx, 1] * (1.0 - fraction) + color_map[c2_idx, 1] * fraction
                b_val = color_map[c1_idx, 2] * (1.0 - fraction) + color_map[c2_idx, 2] * fraction

                # uint8 に変換する前にカラー値を [0, 255] にクランプします
                output_image_rgba[r_idx, c_idx, 0] = np.uint8(max(0.0, min(255.0, r_val)))
                output_image_rgba[r_idx, c_idx, 1] = np.uint8(max(0.0, min(255.0, g_val)))
                output_image_rgba[r_idx, c_idx, 2] = np.uint8(max(0.0, min(255.0, b_val)))
    return output_image_rgba


class SmoothColoringPlugin(ColoringAlgorithmPlugin):
    @property
    def name(self) -> str:
        return "スムーズカラー"

    def get_parameters_definition(self) -> list:
        return [
            {'name': 'color_scale', 'label': '色のスケール',
             'type': 'float', 'default': 1.0, 'range': (0.01, 100.0), 'step': 0.01, # 範囲/ステップを調整
             'tooltip': '色の変化の速さを調整します。大きいほど色が細かく変化します。'}
        ]

    def apply_coloring(self, fractal_data: dict, common_fractal_params: dict,
                       algorithm_params: dict, color_map_data: list[tuple[int,int,int]] | None) -> np.ndarray:

        iterations = fractal_data.get('iterations')
        last_z_mod_sq = fractal_data.get('last_z_modulus_sq')

        # --- ここからデバッグ情報追加 ---
        # print(f"SmoothColoringPlugin: カラーリング適用中...")
        # print(f"  共通パラメータ: max_iters={common_fractal_params.get('max_iterations', 'N/A')}, escape_radius={common_fractal_params.get('escape_radius', 'N/A')}")
        # print(f"  アルゴリズムパラメータ: color_scale={algorithm_params.get('color_scale', 'N/A')}")
        # print(f"  受信した fractal_data キー: {list(fractal_data.keys())}")

        # if iterations is not None:
        #     print(f"  反復回数: shape={iterations.shape}, dtype={iterations.dtype}, min={np.min(iterations)}, max={np.max(iterations)}, mean={np.mean(iterations):.2f}")
        #     points_in_set = np.sum(iterations == common_fractal_params.get('max_iterations', 100))
        #     print(f"  集合内の点 (iter == max_iter): {points_in_set} / {iterations.size} ({points_in_set/iterations.size*100:.2f}%)")
        # else:
        #     print("  反復回数データがありません。")

        # if last_z_mod_sq is not None:
        #     print(f"  最終Z係数二乗: shape={last_z_mod_sq.shape}, dtype={last_z_mod_sq.dtype}, min={np.min(last_z_mod_sq):.2e}, max={np.max(last_z_mod_sq):.2e}, mean={np.mean(last_z_mod_sq):.2e}")
        #     if iterations is not None and np.any(iterations < common_fractal_params.get('max_iterations', 100)):
        #         escaped_mask = iterations < common_fractal_params.get('max_iterations', 100)
        #         print(f"    発散した点 (last_z_mod_sq): min={np.min(last_z_mod_sq[escaped_mask]):.2e}, max={np.max(last_z_mod_sq[escaped_mask]):.2e}, mean={np.mean(last_z_mod_sq[escaped_mask]):.2e}")
        # else:
        #     print("  最終Z係数二乗データがありません。")
        # --- デバッグ情報追加ここまで ---

        if iterations is None or last_z_mod_sq is None:
            height_px = common_fractal_params.get('image_height_px', 100) # 利用可能であれば共通パラメータから取得
            width_px = common_fractal_params.get('image_width_px', 100)
            print("SmoothColoringPlugin 警告: 必須データ ('iterations' または 'last_z_modulus_sq') が見つかりません。")
            fallback_img = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_img[:,:,3] = 255 # アルファ
            return fallback_img

        max_iters = common_fractal_params.get('max_iterations', 100)
        escape_radius = common_fractal_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius # JIT関数で使用されます (間接的または将来の式のためであっても)

        color_scale_from_plugin = algorithm_params.get('color_scale', 1.0)

        if not color_map_data or len(color_map_data) < 2: # 補間には少なくとも2色が必要です
            # print("SmoothColoringPlugin 警告: color_map_data の色数が不足しています。デフォルトのグレースケールマップを使用します。")
            # 色が提供されていないか少なすぎる場合は、デフォルトの単純なグレースケールマップ
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
    print("SmoothColoringPlugin のテスト中...")
    plugin = SmoothColoringPlugin()
    print(f"プラグイン名: {plugin.name}")
    print(f"パラメータ定義: {plugin.get_parameters_definition()}")

    # テストデータ
    h, w = 60, 80
    max_i = 200
    test_iters = np.random.randint(0, max_i + 1, size=(h, w), dtype=np.int32)
    # 集合内のいくつかの点をシミュレート
    test_iters[h//2 - 5 : h//2 + 5, w//2 - 5 : w//2 + 5] = max_i
    # 様々な|Z|^2値を持ついくつかの発散した点をシミュレート
    # 発散した点の場合、last_z_mod_sq は escape_radius_sq より大きくなるはずです
    er_val = 2.0 # テスト用の escape_radius
    er_sq = er_val * er_val
    test_mod_sq = np.random.uniform(er_sq + 0.001, er_sq + 1000.0, size=(h,w)).astype(np.float64) # er_sq より大きいことを確認
    test_mod_sq[test_iters == max_i] = 0.0 # 集合内の点の場合、|Z|^2 はしばしば0または未定義です

    test_fractal_data = {'iterations': test_iters, 'last_z_modulus_sq': test_mod_sq, 'height_px':h, 'width_px':w}
    test_common_params = {'max_iterations': max_i, 'escape_radius': er_val, 'image_height_px':h, 'image_width_px':w}

    # デフォルトのアルゴリズムパラメータを取得
    default_algo_params = {}
    for param_def in plugin.get_parameters_definition():
        default_algo_params[param_def['name']] = param_def['default']

    # カラーマップでテスト
    test_color_map = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255), (255,0,255)]

    print("\nカラーマップを使用してカラーリングを適用中...")
    colored_img = plugin.apply_coloring(test_fractal_data, test_common_params, default_algo_params, test_color_map)
    print(f"  カラー画像形状: {colored_img.shape}")
    assert colored_img.shape == (h,w,4)

    # カラーマップなしでテスト (デフォルトのグレースケールを使用するはずです)
    print("\nカラーマップなしでカラーリングを適用中 (デフォルトのグレースケールを使用するはずです)...")
    colored_img_no_map = plugin.apply_coloring(test_fractal_data, test_common_params, default_algo_params, None)
    print(f"  カラー画像 (マップなし) 形状: {colored_img_no_map.shape}")
    assert colored_img_no_map.shape == (h,w,4)

    # 集合内の点が黒であるかどうかを確認
    assert np.array_equal(colored_img[h//2, w//2, :3], [0,0,0]), "Center (in set) point not black."

    # 最小限のカラーマップ (長さ2) でテスト
    min_color_map = [(255,0,0), (0,0,255)]
    print("\n最小限のカラーマップ (2色) を使用してカラーリングを適用中...")
    colored_img_min_map = plugin.apply_coloring(test_fractal_data, test_common_params, default_algo_params, min_color_map)
    print(f"  カラー画像 (最小マップ) 形状: {colored_img_min_map.shape}")
    assert colored_img_min_map.shape == (h,w,4)

    # 問題のある last_z_mod_sq 値 (例: 非常に小さい、または係数が <= 1) でテスト
    # これは smooth_val 計算の堅牢性をテストします
    print("\n潜在的に問題のある mod_sq 値を使用してカラーリングを適用中...")
    problem_mod_sq = np.copy(test_mod_sq)
    # 処理されない場合に係数が <= 1 になるような値をいくつか導入します
    problem_mod_sq[0,0] = 0.5 # 係数 < 1
    problem_mod_sq[0,1] = 0.0 # 係数 = 0
    test_iters[0,0] = 10 # これらが発散した点であることを確認します
    test_iters[0,1] = 10
    problem_fractal_data = {'iterations': test_iters, 'last_z_modulus_sq': problem_mod_sq, 'height_px':h, 'width_px':w}
    colored_img_problem = plugin.apply_coloring(problem_fractal_data, test_common_params, default_algo_params, test_color_map)
    print(f"  カラー画像 (問題のある mod_sq) 形状: {colored_img_problem.shape}")
    assert colored_img_problem.shape == (h,w,4)
    # 主にクラッシュせずに画像を生成することを確認します。
    # ピクセル (0,0) と (0,1) は iter ベースのカラーリングにフォールバックするはずです (または実質的に smooth_val = iters として)
    # 例えば、smooth_val が float(iters[0,0]) になった場合、色は iters[0,0] に基づくべきです

    print("\nSmoothColoringPlugin のテストが完了しました。")


class SmoothColoringPlugin(ColoringAlgorithmPlugin):
    @property
    def name(self) -> str:
        return "スムーズカラー"

    def get_parameters_definition(self) -> list:
        return [
            {'name': 'color_scale', 'label': '色のスケール', # 訳注: 最初の定義ブロックと同一のため、翻訳も同一
             'type': 'float', 'default': 1.0, 'range': (0.1, 50.0), 'step': 0.1,
             'tooltip': '色の変化の速さを調整します。大きいほど色が細かく変化します。'}
        ]

    def apply_coloring(self, fractal_data: dict, common_fractal_params: dict,
                       algorithm_params: dict, color_map_data: list[tuple[int,int,int]] | None) -> np.ndarray:

        iterations = fractal_data.get('iterations')
        last_z_mod_sq = fractal_data.get('last_z_modulus_sq')

        # --- ここからデバッグ情報追加 ---
        print(f"SmoothColoringPlugin: カラーリング適用中...")
        print(f"  共通パラメータ: max_iters={common_fractal_params.get('max_iterations', 'N/A')}, escape_radius={common_fractal_params.get('escape_radius', 'N/A')}")
        print(f"  アルゴリズムパラメータ: color_scale={algorithm_params.get('color_scale', 'N/A')}")
        print(f"  受信した fractal_data キー: {list(fractal_data.keys())}")

        if iterations is not None:
            print(f"  反復回数: shape={iterations.shape}, dtype={iterations.dtype}, min={np.min(iterations)}, max={np.max(iterations)}, mean={np.mean(iterations):.2f}")
            points_in_set = np.sum(iterations == common_fractal_params.get('max_iterations', 100))
            print(f"  集合内の点 (iter == max_iter): {points_in_set} / {iterations.size} ({points_in_set/iterations.size*100:.2f}%)")
        else:
            print("  反復回数データがありません。")

        if last_z_mod_sq is not None:
            print(f"  最終Z係数二乗: shape={last_z_mod_sq.shape}, dtype={last_z_mod_sq.dtype}, min={np.min(last_z_mod_sq):.2e}, max={np.max(last_z_mod_sq):.2e}, mean={np.mean(last_z_mod_sq):.2e}")
            if iterations is not None and np.any(iterations < common_fractal_params.get('max_iterations', 100)):
                escaped_mask = iterations < common_fractal_params.get('max_iterations', 100)
                print(f"    発散した点 (last_z_mod_sq): min={np.min(last_z_mod_sq[escaped_mask]):.2e}, max={np.max(last_z_mod_sq[escaped_mask]):.2e}, mean={np.mean(last_z_mod_sq[escaped_mask]):.2e}")
        else:
            print("  最終Z係数二乗データがありません。")
        # --- デバッグ情報追加ここまで ---

        if iterations is None or last_z_mod_sq is None:
            height_px = common_fractal_params.get('image_height_px', 100) # 利用可能であれば共通パラメータから取得
            width_px = common_fractal_params.get('image_width_px', 100)
            print("SmoothColoringPlugin 警告: 必須データ ('iterations' または 'last_z_modulus_sq') が見つかりません。")
            fallback_img = np.zeros((height_px, width_px, 4), dtype=np.uint8)
            fallback_img[:,:,3] = 255 # アルファ
            return fallback_img

        max_iters = common_fractal_params.get('max_iterations', 100)
        escape_radius = common_fractal_params.get('escape_radius', 2.0)
        escape_radius_sq = escape_radius * escape_radius

        color_scale_from_plugin = algorithm_params.get('color_scale', 1.0)

        if not color_map_data or len(color_map_data) < 2: # 補間には少なくとも2色が必要です
            print("SmoothColoringPlugin 警告: color_map_data の色数が不足しています。デフォルトのグレースケールマップを使用します。")
            # 色が提供されていないか少なすぎる場合は、デフォルトの単純なグレースケールマップ
            color_map_np = np.array([(i,i,i) for i in range(256)], dtype=np.uint8)
        else:
            color_map_np = np.array(color_map_data, dtype=np.uint8)

        # print(f"SmoothColoringPlugin: スムーズカラーリング適用中。 MaxIters: {max_iters}, ER^2: {escape_radius_sq}, MapSize: {color_map_np.shape[0]}")

        colored_image = _apply_smooth_coloring_jit(
            iterations, last_z_mod_sq, max_iters, escape_radius_sq,
            color_scale_from_plugin, # color_scale パラメータを渡す
            color_map_np
        )

        # print(f"SmoothColoringPlugin: カラーリング完了。出力形状: {colored_image.shape}")
        return colored_image

if __name__ == '__main__':
    print("SmoothColoringPlugin のテスト中...")
    plugin = SmoothColoringPlugin()
    print(f"プラグイン名: {plugin.name}")
    print(f"パラメータ定義: {plugin.get_parameters_definition()}")

    # テストデータ
    h, w = 60, 80
    max_i = 200
    test_iters = np.random.randint(0, max_i + 1, size=(h, w), dtype=np.int32)
    # 集合内のいくつかの点をシミュレート
    test_iters[h//2 - 5 : h//2 + 5, w//2 - 5 : w//2 + 5] = max_i
    # 様々な|Z|^2値を持ついくつかの発散した点をシミュレート
    # 発散した点の場合、last_z_mod_sq は escape_radius_sq より大きくなるはずです
    er_sq = 4.0
    test_mod_sq = np.random.uniform(er_sq + 0.1, er_sq + 100.0, size=(h,w)).astype(np.float64)
    test_mod_sq[test_iters == max_i] = 0.0 # 集合内の点の場合、|Z|^2 は 0 です

    test_fractal_data = {'iterations': test_iters, 'last_z_modulus_sq': test_mod_sq, 'height_px':h, 'width_px':w}
    test_common_params = {'max_iterations': max_i, 'escape_radius': math.sqrt(er_sq)}
    test_algo_params = plugin.get_parameters_definition()[0]['default'] if plugin.get_parameters_definition() else {} # パラメータが存在する場合はデフォルトを使用

    # カラーマップでテスト
    test_color_map = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255), (255,0,255)]

    print("\nカラーマップを使用してカラーリングを適用中...")
    colored_img = plugin.apply_coloring(test_fractal_data, test_common_params, test_algo_params, test_color_map)
    print(f"  カラー画像形状: {colored_img.shape}")
    assert colored_img.shape == (h,w,4)

    # カラーマップなしでテスト (デフォルトのグレースケールを使用するはずです)
    print("\nカラーマップなしでカラーリングを適用中 (デフォルトのグレースケールを使用するはずです)...")
    colored_img_no_map = plugin.apply_coloring(test_fractal_data, test_common_params, test_algo_params, None)
    print(f"  カラー画像 (マップなし) 形状: {colored_img_no_map.shape}")
    assert colored_img_no_map.shape == (h,w,4)

    # 集合内の点が黒であるかどうかを確認
    assert np.array_equal(colored_img[h//2, w//2, :3], [0,0,0]), "Center (in set) point not black."

    print("\nSmoothColoringPlugin のテストが完了しました。")
