from abc import ABC, abstractmethod
import numpy as np

class ColoringAlgorithmPlugin(ABC):
    """
    カラーリングアルゴリズムプラグインの抽象基底クラス。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """カラーリングアルゴリズムの表示名 (例: "標準エスケープ", "スムーズ")。"""
        pass

    @property
    def target_type(self) -> str:
        """
        このカラーリングプラグインが処理対象とするデータの種類を示します。
        'divergent': 発散部のデータ (例: マンデルブロ集合の外部)
        'non_divergent': 非発散部のデータ (例: ジュリア集合の内部)
        デフォルトは 'divergent' です。
        """
        return 'divergent'

    @abstractmethod
    def get_parameters_definition(self) -> list:
        """
        このカラーリングアルゴリズム固有のパラメータ定義をリストで返します。
        形式は FractalPlugin の get_parameters_definition と同様です。
        パラメータがない場合は空のリストを返します。
        """
        pass

    @abstractmethod
    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict,
        color_map_data: list[tuple[int, int, int]] | None # カラーマップはオプション
    ) -> np.ndarray:
        """
        指定されたデータとカラーマップを使用してカラーリングを適用し、
        RGBA形式のNumPy画像配列 (uint8, 高さx幅x4) を返します。

        引数:
            fractal_data (dict): フラクタル計算結果。
                必須キー:
                    'iterations': np.ndarray (dtype=np.int32) - エスケープ時間配列。
                オプションキー (アルゴリズムによる):
                    'last_z_modulus_sq': np.ndarray (dtype=np.float64) - 発散時の|Z|^2。
                    'last_z_real': np.ndarray (dtype=np.float64) - 発散時のZの実部。
                    'last_z_imag': np.ndarray (dtype=np.float64) - 発散時のZの虚部。
                    # 他にも軌道トラップ用の軌跡データなども考えられる

            common_fractal_params (dict): フラクタル計算時の共通パラメータ。
                主なキー:
                    'max_iterations': int
                    'escape_radius': float
                    # 他、必要に応じてエンジンから渡される共通設定値

            algorithm_params (dict): このカラーリングアルゴリズム固有のパラメータ。
                                    get_parameters_definitionで定義された 'name' がキー。

            color_map_data (list[tuple[int, int, int]] | None):
                使用するカラーマップの色データのリスト。各要素は(R, G, B)のタプル (0-255)。
                カラーマップを使用しないアルゴリズムの場合は無視されるか、Noneまたは空リストが渡される。

        戻り値:
            numpy.ndarray: RGBAカラーデータのNumPy配列 (形状: 高Hx幅Wx4, dtype=np.uint8)。
        """
        pass

if __name__ == '__main__':
    # 簡単なテスト用ダミープラグイン
    class DummyColoringPlugin(ColoringAlgorithmPlugin):
        @property
        def name(self) -> str:
            return "DummyColoring"

        def get_parameters_definition(self) -> list:
            return [{'name': 'dummy_color_param', 'label': 'Dummy Color P',
                     'type': 'float', 'default': 0.5, 'range': (0.0, 1.0)}]

        def apply_coloring(self, fractal_data: dict, common_fractal_params: dict,
                           algorithm_params: dict, color_map_data: list[tuple[int, int, int]] | None) -> np.ndarray:
            iterations = fractal_data['iterations']
            height, width = iterations.shape
            max_iters = common_fractal_params.get('max_iterations', 100)

            print(f"DummyColoring: apply_coloring が呼び出されました。")
            print(f"  アルゴリズムパラメータ: {algorithm_params}")
            print(f"  カラーマップサイズ: {len(color_map_data) if color_map_data else 0}")

            img_array = np.zeros((height, width, 4), dtype=np.uint8)
            img_array[:, :, 3] = 255 # Alphaチャンネルを不透明に

            for r_idx in range(height):
                for c_idx in range(width):
                    iter_val = iterations[r_idx, c_idx]
                    if iter_val == max_iters: # 内部 (最大反復回数に達した場合)
                        img_array[r_idx, c_idx, 0:3] = [0, 0, 0] # 黒
                    else: # 外部 (発散した場合)
                        if color_map_data and len(color_map_data) > 0:
                            # カラーマップを使用 (単純な剰余で色を選択)
                            color_idx = iter_val % len(color_map_data)
                            img_array[r_idx, c_idx, 0:3] = color_map_data[color_idx]
                        else:
                            # カラーマップがない場合はグレースケール (反復回数に応じて)
                            gray_val = int(255 * (iter_val / max_iters))
                            gray_val = max(0, min(255, gray_val)) # クランプ
                            img_array[r_idx, c_idx, 0:3] = [gray_val, gray_val, gray_val]
            return img_array

    print("DummyColoringPlugin のテストを実行中...")
    dummy_plugin = DummyColoringPlugin()
    print(f"カラーリングプラグイン名: {dummy_plugin.name}")
    print(f"ターゲットタイプ: {dummy_plugin.target_type}") # 新しいプロパティを確認
    assert dummy_plugin.target_type == 'divergent' # デフォルト値を確認
    print(f"パラメータ定義: {dummy_plugin.get_parameters_definition()}")

    # テスト用データ作成
    test_iters_shape = (10, 20)
    test_iters = np.random.randint(0, 101, size=test_iters_shape, dtype=np.int32)
    # 内部の点をいくつか設定
    test_iters[test_iters_shape[0]//2 - 2 : test_iters_shape[0]//2 + 2,
               test_iters_shape[1]//2 - 2 : test_iters_shape[1]//2 + 2] = 100

    test_fractal_data = {'iterations': test_iters}
    test_common_params = {'max_iterations': 100, 'escape_radius': 2.0} # escape_radius はダミーでは未使用
    test_algo_params = {'dummy_color_param': 0.7} # ダミーでは未使用

    # カラーマップありのテスト
    test_color_map = [(255,0,0), (0,255,0), (0,0,255), (255,255,0)] # R, G, B, Y
    print("\nカラーマップを使用してカラーリングを適用中...")
    colored_img_map = dummy_plugin.apply_coloring(test_fractal_data, test_common_params, test_algo_params, test_color_map)
    print(f"  カラー画像形状: {colored_img_map.shape}, dtype: {colored_img_map.dtype}")
    assert colored_img_map.shape == (test_iters_shape[0], test_iters_shape[1], 4)
    assert colored_img_map.dtype == np.uint8
    assert colored_img_map[test_iters_shape[0]//2, test_iters_shape[1]//2, 0] == 0 # 中央の点は黒のはず

    # カラーマップなしのテスト (グレースケールになるはず)
    print("\nカラーマップなしでカラーリングを適用中 (グレースケールになるはず)...")
    colored_img_no_map = dummy_plugin.apply_coloring(test_fractal_data, test_common_params, test_algo_params, None)
    print(f"  カラー画像 (マップなし) 形状: {colored_img_no_map.shape}, dtype: {colored_img_no_map.dtype}")
    assert colored_img_no_map.shape == (test_iters_shape[0], test_iters_shape[1], 4)
    assert colored_img_no_map.dtype == np.uint8
    assert colored_img_no_map[test_iters_shape[0]//2, test_iters_shape[1]//2, 0] == 0 # 中央の点は黒

    # 発散した点の色を確認 (例: iter_val = 50, max_iters = 100 -> gray = 127)
    test_iters_temp = test_iters.copy()
    test_iters_temp[0,0] = 50
    colored_img_gray_check = dummy_plugin.apply_coloring({'iterations': test_iters_temp}, test_common_params, test_algo_params, None)
    expected_gray = int(255 * (50/100))
    assert all(colored_img_gray_check[0,0, :3] == [expected_gray, expected_gray, expected_gray])
    print(f"  iter=50 のグレースケール確認: 成功 (値: {expected_gray})")

    print("\nDummyColoringPlugin のテストが完了しました。")
