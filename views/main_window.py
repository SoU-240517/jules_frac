from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QStatusBar, QSplitter, QLabel, QWidget, QApplication, QVBoxLayout
)
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QMainWindow, QMenuBar, QStatusBar, QSplitter, QVBoxLayout, QApplication # インポートを追加
from .render_area import RenderArea
from .parameter_panel import ParameterPanel
from .high_res_dialog import HighResOutputDialog
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from .status_bar_animator import StatusBarAnimator
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class MainWindow(QMainWindow):
    """
    アプリケーションのメインウィンドウ。

    フラクタル画像の表示エリア、パラメータ設定パネル、メニューバー、ステータスバーを管理します。
    FractalController と連携し、ユーザー操作に応じたフラクタル計算のトリガー、
    高解像度出力ダイアログの表示、および各種状態の更新を行います。
    """
    def __init__(self, fractal_controller, settings_manager):
        """MainWindow を初期化します。
        """
        super().__init__()
        self.fractal_controller = fractal_controller
        self.settings_manager = settings_manager # settings_manager を保存
        self.logger = CustomLogger() # ロガーインスタンスを追加

        self.setWindowTitle("高機能フラクタル描画アプリケーション")
        self.resize(1400, 800)

        self.progress_dialog: QProgressDialog | None = None
        # SettingsManager から最後のエクスポート設定を読み込む、または空の辞書を使用
        self.last_export_settings: dict = self.settings_manager.get_setting(
            HighResOutputDialog.SETTINGS_SECTION_NAME, {}
        )


        # UI初期化
        self._create_actions()
        self._create_menu_bar() # メニューを作成しアクションを追加
        self.status_bar = self.statusBar() # ステータスバーを取得
        self.status_bar_animator = StatusBarAnimator(self.status_bar, self)
        self.status_bar.showMessage("準備完了")

        self._setup_central_widget() # RenderArea と ParameterPanel をセットアップ

        self._connect_controller_signals() # FractalControllerからのシグナルを接続

        self._initial_render_done = False
        self._initial_render_attempts = 0

    def _create_actions(self):
        """
        メニューバーやツールバーで使用する QAction インスタンスを作成します。
        """
        self.export_action = QAction("高解像度出力...", self)
        self.export_action.setShortcut("Ctrl+E")
        # self.export_action.triggered.connect(self._open_high_res_dialog) # 接続は _connect_controller_signals またはメニュー内で直接行うように移動

        # 終了アクションの例 (拡張可能)
        self.exit_action = QAction("終了", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)


    def _create_menu_bar(self): # 一貫性のために _create_menus から名前変更
        """
        メインウィンドウのメニューバーを作成し、アクションを配置します。
        """
        menu_bar = self.menuBar()
        # ファイルメニュー
        file_menu = menu_bar.addMenu("&ファイル")
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # ヘルプメニュー (プレースホルダー)
        help_menu = menu_bar.addMenu("&ヘルプ")
        about_action = QAction("バージョン情報", self)
        # about_action.triggered.connect(self._show_about_dialog) # バージョン情報ダイアログのプレースホルダー
        help_menu.addAction(about_action)


    def _connect_controller_signals(self):
        """
        FractalController からのシグナルを、このウィンドウ内の適切なスロットや
        子ウィジェットのメソッドに接続します。
        """
        if self.fractal_controller:
            # フラクタル描画とパラメータ更新
            if hasattr(self.render_area, 'update_image'):
                self.fractal_controller.image_rendered.connect(self.render_area.update_image)
            if hasattr(self.parameter_panel, 'parameters_changed_in_ui_signal'):
                self.parameter_panel.parameters_changed_in_ui_signal.connect(self.on_ui_parameters_changed)
            if hasattr(self.parameter_panel, 'render_button'): # ParameterPanel に描画ボタンがあると仮定
                self.parameter_panel.render_button.clicked.connect(self.trigger_render_from_panel)

            if hasattr(self.fractal_controller, 'parameters_updated_externally') and \
               hasattr(self.parameter_panel, 'update_ui_from_controller_parameters'):
                self.fractal_controller.parameters_updated_externally.connect(
                    self.parameter_panel.update_ui_from_controller_parameters)

            if hasattr(self.fractal_controller, 'active_fractal_plugin_ui_needs_update') and \
               hasattr(self.parameter_panel, '_update_fractal_plugin_specific_ui'): # メソッド名を仮定
                self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(
                    self.parameter_panel._update_fractal_plugin_specific_ui) # 正しいスロットに接続

            # 以下の active_coloring_plugin_ui_needs_update 接続ブロックは削除されました。

            if hasattr(self.fractal_controller, 'active_color_map_changed_externally') and \
               hasattr(self.parameter_panel, '_update_color_selection_from_controller'):
                self.fractal_controller.active_color_map_changed_externally.connect(
                    self.parameter_panel._update_color_selection_from_controller)

            # レンダリングタスク開始の新しいシグナル
            if hasattr(self.fractal_controller, 'rendering_task_started'):
                self.fractal_controller.rendering_task_started.connect(self._on_rendering_task_started)
            else:
                logger.log("FractalController に rendering_task_started シグナルが存在しません。", level="WARNING")

            # rendering_state_changed シグナルの接続 (ParameterPanel の UI 更新用)
            if hasattr(self.fractal_controller, 'rendering_state_changed') and \
               hasattr(self.parameter_panel, '_on_rendering_state_changed'):
                self.fractal_controller.rendering_state_changed.connect(
                    self.parameter_panel._on_rendering_state_changed
                )
            else:
                logger.log("ParameterPanel または FractalController に rendering_state_changed 関連の属性が存在しません。", level="WARNING")

            # 高解像度エクスポートシグナル
            self.fractal_controller.export_started.connect(self._on_export_started)
            self.fractal_controller.export_progress_updated.connect(self._on_export_progress_updated)
            self.fractal_controller.export_process_finished.connect(self._on_export_process_finished)

            # エクスポートアクショントリガーを接続
            if hasattr(self, 'export_action'):
                 self.export_action.triggered.connect(self._open_high_res_dialog)
            # ステータスバー接続の堅牢性を確保
            if hasattr(self, 'status_bar') and self.status_bar is not None:
                 self.fractal_controller.status_updated.connect(self.update_status_bar)
            else:
                 logger.log("シグナル接続前に StatusBar が初期化されていません。", level="WARNING")
        else:
            logger.log("シグナル接続に FractalController が利用できません。", level="WARNING")

    @pyqtSlot()
    def _on_rendering_task_started(self):
        """
        コントローラーからレンダリングタスク開始のシグナルを受信したときに呼び出されます。
        ステータスバーのアニメーションを開始します。
        """
        self.logger.log("レンダリングタスクが開始されました。アニメーションを開始します。", level="DEBUG")
        self.status_bar_animator.start_animation()

    def update_status_bar(self, message: str):
        """
        ステータスバーのメッセージを更新します。
        アニメーションが実行中の場合は停止し、指定されたメッセージで上書きします。

        Args:
            message (str): ステータスバーに表示する新しいメッセージ。
        """
        if self.status_bar_animator and self.status_bar_animator.is_running:
            self.logger.log(f"update_status_bar がメッセージとともに呼び出されました '{message}'. アニメーションを停止します。", level="DEBUG")
            self.status_bar_animator.stop_animation(final_message=message)
            return # アニメーターがメッセージを設定します
        if self.status_bar: self.status_bar.showMessage(message)

    def _setup_central_widget(self):
        """
        メインウィンドウの中央ウィジェットとして QSplitter を設定し、
        RenderArea と ParameterPanel を配置します。
        """
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.render_area = RenderArea(self, fractal_controller=self.fractal_controller)
        splitter.addWidget(self.render_area)
        self.parameter_panel = ParameterPanel(self.fractal_controller, self)
        splitter.addWidget(self.parameter_panel)
        self.setCentralWidget(splitter)
        initial_width = self.width()
        splitter.setSizes([int(initial_width * 0.7), int(initial_width * 0.3)])
    def on_ui_parameters_changed(self, max_iterations):
        """
        ParameterPanel で共通パラメータが変更されたときに呼び出されるスロット。
        FractalController にパラメータの更新を通知します。

        Args:
            max_iterations (int): 最大反復回数。
        """
        if self.fractal_controller:
            self.fractal_controller.update_common_fractal_parameters(max_iterations=max_iterations)
        else:
            logger.log("パラメータ更新に FractalController が利用できません。", level="WARNING")

    @pyqtSlot()
    def _open_high_res_dialog(self):
        """
        高解像度出力設定ダイアログを開きます。
        現在のフラクタルパラメータとビュー設定をダイアログに渡します。
        """
        if not self.fractal_controller:
            QMessageBox.warning(self, "エラー", "コントローラーが利用できません。")
            return

        common_params = self.fractal_controller.get_current_common_parameters()
        fractal_plugin_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        fractal_plugin_params = self.fractal_controller.get_current_fractal_plugin_parameters_from_engine()
        coloring_algo_name = self.fractal_controller.get_active_coloring_plugin_name_from_engine()
        coloring_algo_params = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine()

        # パック名とマップ名を取得する修正された方法
        current_pack_name_ctrl = self.fractal_controller.get_active_color_pack_name_from_engine()
        current_color_map_ctrl = self.fractal_controller.get_active_color_map_name_from_engine()


        view_params_for_dialog = {
            'image_width_px': self.render_area.width(),
            'image_height_px': self.render_area.height(),
            'max_iterations': common_params.get('max_iterations', 100)
        }

        dialog_defaults = self.last_export_settings.copy()
        dialog_defaults['iterations'] = common_params.get('max_iterations', 100) * 2
        # last_export_settings が空の場合、dialog_defaults は HighResOutputDialog の内部デフォルト値を幅/高さに使用します。
        # または、last_export_settings が空の場合は現在のビューから明示的に設定できます。
        if not self.last_export_settings.get('width'): # 保存された設定に幅がない場合
             dialog_defaults['width'] = self.render_area.width()
             dialog_defaults['height'] = self.render_area.height()


        dialog = HighResOutputDialog(
            settings_manager=self.settings_manager,
            current_dialog_defaults=dialog_defaults,
            current_view_params=view_params_for_dialog,
            parent=self
        )

        if dialog.exec():
            export_settings = dialog.get_export_settings() # UIから設定を取得し、dialog.accept()経由で保存します
            if export_settings and export_settings.get('filepath'):
                logger.log(f"エクスポートダイアログが承認されました。ダイアログからの設定: {export_settings}", level="INFO")

                # ダイアログで直接設定されていないが、エンジンの生成メソッドに必要な部分の現在のエンジン状態を渡す
                export_settings['fractal_plugin_name'] = fractal_plugin_name
                export_settings['fractal_plugin_params'] = fractal_plugin_params
                export_settings['coloring_algorithm_name'] = coloring_algo_name
                export_settings['coloring_algorithm_params'] = coloring_algo_params
                export_settings['color_pack_name'] = current_pack_name_ctrl
                export_settings['color_map_name'] = current_color_map_ctrl
                # フラクタル自体の中心/幅などの共通パラメータは、common_params_override によって上書きされない限り、
                # generate_image_for_output で現在のエンジン状態からデフォルトで取得されます。
                # ダイアログは主に反復回数、解像度、AA、ファイル詳細を上書きします。
                # generate_image_for_output の common_params_override が export_settings['iterations'] からの反復回数を
                # 正しく使用することを確認する必要があります。
                # 現在のエンジンの center_real、center_imag、width は generate_image_for_output によってデフォルトで使用されます。
                # これは通常、高解像度で「現在のビュー」をエクスポートする場合に望ましい動作です。
                # ダイアログでエクスポート用の中心/幅の変更を許可する場合、それらは common_params_override に入ります。

                self.fractal_controller.start_high_res_export(export_settings)
                self.last_export_settings = export_settings # 次回ダイアログを開くために最後に使用した設定を更新
            else:
                QMessageBox.warning(self, "出力エラー", "ファイルパスが指定されていません。")
        else:
            logger.log("エクスポートダイアログがキャンセルされました。", level="INFO")

    @pyqtSlot()
    def _on_export_started(self):
        """
        高解像度エクスポートが開始されたときに呼び出されるスロット。
        プログレスダイアログを表示し、エクスポートアクションを無効化します。
        """
        if self.progress_dialog: self.progress_dialog.cancel()
        self.progress_dialog = QProgressDialog("高解像度画像を生成中...", "キャンセル", 0, 100, self)
        self.progress_dialog.setWindowTitle("エクスポート処理中")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        if self.fractal_controller: self.progress_dialog.canceled.connect(self.fractal_controller.cancel_current_export)
        self.progress_dialog.setValue(0)
        if hasattr(self, 'export_action'): self.export_action.setEnabled(False) # エクスポート中は無効化
        logger.log("エクスポートが開始されました。プログレスダイアログが表示されました。", level="INFO")

    @pyqtSlot(int)
    def _on_export_progress_updated(self, value: int):
        """
        高解像度エクスポートの進捗が更新されたときに呼び出されるスロット。
        プログレスダイアログの値を更新します。

        Args:
            value (int): 新しい進捗値 (0-100)。
        """
        if self.progress_dialog: self.progress_dialog.setValue(value)

    @pyqtSlot(bool, str)
    def _on_export_process_finished(self, success: bool, message: str):
        """
        高解像度エクスポート処理が完了したときに呼び出されるスロット。
        プログレスダイアログを閉じ、結果をユーザーに通知し、エクスポートアクションを再度有効化します。
        """
        logger.log(f"エクスポート処理が完了しました。成功: {success}, メッセージ: {message}", level="INFO")
        if self.status_bar_animator and self.status_bar_animator.is_running:
            self.logger.log("MainWindow: Export finished, ensuring render animation is stopped.", level="DEBUG")
            self.status_bar_animator.stop_animation() # メッセージを設定せずに停止すると、エクスポートメッセージが優先されます

        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if success: QMessageBox.information(self, "エクスポート完了", f"画像を保存しました:\n{message}")
        else: QMessageBox.warning(self, "エクスポート失敗", f"エラーが発生しました:\n{message}")

        if hasattr(self, 'export_action'): self.export_action.setEnabled(True) # 再度有効化
        self.update_status_bar(f"エクスポート完了: {message}" if success else f"エクスポート失敗: {message}")


    @pyqtSlot()
    def trigger_render_from_panel(self):
        """
        ParameterPanel の「描画実行」ボタンがクリックされたときに呼び出されるスロット。
        現在のUIパラメータと RenderArea のサイズを使用してレンダリングをトリガーします。
        """
        if not self.fractal_controller:
            logger.log("FractalController が利用できません。", level="ERROR")
            return

        logger.log("'描画'ボタンがクリックされました.", level="DEBUG")
        if not hasattr(self, 'parameter_panel') or self.parameter_panel is None:
            logger.log("parameter_panel が初期化されていません。", level="ERROR")
            return

        params = self.parameter_panel.get_current_ui_parameters()
        # 描画トリガー前に現在のUI状態に基づいてエンジンパラメータを更新
        self.fractal_controller.update_common_fractal_parameters(max_iterations=params['max_iterations']
            # source="ui_button" # コントローラーで source 引数を使用する場合
        )

        if not hasattr(self, 'render_area') or self.render_area is None: # render_area の存在確認
            logger.log("render_area が初期化されていません。", level="ERROR")
            return

        render_width = self.render_area.width()
        render_height = self.render_area.height()

        if render_width <= 0 or render_height <= 0:
            logger.log("RenderAreaのサイズが不正です. デフォルトサイズで描画を試みます.", level="WARNING")
            # コントローラーの現在 (おそらくデフォルト) の画像サイズ設定で描画をトリガー
            self.fractal_controller.trigger_render()
        else:
            self.fractal_controller.trigger_render(render_width, render_height)
        logger.log(f"描画をトリガーしました (要求解像度: {render_width}x{render_height}).", level="DEBUG")

    def showEvent(self, event):
        """
        ウィンドウが表示されたときに呼び出されるイベントハンドラ。
        初回表示時に、UIが安定した後に一度だけ初期レンダリングを実行します。

        Args:
            event (QShowEvent): イベントオブジェクト。
        """
        super().showEvent(event)
        # UIが安定するのを待つために短い遅延の後、初回描画を一度だけ実行します。
        if not self._initial_render_done:
            # QTimer.singleShot を使用して初回描画をわずかに遅延させ、
            # ウィンドウとそのウィジェットのサイズが決定され、表示されていることを確認します。
            QTimer.singleShot(100, self._perform_initial_render)

    def _perform_initial_render(self):
        """
        ウィンドウの初回表示時にフラクタル画像の初期レンダリングを実行します。
        RenderArea のサイズが確定し、必要なコンポーネントが初期化されていることを確認してから実行します。
        """
        if self._initial_render_done:
            return

        if not self.fractal_controller:
            logger.log("初回描画に FractalController を利用できません。", level="ERROR")
            return

        self._initial_render_attempts += 1
        logger.log(f"初回描画を試みます (試行: {self._initial_render_attempts}).", level="DEBUG")

        # 重要なコンポーネントが初期化され、RenderArea が有効なサイズを持っているか確認
        if not hasattr(self, 'render_area') or self.render_area is None or \
           self.render_area.width() <= 0 or self.render_area.height() <= 0 or \
           not hasattr(self, 'parameter_panel') or self.parameter_panel is None:

            if self._initial_render_attempts <= 5: # 数回リトライ
                logger.log("RenderAreaまたはParameterPanelが未初期化かサイズ不正のため初回描画を遅延します.", level="WARNING")
                QTimer.singleShot(200 * self._initial_render_attempts, self._perform_initial_render)
            else:
                logger.log("RenderAreaまたはParameterPanelの初期化/サイズ確定に失敗しました. 初回描画を中止します.", level="ERROR")
            return

        # パネルから初期パラメータを読み込み (コントローラーまたはデフォルトから読み込まれているはず)
        initial_params = self.parameter_panel.get_current_ui_parameters()
        self.fractal_controller.update_common_fractal_parameters(max_iterations=initial_params['max_iterations']
            # source="initial_load" # source 引数を使用する場合
        )

        render_width = self.render_area.width()
        render_height = self.render_area.height()

        logger.log(f"RenderAreaサイズ ({render_width}x{render_height}) で初回描画を実行します.", level="DEBUG")
        self.fractal_controller.trigger_render(render_width, render_height)
        self._initial_render_done = True
        logger.log("初回描画完了", level="INFO")


