import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QObject, pyqtSignal # Import necessary Qt components

# FractalController と、それが依存する可能性のあるクラス（例: FractalEngine）をインポート
# パスは実際のプロジェクト構造に合わせて調整してください。
# from controllers.fractal_controller import FractalController
# from models.fractal_engine import FractalEngine # 仮に存在すると仮定

# このテストでは FractalController のみに焦点を当て、FractalEngine はモックします。
# そのため、FractalEngine の具体的な実装は不要です。

# FractalControllerのパス問題を解決するため、sys.pathにプロジェクトルートを追加することを検討
# import sys
# from pathlib import Path
# sys.path.append(str(Path(__file__).resolve().parent.parent)) # プロジェクトルートをsys.pathに追加

from controllers.fractal_controller import FractalController


class TestFractalController(unittest.TestCase):

    def setUp(self):
        # FractalEngine のモックを作成
        self.mock_fractal_engine = MagicMock()
        self.mock_fractal_engine.plugin_manager = MagicMock() # engineがplugin_managerを持つと仮定
        # TypeError: '<=' not supported between instances of 'MagicMock' and 'int' の修正
        self.mock_fractal_engine.image_width_px = 800
        self.mock_fractal_engine.image_height_px = 600
        # self.controller.initial_width = 3.0 # FractalController の initial_width を設定 # 初期化後に移動

        # update_status_display で使用される common_parameters のモックを設定
        # MagicMock.__format__ エラーを避けるため、実際の数値や適切な型の値を返すようにする
        mock_common_params = {
            'width': 3.0,
            'center_real': -0.5,
            'center_imag': 0.0,
            'max_iterations': 100,
            'height': 2.25,
            'escape_radius': 4.0
        }
        self.mock_fractal_engine.get_common_parameters.return_value = mock_common_params

        # update_status_display で使用される plugin name のモック
        # .name 属性を持つようにモックを設定
        mock_fp = MagicMock()
        mock_fp.name = "TestFractalPlugin"
        self.mock_fractal_engine.get_active_fractal_plugin.return_value = mock_fp

        def mock_get_active_coloring_plugin(target_type):
            mock_cp = MagicMock()
            if target_type == 'divergent':
                mock_cp.name = "DivergentColorPlugin"
            elif target_type == 'non_divergent':
                mock_cp.name = "NonDivergentColorPlugin"
            else:
                return None # Should not happen in these tests
            return mock_cp
        self.mock_fractal_engine.get_active_coloring_plugin.side_effect = mock_get_active_coloring_plugin

        # get_current_color_map_selection がターゲットタイプに応じて異なる値を返すように設定
        def mock_get_color_map_selection(target_type):
            if target_type == 'divergent':
                return ("DivPack", "DivMap")
            elif target_type == 'non_divergent':
                return ("NonDivPack", "NonDivMap")
            return (None, None)
        self.mock_fractal_engine.get_current_color_map_selection.side_effect = mock_get_color_map_selection

        self.mock_fractal_engine.get_fractal_plugin_parameters.return_value = {"param_fp": 1.0}
        # get_coloring_plugin_parameters は active_coloring_target_type に依存するため、
        # update_status_display のテスト内でコントローラの active_coloring_target_type を設定した上で、
        # それに応じた値を返すようにエンジンモックを調整する必要があるかもしれない。
        # ただし、update_status_display の現在の実装では、両方の情報を取得しようとするため、
        # ここでの一般的なモックは影響しない。
        self.mock_fractal_engine.get_coloring_plugin_parameters.return_value = {"param_cp": 0.5}


        # FractalController のインスタンスを作成
        self.controller = FractalController(fractal_engine=self.mock_fractal_engine)
        self.controller.initial_width = 3.0 # controller インスタンス作成後に initial_width を設定

        # シグナルをキャッチするためのモックスロット
        self.mock_slot_active_coloring_target_and_plugin_changed = MagicMock()
        self.mock_slot_active_color_map_changed = MagicMock()

        # シグナルにモックスロットを接続
        self.controller.active_coloring_target_and_plugin_changed_externally.connect(
            self.mock_slot_active_coloring_target_and_plugin_changed
        )
        self.controller.active_color_map_changed_externally.connect(
            self.mock_slot_active_color_map_changed
        )

    def test_01_get_available_coloring_plugin_names(self):
        """get_available_coloring_plugin_names_from_engineがtarget_typeをエンジンに渡すか"""
        expected_plugins = ["PluginA", "PluginB"]
        self.mock_fractal_engine.get_available_coloring_plugin_names.return_value = expected_plugins

        result_div = self.controller.get_available_coloring_plugin_names_from_engine(target_type='divergent')
        self.mock_fractal_engine.get_available_coloring_plugin_names.assert_called_with(target_type='divergent')
        self.assertEqual(result_div, expected_plugins)

        result_nondiv = self.controller.get_available_coloring_plugin_names_from_engine(target_type='non_divergent')
        self.mock_fractal_engine.get_available_coloring_plugin_names.assert_called_with(target_type='non_divergent')
        self.assertEqual(result_nondiv, expected_plugins)


    def test_02_set_active_coloring_plugin_and_recolor(self):
        """set_active_coloring_plugin_and_recolorがエンジンを呼び出しシグナルを発行するか"""
        plugin_name = "TestColoringPlugin"
        target_type_divergent = 'divergent'
        target_type_non_divergent = 'non_divergent'

        self.mock_fractal_engine.set_active_coloring_plugin.return_value = True
        # trigger_recolor -> trigger_render -> FractalRenderer のモックが必要になる場合があるが、
        # ここでは set_active_coloring_plugin の呼び出しとシグナル発行に集中する。
        # trigger_recolor の中の self.active_coloring_target_type の更新もテストする。
        with patch.object(self.controller, 'trigger_recolor') as mock_trigger_recolor:
            # Divergent
            self.controller.set_active_coloring_plugin_and_recolor(plugin_name, target_type=target_type_divergent)
            self.mock_fractal_engine.set_active_coloring_plugin.assert_called_with(plugin_name, target_type=target_type_divergent)
            self.assertEqual(self.controller.active_coloring_target_type, target_type_divergent)
            self.mock_slot_active_coloring_target_and_plugin_changed.assert_called_with(target_type_divergent, plugin_name)
            mock_trigger_recolor.assert_called_once() # Ensure recolor is triggered

            mock_trigger_recolor.reset_mock()
            self.mock_slot_active_coloring_target_and_plugin_changed.reset_mock()

            # Non-Divergent
            self.controller.set_active_coloring_plugin_and_recolor(plugin_name, target_type=target_type_non_divergent)
            self.mock_fractal_engine.set_active_coloring_plugin.assert_called_with(plugin_name, target_type=target_type_non_divergent)
            self.assertEqual(self.controller.active_coloring_target_type, target_type_non_divergent)
            self.mock_slot_active_coloring_target_and_plugin_changed.assert_called_with(target_type_non_divergent, plugin_name)
            mock_trigger_recolor.assert_called_once()


    def test_03_set_coloring_plugin_parameter_and_recolor(self):
        """set_coloring_plugin_parameter_and_recolorがエンジンを呼び出すか"""
        param_name = "brightness"
        value = 0.5
        target_type = 'divergent'

        with patch.object(self.controller, 'trigger_recolor') as mock_trigger_recolor:
            self.controller.set_coloring_plugin_parameter_and_recolor(param_name, value, target_type=target_type, allow_recolor=True)
            self.mock_fractal_engine.set_coloring_plugin_parameter.assert_called_with(param_name, value, target_type=target_type)
            self.assertEqual(self.controller.active_coloring_target_type, target_type) # active_coloring_target_typeが更新されるか
            mock_trigger_recolor.assert_called_once()

        # allow_recolor = False の場合
        mock_trigger_recolor.reset_mock()
        with patch.object(self.controller, 'update_status_display') as mock_update_status: # allow_recolor=False時はこちらが呼ばれる
            self.controller.set_coloring_plugin_parameter_and_recolor(param_name, value, target_type=target_type, allow_recolor=False)
            self.mock_fractal_engine.set_coloring_plugin_parameter.assert_called_with(param_name, value, target_type=target_type)
            mock_trigger_recolor.assert_not_called()
            mock_update_status.assert_called_once() # update_status_displayが呼ばれるか


    def test_04_set_active_color_map_and_recolor(self):
        """set_active_color_map_and_recolorがエンジンを呼び出しシグナルを発行するか"""
        pack_name = "TestPack"
        map_name = "TestMap"
        target_type = 'non_divergent'

        self.mock_fractal_engine.set_active_color_map.return_value = True
        with patch.object(self.controller, 'trigger_recolor') as mock_trigger_recolor:
            self.controller.set_active_color_map_and_recolor(pack_name, map_name, target_type=target_type)
            self.mock_fractal_engine.set_active_color_map.assert_called_with(pack_name, map_name, target_type=target_type)
            self.assertEqual(self.controller.active_coloring_target_type, target_type) # active_coloring_target_typeが更新されるか
            self.mock_slot_active_color_map_changed.assert_called_with(pack_name, map_name, target_type) # target_typeを含むシグナル
            mock_trigger_recolor.assert_called_once()


    def test_05_get_active_color_names_with_target_type(self):
        """get_active_color_pack/map_name_from_engineがtarget_typeをエンジンに渡すか"""
        # モックの準備
        self.mock_fractal_engine.get_current_color_map_selection.side_effect = \
            lambda target_type: (f"Pack_{target_type}", f"Map_{target_type}")

        # get_active_color_pack_name_from_engine のテスト
        pack_div = self.controller.get_active_color_pack_name_from_engine(target_type='divergent')
        self.mock_fractal_engine.get_current_color_map_selection.assert_called_with(target_type='divergent')
        self.assertEqual(pack_div, "Pack_divergent")

        pack_nondiv = self.controller.get_active_color_pack_name_from_engine(target_type='non_divergent')
        self.mock_fractal_engine.get_current_color_map_selection.assert_called_with(target_type='non_divergent')
        self.assertEqual(pack_nondiv, "Pack_non_divergent")

        # get_active_color_map_name_from_engine のテスト
        map_div = self.controller.get_active_color_map_name_from_engine(target_type='divergent')
        self.mock_fractal_engine.get_current_color_map_selection.assert_called_with(target_type='divergent')
        self.assertEqual(map_div, "Map_divergent")

        map_nondiv = self.controller.get_active_color_map_name_from_engine(target_type='non_divergent')
        self.mock_fractal_engine.get_current_color_map_selection.assert_called_with(target_type='non_divergent')
        self.assertEqual(map_nondiv, "Map_non_divergent")


    @patch('controllers.fractal_controller.FractalRenderer') # FractalRenderer のコンストラクタをモック
    def test_06_trigger_render_passes_active_coloring_target_type(self, MockFractalRenderer):
        """trigger_renderがFractalRendererにactive_coloring_target_typeを渡すか"""
        # active_coloring_target_type を特定の値に設定
        test_target_type = 'non_divergent'
        self.controller.active_coloring_target_type = test_target_type

        # FractalRenderer のインスタンス化をキャッチするためのモック
        mock_renderer_instance = MockFractalRenderer.return_value

        # trigger_render を呼び出す
        self.controller.trigger_render(full_recompute=True)

        # FractalRenderer が正しい引数で呼び出されたか確認
        MockFractalRenderer.assert_called_once()
        args, kwargs = MockFractalRenderer.call_args
        self.assertEqual(kwargs.get('active_coloring_target_type'), test_target_type)

        # QThreadPool.start が呼ばれたことを確認
        # QThreadPool のモックは複雑なので、ここでは renderer_instance.start() が呼ばれたかで代用するか、
        # QThreadPool.globalInstance().start() の呼び出しをパッチする
        # ここではrendererのsignalsに接続されることと、startが呼ばれることを期待する
        # (FractalRendererはQRunnableを継承しているため、start()メソッドはない。thread_pool.start(task)が正しい)
        # このテストはQThreadPoolの動作までは検証しない。Rendererが正しいパラメータで生成されることまで。


    def test_07_update_status_display(self):
        """update_status_displayが両方のtarget_typeの情報を取得しようとするか"""
        # self.mock_fractal_engine.get_active_fractal_plugin.return_value = MagicMock(name="TestFractalPlugin")
        # self.mock_fractal_engine.get_active_coloring_plugin.side_effect = [
        #     MagicMock(name="DivPlugin"), # for 'divergent'
        #     MagicMock(name="NonDivPlugin") # for 'non_divergent'
        # ]
        # self.mock_fractal_engine.get_current_color_map_selection.side_effect = [
        #     ("DivPack", "DivMap"),   # for 'divergent'
        #     ("NonDivPack", "NonDivMap") # for 'non_divergent'
        # ]
        # self.mock_fractal_engine.get_common_parameters.return_value = {'width': 1.0, 'center_real': 0.0, 'center_imag': 0.0, 'max_iterations': 100}
        # self.mock_fractal_engine.get_fractal_plugin_parameters.return_value = {}
        # self.mock_fractal_engine.get_coloring_plugin_parameters.return_value = {} # これは active_coloring_target_type に依存するので、ここでは不要

        with patch.object(self.controller, 'status_updated') as mock_status_updated:
            # update_status_display を呼び出す前に、active_coloring_target_type を設定しておく
            self.controller.active_coloring_target_type = 'divergent' # 例
            self.controller.update_status_display()

            # get_active_coloring_plugin と get_current_color_map_selection が
            # 'divergent' と 'non_divergent' の両方で呼ばれたか確認
            self.mock_fractal_engine.get_active_coloring_plugin.assert_any_call(target_type='divergent')
            self.mock_fractal_engine.get_active_coloring_plugin.assert_any_call(target_type='non_divergent')
            self.mock_fractal_engine.get_current_color_map_selection.assert_any_call(target_type='divergent')
            self.mock_fractal_engine.get_current_color_map_selection.assert_any_call(target_type='non_divergent')

            # ステータスメッセージの内容確認（部分的に）
            mock_status_updated.emit.assert_called_once() # emitが呼ばれたかを確認
            status_message = mock_status_updated.emit.call_args[0][0]
            self.assertIn("C(D): DivergentColorPlugin (DivPack/DivMap)", status_message)
            self.assertIn("C(ND): NonDivergentColorPlugin (NonDivPack/NonDivMap)", status_message)


if __name__ == '__main__':
    unittest.main()
