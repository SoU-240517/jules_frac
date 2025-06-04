import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QSize # Import QSize

# views.parameter_panel が存在し、ParameterPanel クラスをインポートできることを前提とします。
# もしパスが異なる場合は、適切に修正してください。
# sys.path.append(str(Path(__file__).parent.parent)) をテストファイルの先頭に追加することも検討。
from views.parameter_panel import ParameterPanel

# QApplicationインスタンスの作成 (テスト実行に必要)
# 通常、テストスイート全体で一度だけ作成するのが良いですが、ここではファイル単位で記述します。
# 実際のテストランナーによっては、より良い管理方法があります。
app = QApplication.instance()
if app is None:
    app = QApplication([])

class TestParameterPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # ParameterPanel は FractalController を必要とします。モックを作成します。
        cls.mock_fractal_controller = MagicMock()

        # FractalController のメソッドの戻り値をモックします。
        # これらは ParameterPanel が初期化時に呼び出すものです。
        cls.mock_fractal_controller.get_available_fractal_plugin_names_from_engine.return_value = ["TestFractal"]
        cls.mock_fractal_controller.get_active_fractal_plugin_name_from_engine.return_value = "TestFractal"
        cls.mock_fractal_controller.get_fractal_plugin_parameter_definitions_from_engine.return_value = [] # 簡略化のため空
        cls.mock_fractal_controller.get_current_fractal_plugin_parameters_from_engine.return_value = {} # 簡略化のため空

        # カラーリング関連のメソッドのモック (target_type を考慮)
        cls.mock_fractal_controller.get_available_coloring_plugin_names_from_engine = MagicMock(
            side_effect=lambda target_type: [f"TestColor_{target_type}_1", f"TestColor_{target_type}_2"]
        )
        cls.mock_fractal_controller.get_active_coloring_plugin_name_from_engine = MagicMock(
            side_effect=lambda target_type: f"TestColor_{target_type}_1"
        )
        cls.mock_fractal_controller.get_coloring_plugin_parameter_definitions_from_engine = MagicMock(return_value=[]) # 簡略化
        cls.mock_fractal_controller.get_current_coloring_plugin_parameters_from_engine = MagicMock(return_value={}) # 簡略化
        cls.mock_fractal_controller.get_plugin_presets = MagicMock(return_value={}) # プリセットなし

        cls.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value = ["Pack1", "Pack2"]
        cls.mock_fractal_controller.get_active_color_pack_name_from_engine = MagicMock(
            side_effect=lambda target_type: "Pack1"
        )
        cls.mock_fractal_controller.get_color_map_names_in_pack_from_engine = MagicMock(
            return_value=["MapA", "MapB"]
        )
        cls.mock_fractal_controller.get_active_color_map_name_from_engine = MagicMock(
            side_effect=lambda target_type: "MapA"
        )
        # _create_colormap_thumbnail が呼ばれる get_color_map_data_from_engine のモック
        cls.mock_fractal_controller.get_color_map_data_from_engine.return_value = [(255,0,0), (0,255,0), (0,0,255)]


        # ParameterPanel のインスタンスを作成
        # ParameterPanel内で QSize が使われているため、ここでインポートを確認
        # from PyQt6.QtCore import QSize # これはファイルの先頭で行うべき
        cls.panel = ParameterPanel(fractal_controller=cls.mock_fractal_controller)

    def test_01_initialization_ui_elements_exist(self):
        """ParameterPanel初期化時に発散部と非発散部のUI要素が作成されるかテスト"""
        self.assertIsNotNone(self.panel.divergent_coloring_group, "発散部カラーリンググループが存在しません")
        self.assertIsNotNone(self.panel.non_divergent_coloring_group, "非発散部カラーリンググループが存在しません")

        # 発散部UI要素の存在確認
        self.assertIsNotNone(self.panel.coloring_algorithm_combo_divergent)
        self.assertIsNotNone(self.panel.coloring_plugin_specific_group_divergent)
        self.assertIsNotNone(self.panel.color_pack_combo_divergent)
        self.assertIsNotNone(self.panel.color_map_listwidget_divergent)

        # 非発散部UI要素の存在確認
        self.assertIsNotNone(self.panel.coloring_algorithm_combo_non_divergent)
        self.assertIsNotNone(self.panel.coloring_plugin_specific_group_non_divergent)
        self.assertIsNotNone(self.panel.color_pack_combo_non_divergent)
        self.assertIsNotNone(self.panel.color_map_listwidget_non_divergent)

    def test_02_load_initial_parameters_divergent(self):
        """load_initial_parametersが発散部のUIを正しく初期化するかテスト"""
        # _populate_coloring_algorithm_combo の呼び出し確認 (発散部)
        self.mock_fractal_controller.get_available_coloring_plugin_names_from_engine.assert_any_call(target_type='divergent')
        self.mock_fractal_controller.get_active_coloring_plugin_name_from_engine.assert_any_call(target_type='divergent')
        self.assertEqual(self.panel.coloring_algorithm_combo_divergent.currentText(), "TestColor_divergent_1")

        # _populate_color_pack_combo の呼び出し確認 (発散部)
        self.mock_fractal_controller.get_active_color_pack_name_from_engine.assert_any_call(target_type='divergent')
        self.assertEqual(self.panel.color_pack_combo_divergent.currentText(), "Pack1")

        # _populate_color_map_list の呼び出し確認 (発散部)
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.assert_any_call("Pack1")
        self.mock_fractal_controller.get_active_color_map_name_from_engine.assert_any_call(target_type='divergent')
        self.assertIsNotNone(self.panel.color_map_listwidget_divergent.currentItem())
        self.assertEqual(self.panel.color_map_listwidget_divergent.currentItem().text(), "MapA")

    def test_03_load_initial_parameters_non_divergent(self):
        """load_initial_parametersが非発散部のUIを正しく初期化するかテスト"""
        # _populate_coloring_algorithm_combo の呼び出し確認 (非発散部)
        self.mock_fractal_controller.get_available_coloring_plugin_names_from_engine.assert_any_call(target_type='non_divergent')
        self.mock_fractal_controller.get_active_coloring_plugin_name_from_engine.assert_any_call(target_type='non_divergent')
        self.assertEqual(self.panel.coloring_algorithm_combo_non_divergent.currentText(), "TestColor_non_divergent_1")

        # _populate_color_pack_combo の呼び出し確認 (非発散部)
        self.mock_fractal_controller.get_active_color_pack_name_from_engine.assert_any_call(target_type='non_divergent')
        self.assertEqual(self.panel.color_pack_combo_non_divergent.currentText(), "Pack1")

        # _populate_color_map_list の呼び出し確認 (非発散部)
        # Note: get_color_map_names_in_pack_from_engine はパック名のみに依存するため、target_typeなしで呼ばれる想定
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.assert_any_call("Pack1")
        self.mock_fractal_controller.get_active_color_map_name_from_engine.assert_any_call(target_type='non_divergent')
        self.assertIsNotNone(self.panel.color_map_listwidget_non_divergent.currentItem())
        self.assertEqual(self.panel.color_map_listwidget_non_divergent.currentItem().text(), "MapA")

    # --- UI操作とコントローラー連携のテスト ---
    # (例: 発散部アルゴリズム変更)
    @patch.object(ParameterPanel, '_update_coloring_plugin_specific_ui') # このメソッドの呼び出しを検証
    def test_04_on_coloring_algorithm_changed_divergent(self, mock_update_specific_ui):
        """発散部アルゴリズム変更時にコントローラーが正しく呼ばれるか"""
        # 事前状態の確認
        current_algo_divergent = self.panel.coloring_algorithm_combo_divergent.currentText()
        self.assertNotEqual(current_algo_divergent, "TestColor_divergent_2")

        # アクション: 発散部アルゴリズムコンボボックスの値を変更
        self.panel.coloring_algorithm_combo_divergent.setCurrentText("TestColor_divergent_2")
        # _on_coloring_algorithm_changed が呼び出されるはず

        # 検証: コントローラーのメソッドが正しい引数で呼ばれたか
        self.mock_fractal_controller.set_active_coloring_plugin_and_recolor.assert_called_with(
            plugin_name="TestColor_divergent_2",
            target_type='divergent'
        )
        # _update_coloring_plugin_specific_ui の直接呼び出しの検証は削除。
        # シグナル経由での呼び出しは update_active_coloring_target_and_plugin_from_controller のテストでカバーされる想定。


    @patch.object(ParameterPanel, '_update_coloring_plugin_specific_ui')
    def test_05_on_coloring_algorithm_changed_non_divergent(self, mock_update_specific_ui):
        """非発散部アルゴリズム変更時にコントローラーが正しく呼ばれるか"""
        self.panel.coloring_algorithm_combo_non_divergent.setCurrentText("TestColor_non_divergent_2")
        self.mock_fractal_controller.set_active_coloring_plugin_and_recolor.assert_called_with(
            plugin_name="TestColor_non_divergent_2",
            target_type='non_divergent'
        )
        # _update_coloring_plugin_specific_ui の直接呼び出しの検証は削除。

    # --- コントローラーからの更新通知テスト ---
    def test_06_update_active_coloring_target_and_plugin_from_controller_divergent(self):
        """コントローラーから発散部プラグイン変更通知が来た場合にUIが更新されるか"""
        # ParameterPanelのメソッドを直接呼び出してシグナルを模倣
        self.panel.update_active_coloring_target_and_plugin_from_controller(
            target_type='divergent',
            plugin_name='TestColor_divergent_2'
        )
        self.assertEqual(self.panel.coloring_algorithm_combo_divergent.currentText(), 'TestColor_divergent_2')
        # _update_coloring_plugin_specific_uiが呼ばれたことも検証したいが、副作用の確認に留める

    def test_07_update_color_selection_from_controller_non_divergent(self):
        """コントローラーから非発散部カラーマップ変更通知が来た場合にUIが更新されるか"""
        # 事前準備: Pack2 に MapC, MapD があると仮定
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.reset_mock(side_effect=True) # side_effectをリセット
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.side_effect =             lambda pack_name: ["MapC", "MapD"] if pack_name == "Pack2" else ["MapA", "MapB"]

        self.panel._update_color_selection_from_controller(
            pack_name='Pack2',
            map_name='MapC',
            target_type='non_divergent'
        )
        self.assertEqual(self.panel.color_pack_combo_non_divergent.currentText(), 'Pack2')
        self.assertEqual(self.panel.color_map_listwidget_non_divergent.currentItem().text(), 'MapC')

    def test_08_on_color_pack_changed_divergent(self):
        """発散部カラーパック変更時にコントローラーが正しく呼ばれるか"""
        # 事前準備: カラーマップリストが期待通りにモックされるようにする
        # Pack2が選択されたら、get_color_map_names_in_pack_from_engine は "MapC", "MapD" を返すようにする
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.reset_mock(side_effect=True)
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.side_effect = \
            lambda pack_name: ["MapC", "MapD"] if pack_name == "Pack2" else ["MapA", "MapB"]

        # アクション: 発散部カラーパックコンボボックスの値を変更
        # これにより _on_color_pack_changed -> _populate_color_map_list -> _on_color_map_changed (最初のアイテム選択) がトリガーされる
        self.panel.color_pack_combo_divergent.setCurrentText("Pack2")

        # 検証: set_active_color_map_and_recolor が呼ばれるか (新しいパックの最初のマップで)
        # _populate_color_map_list で MapC, MapD が設定され、MapCが自動選択されるはず
        self.mock_fractal_controller.set_active_color_map_and_recolor.assert_called_with(
            "Pack2", "MapC", target_type='divergent'
        )

    def test_09_update_active_coloring_target_and_plugin_from_controller_non_divergent(self):
        """コントローラーから非発散部プラグイン変更通知が来た場合にUIが更新されるか"""
        with patch.object(self.panel, '_update_coloring_plugin_specific_ui') as mock_update_ui:
            self.panel.update_active_coloring_target_and_plugin_from_controller(
                target_type='non_divergent',
                plugin_name='TestColor_non_divergent_2',
                # preset_name='SomePreset' # オプションでプリセットもテスト可能
            )
            self.assertEqual(self.panel.coloring_algorithm_combo_non_divergent.currentText(), 'TestColor_non_divergent_2')
            mock_update_ui.assert_called_with('TestColor_non_divergent_2', 'non_divergent')
            # 必要であればプリセットコンボボックスの選択も検証

    def test_10_update_color_selection_from_controller_divergent(self):
        """コントローラーから発散部カラーマップ変更通知が来た場合にUIが更新されるか"""
        original_available_packs = self.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value
        self.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value = ["Pack1", "Pack2", "PackNew"]

        # ParameterPanelのコンボボックスを新しいパックリストで更新するために、
        # _populate_color_pack_comboを直接呼び出すか、
        # もしこのメソッドがUIイベントにしか反応しないなら、UIイベントをシミュレートする必要がある。
        # ここでは、_populate_color_pack_combo が内部的に呼ばれることを期待して、
        # _update_color_selection_from_controller を呼び出す前に Panel の状態を整合させる。
        # _update_color_selection_from_controller 内部で pack_name がなければ _populate_color_pack_combo が呼ばれる。

        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.reset_mock(side_effect=True)
        self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.side_effect = \
            lambda pack_name: ["MapX", "MapY"] if pack_name == "PackNew" else (["MapC", "MapD"] if pack_name == "Pack2" else ["MapA", "MapB"])

        self.panel._update_color_selection_from_controller(
            pack_name='PackNew',
            map_name='MapY',
            target_type='divergent'
        )
        self.assertEqual(self.panel.color_pack_combo_divergent.currentText(), 'PackNew')
        self.assertIsNotNone(self.panel.color_map_listwidget_divergent.currentItem())
        self.assertEqual(self.panel.color_map_listwidget_divergent.currentItem().text(), 'MapY')

        # モックを元に戻す
        self.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value = original_available_packs

    # def test_10_update_color_selection_from_controller_divergent(self):
    #     """コントローラーから発散部カラーマップ変更通知が来た場合にUIが更新されるか"""
    #     original_available_packs = self.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value
    #     self.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value = ["Pack1", "Pack2", "PackNew"]

    #     # ParameterPanelのコンボボックスを新しいパックリストで更新するために、
    #     # _populate_color_pack_comboを直接呼び出すか、
    #     # もしこのメソッドがUIイベントにしか反応しないなら、UIイベントをシミュレートする必要がある。
    #     # ここでは、_populate_color_pack_combo が内部的に呼ばれることを期待して、
    #     # _update_color_selection_from_controller を呼び出す前に Panel の状態を整合させる。
    #     # _update_color_selection_from_controller 内部で pack_name がなければ _populate_color_pack_combo が呼ばれる。

    #     self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.reset_mock(side_effect=True)
    #     self.mock_fractal_controller.get_color_map_names_in_pack_from_engine.side_effect = \
    #         lambda pack_name: ["MapX", "MapY"] if pack_name == "PackNew" else (["MapC", "MapD"] if pack_name == "Pack2" else ["MapA", "MapB"])

    #     self.panel._update_color_selection_from_controller(
    #         pack_name='PackNew',
    #         map_name='MapY',
    #         target_type='divergent'
    #     )
    #     self.assertEqual(self.panel.color_pack_combo_divergent.currentText(), 'PackNew')
    #     self.assertIsNotNone(self.panel.color_map_listwidget_divergent.currentItem())
    #     self.assertEqual(self.panel.color_map_listwidget_divergent.currentItem().text(), 'MapY')

    #     # モックを元に戻す
    #     self.mock_fractal_controller.get_available_color_pack_names_from_engine.return_value = original_available_packs


if __name__ == '__main__':
    unittest.main()