if __name__ == '__main__':
    import sys
    from PyQt6.QtCore import QTimer, QObject, pyqtSignal # テストでの時間指定エミッションおよび QObject/pyqtSignal 用
    import numpy # テストでのダミーデータ作成用

    import numpy as np  # numpyがnpとしてインポートされていることを確認

    class MockFractalController(QObject):
        status_updated = pyqtSignal(str)
        image_rendered = pyqtSignal(object)
        parameters_updated_externally = pyqtSignal() # ParameterPanel が使用する場合の一貫性のために保持

        def __init__(self, engine=None):
            super().__init__()
            self.dummy_image_counter = 0
            self._params_cache = {"center_real":-0.5, "center_imag":0.0, "width":3.0, "max_iterations":100, "height":2.0}


        def set_main_window(self, win): pass

        def trigger_render(self, w=None, h=None):
            logger.log(f"MockController: 約 {w}x{h} で描画がトリガーされました", level="DEBUG")
            self.dummy_image_counter += 1
            width, height = 100 + self.dummy_image_counter*20, 80 + self.dummy_image_counter*15
            dummy_data = np.zeros((height, width, 4), dtype=np.uint8) # RGBA
            dummy_data[:, :, 0] = (self.dummy_image_counter * 60) % 255
            dummy_data[:, :, 1] = (128 + self.dummy_image_counter * 10) % 255
            dummy_data[:, :, 2] = (50 + self.dummy_image_counter * 5) % 255
            dummy_data[:, :, 3] = 255
            self.image_rendered.emit(dummy_data)
            self.status_updated.emit(f"Mock: ダミー画像 {self.dummy_image_counter} ({width}x{height}) を描画しました")

        def update_status_display(self):
            self.status_updated.emit("Mock ステータス: パラメータが更新されました")

        def get_current_parameters(self):
            return self._params_cache

        def get_current_engine_parameters(self): # RenderArea パン計算用
             return self.get_current_parameters()

        def update_fractal_parameters(self, cr, ci, w, iters): # モックの簡略化のため source を削除
            logger.log(f"MockController: update_fractal_parameters: CR={cr}, CI={ci}, W={w}, Iters={iters}", level="DEBUG") # ログメッセージ
            self._params_cache = {"center_real":cr, "center_imag":ci, "width":w, "max_iterations":iters}
            # モックテストに関連する場合、高さが何らかのアスペクト比に基づいて更新されることを確認
            self._params_cache["height"] = w * ( (self._params_cache.get("image_height_px",3) / self._params_cache.get("image_width_px",4) ) if self._params_cache.get("image_width_px",4) > 0 else 0.75)
            self.status_updated.emit(f"Mock: パラメータが CR={cr:.2f}, W={w:.2f}, Iters={iters} に更新されました")
            # self.parameters_updated_externally.emit() # UI以外の変更の場合のみ

        def pan_fractal(self, dr, di):
            logger.log(f"MockController (MainWindow テスト): pan_fractal が dr={dr:.4e}, di={di:.4e} で呼び出されました", level="DEBUG")
            params = self.get_current_parameters()
            new_cr = params["center_real"] - dr
            new_ci = params["center_imag"] - di
            self.update_fractal_parameters(new_cr, new_ci, params["width"], params["max_iterations"])
            self.parameters_updated_externally.emit() # パンはパラメータへの外部更新です
            self.trigger_render()


    app = QApplication(sys.argv)
    mock_controller = MockFractalController()
    main_win = MainWindow(fractal_controller=mock_controller)
    # ステータス更新を接続、MainWindow が内部で接続していれば既に完了していますが、テストの明確性のために良い
    if hasattr(mock_controller, 'status_updated') and hasattr(main_win, 'update_status_bar'):
         mock_controller.status_updated.connect(main_win.update_status_bar)
    # 主要な接続は MainWindow の __init__ 内にあります

    main_win.show()

    # 短い遅延の後、「ボタン」からの描画トリガーをシミュレート
    # 実際のシナリオでは、ユーザーはParameterPanelの描画ボタンをクリックします
    def simulate_render_button_click():
        if hasattr(main_win, 'trigger_render_from_panel'):
            logger.log("\nテストハーネス: 描画ボタンクリックをシミュレート中...", level="INFO")
            main_win.trigger_render_from_panel()

    QTimer.singleShot(1000, simulate_render_button_click)

    # UIパラメータ変更後の描画ボタンクリックをシミュレート
    def simulate_ui_change_then_render():
        logger.log("\nテストハーネス: パネルでのUIパラメータ変更をシミュレート中...", level="INFO")
        if hasattr(main_win, 'parameter_panel'):
            # これにより parameters_changed_in_ui_signal が発行され、MainWindow は on_ui_parameters_changed に接続します
            main_win.parameter_panel.width_spinbox.setValue(1.5)

        # パラメータ更新処理のための短い遅延の後、描画ボタンクリックをシミュレート
        QTimer.singleShot(200, simulate_render_button_click)


    QTimer.singleShot(2500, simulate_ui_change_then_render)


    sys.exit(app.exec())
