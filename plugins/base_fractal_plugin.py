from abc import ABC, abstractmethod
import numpy as np

class FractalPlugin(ABC):
    """
    フラクタルプラグインの抽象基底クラス。
    すべてのフラクタルプラグインはこのクラスを継承する必要があります。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """プラグインの表示名 (例: "Mandelbrot", "Julia")。"""
        pass

    @abstractmethod
    def get_parameters_definition(self) -> list:
        """
        プラグイン固有のパラメータ定義をリストで返します。
        各要素はパラメータを記述する辞書です。
        例:
        [
            {
                'name': 'c_real',
                'label': 'C (実部)',
                'type': 'float',
                'default': -0.745,
                'range': (-2.0, 2.0),
                'step': 0.001
            },
            # ... 他のパラメータ ...
        ]
        パラメータがない場合は空のリストを返します。
        """
        pass

    @abstractmethod
    def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> dict:
        """
        フラクタル計算を実行し、エスケープ時間のNumPy配列を返します。

        引数:
            common_params (dict): 共通パラメータ。以下のキーを含むことを期待:
                'center_real': float - 描画中心の実部
                'center_imag': float - 描画中心の虚部
                'width': float - 描画範囲の幅 (実数軸方向)
                'height': float - 描画範囲の高さ (虚数軸方向, アスペクト比から計算)
                'max_iterations': int - 最大反復回数
                'escape_radius': float - 発散判定半径
            plugin_params (dict): このプラグイン固有のパラメータ。
                                 get_parameters_definitionで定義された 'name' をキーとする。
            image_width_px (int): 生成画像の幅 (ピクセル単位)
            image_height_px (int): 生成画像の高さ (ピクセル単位)

        戻り値:
            dict: 計算結果を格納した辞書。最低限以下のキーを含むことを期待:
                  'iterations': numpy.ndarray (dtype=np.int32) - 各ピクセルのエスケープ回数/収束判定値
                  'last_zn_values': numpy.ndarray (dtype=np.complex128) - 各ピクセルの最終Z_n値 (複素数)
                  他のキーはプラグインやカラーリングアルゴリズムの要求に応じて追加可能
                  (例: 'last_z_modulus_sq', 'zn_trajectory_real', 'zn_trajectory_imag')
        """
        pass

    @abstractmethod
    def get_default_view_parameters(self) -> dict:
        """
        このフラクタルタイプに適したデフォルトの視点パラメータを辞書で返します。
        例: {'center_real': -0.5, 'center_imag': 0.0, 'width': 3.0}
        これらの値は共通パラメータに対応します。
        """
        pass

    # オプションのメソッド: プリセット値を提供する場合など
    def get_presets(self) -> dict | None:
        """
        プラグイン固有のプリセット値 (例: JuliaセットのC定数) を提供する場合にオーバーライドします。
        キーがプリセット名、値がパラメータの辞書となるような辞書を返します。
        例: {"Classic Dragon": {"c_real": -0.8, "c_imag": 0.156}}
        プリセットがない場合はNoneを返します。
        """
        return None

if __name__ == '__main__':
    # このファイルは直接実行されることを意図していませんが、
    # 簡単なテストやドキュメント確認のために以下のようなコードを書くことはできます。

    class DummyPlugin(FractalPlugin):
        @property
        def name(self) -> str:
            return "Dummy"

        def get_parameters_definition(self) -> list:
            return [{'name': 'dummy_param', 'label': 'Dummy Param', 'type': 'float', 'default': 1.0, 'range': (0.0, 10.0)}]

        def compute_fractal(self, common_params: dict, plugin_params: dict, image_width_px: int, image_height_px: int) -> np.ndarray:
            print(f"DummyPlugin: compute_fractal が以下の引数で呼び出されました:")
            print(f"  共通パラメータ: {common_params}")
            print(f"  プラグインパラメータ: {plugin_params}")
            print(f"  画像サイズ: {image_width_px}x{image_height_px}")
            # 期待される次元と型に一致する有効なnumpy配列が返されることを確認してください
            # テストのため、辞書形式で返されることを確認してください
            return {
                'iterations': np.zeros((image_height_px, image_width_px), dtype=np.int32),
                'last_zn_values': np.zeros((image_height_px, image_width_px), dtype=np.complex128)
            }

        def get_default_view_parameters(self) -> dict:
            return {'center_real': 0.0, 'center_imag': 0.0, 'width': 4.0}

    dummy = DummyPlugin()
    print(f"プラグイン名: {dummy.name}")
    print(f"パラメータ定義: {dummy.get_parameters_definition()}")
    print(f"デフォルトビュー: {dummy.get_default_view_parameters()}")

    # common_params の例 (すべての期待されるキーが存在することを確認してください)
    test_common_params = {
        'center_real': 0.0,
        'center_imag': 0.0,
        'width': 4.0,
        'height': 3.0, # テスト用に4:3のアスペクト比を想定
        'max_iterations': 100,
        'escape_radius': 2.0
    }
    test_plugin_params = {'dummy_param': 1.5}

    result_dict = dummy.compute_fractal(
        common_params=test_common_params,
        plugin_params=test_plugin_params,
        image_width_px=80,
        image_height_px=60
    )
    print(f"計算結果 'iterations' の形状: {result_dict['iterations'].shape}, データ型: {result_dict['iterations'].dtype}")
    print(f"計算結果 'last_zn_values' の形状: {result_dict['last_zn_values'].shape}, データ型: {result_dict['last_zn_values'].dtype}")
    assert result_dict['iterations'].shape == (60, 80)
    assert result_dict['iterations'].dtype == np.int32
    assert result_dict['last_zn_values'].shape == (60, 80)
    assert result_dict['last_zn_values'].dtype == np.complex128


    print(f"プリセット: {dummy.get_presets()}")
    print("\nDummyPlugin のテストが完了しました。")
