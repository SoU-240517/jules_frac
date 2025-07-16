import time
import traceback # この行が存在しない場合に追加
from pathlib import Path # Path を追加
from export.image_exporter import ImageExporter # ExporterSignals は ImageExporter 内部で使用されるシグナルです
from models.fractal_engine import FractalEngine # FractalEngineモデルのインポート (型ヒント用)
from .fractal_renderer import FractalRenderer
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, pyqtSlot, QRunnable # QRunnable を追加
from logger.custom_logger import CustomLogger
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin # ColoringAlgorithmPlugin をインポート
from settings_manager import SettingsManager # SettingsManager をインポート
from typing import Any
import re

logger = CustomLogger()

class FractalController(QObject):
    """
    フラクタル描画アプリケーションのコントローラ。
    フラクタルエンジンや設定管理、UIとの連携、プリセット管理、
    レンダリング・エクスポート・パラメータ操作など、
    アプリ全体の制御を担う中心的なクラスです。
    """
    # --- シグナル定義 ---
    image_rendered = pyqtSignal(object)  # 画像がレンダリングされたときに通知
    status_updated = pyqtSignal(str)  # ステータスバーの表示更新用
    parameters_updated_externally = pyqtSignal(dict)  # パラメータが外部から変更されたとき通知
    active_fractal_plugin_ui_needs_update = pyqtSignal(str)  # アクティブなフラクタルプラグインのUI更新要求
    active_coloring_plugin_ui_needs_update = pyqtSignal(str)  # アクティブなカラーリングプラグインのUI更新要求
    active_coloring_target_and_plugin_changed_externally = pyqtSignal(str, str)  # ターゲットタイプ・プラグイン名変更通知
    active_color_map_changed_externally = pyqtSignal(str, str, str)  # カラーパック・マップ・ターゲットタイプ変更通知
    configuration_applied = pyqtSignal()  # 設定適用後のUI更新通知
    rendering_task_started = pyqtSignal()  # レンダリングタスク開始通知
    rendering_state_changed = pyqtSignal(bool)  # レンダリング状態変化通知（開始:True/終了:False）
    # --- 高解像度エクスポート用シグナル ---
    export_started = pyqtSignal()  # エクスポート開始
    export_progress_updated = pyqtSignal(int)  # エクスポート進捗
    export_process_finished = pyqtSignal(bool, str)  # エクスポート完了（成功/失敗, メッセージ）

    def __init__(self, fractal_engine: FractalEngine, settings_manager: SettingsManager):
        """
        FractalControllerの初期化。
        フラクタルエンジン・設定管理インスタンスを受け取り、
        各種状態やUI連携用の属性を初期化します。

        Args:
            fractal_engine (FractalEngine): フラクタル計算・描画エンジン
            settings_manager (SettingsManager): 設定管理インスタンス
        """
        super().__init__()
        self.fractal_engine = fractal_engine  # フラクタル計算・描画エンジン
        self.settings_manager = settings_manager  # 設定管理
        self.main_window = None  # メインウィンドウ参照
        self.last_compute_time_ms = 0.0  # 直近の計算時間（ミリ秒）
        self.last_coloring_time_ms = 0.0  # 直近のカラーリング時間（ミリ秒）
        self.initial_width = self.fractal_engine.width if self.fractal_engine else 3.0  # 初期表示幅
        self.logger = CustomLogger()  # ロガー
        self.is_rendering = False  # レンダリング中フラグ
        self.preview_downscale_factor = 0.5  # プレビュー解像度の縮小率
        self.current_exporter: ImageExporter | None = None  # 現在のエクスポート処理
        self.thread_pool = QThreadPool.globalInstance()  # スレッドプール
        self.current_renderer_task = None  # 現在のレンダリングタスク
        self.active_coloring_target_type: str = 'divergent'  # デフォルトのカラーリングターゲット
        # 必要に応じて同時エクスポート数を制限可能: self.thread_pool.setMaxThreadCount(1)

    def _apply_config_to_engine(self, config: dict):
        """指定された設定辞書をエンジンに適用します。UI更新や再描画は行いません。"""
        if not self.fractal_engine or not config or not isinstance(config, dict):
            logger.log("設定適用スキップ: エンジン未設定、または無効な設定です。", "WARNING")
            return

        try:
            # 1. フラクタルプラグイン
            fp_name = config.get('fractal_plugin_name')
            logger.log(f"プリセット適用: fractal_plugin_name={fp_name}", level="DEBUG")
            if fp_name:
                current_fp_name = self.get_active_fractal_plugin_name_from_engine()
                logger.log(f"現在のアクティブなフラクタルプラグイン: {current_fp_name}", level="DEBUG")
                if current_fp_name != fp_name:
                    logger.log(f"フラクタルプラグインを切り替えます: {current_fp_name} → {fp_name}", level="INFO")
                    self.fractal_engine.set_active_fractal_plugin(fp_name)
                    # UI更新シグナルもemit
                    self.active_fractal_plugin_ui_needs_update.emit(fp_name)
                else:
                    logger.log("フラクタルプラグインは既に一致しているため切り替えません。", level="DEBUG")
                fp_params = config.get('fractal_plugin_parameters', {})
                logger.log(f"プリセット適用: fractal_plugin_parameters={fp_params}", level="DEBUG")
                for name, value in fp_params.items():
                    self.fractal_engine.set_fractal_plugin_parameter(name, value)

            # 2. 共通パラメータ (プラグインのデフォルトを上書きするためにプラグイン設定後に適用)
            common_params = config.get('common_parameters')
            logger.log(f"プリセット適用: common_parameters={common_params}", level="DEBUG")
            if common_params:
                common_params.pop('height', None)
                self.fractal_engine.set_common_parameters(**common_params)

            # 3. カラーリング設定 (Divergent / Non-Divergent)
            for target_type in ['divergent', 'non_divergent']:
                coloring_config = config.get(f'coloring_{target_type}', {})
                logger.log(f"プリセット適用: coloring_{target_type}={coloring_config}", level="DEBUG")
                if not coloring_config:
                    continue
                cp_name = coloring_config.get('plugin_name')
                if cp_name:
                    self.fractal_engine.set_active_coloring_plugin(cp_name, target_type=target_type)
                    cp_params = coloring_config.get('plugin_parameters', {})
                    for name, value in cp_params.items():
                        self.fractal_engine.set_coloring_plugin_parameter(name, value, target_type=target_type)
                pack_name = coloring_config.get('pack_name')
                map_name = coloring_config.get('map_name')
                if pack_name and map_name:
                    self.fractal_engine.set_active_color_map(pack_name, map_name, target_type=target_type)

            self.fractal_engine.last_fractal_data_cache = None # 設定適用後はキャッシュをクリア
            logger.log("エンジン設定の適用が完了しました。", "DEBUG")
            logger.log(f"適用後のアクティブなフラクタルプラグイン: {self.get_active_fractal_plugin_name_from_engine()}", level="DEBUG")

        except Exception as e:
            logger.log(f"エンジン設定の適用中にエラーが発生しました: {e}", level="ERROR", exc_info=True)

    def apply_configuration_from_settings(self):
        """
        SettingsManager から保存された設定を読み込み、FractalEngine に適用します。
        このメソッドはUIの更新をトリガーしません。UIは別途初期化される必要があります。
        """
        config = self.settings_manager.get_setting("engine_settings")
        if not config or not isinstance(config, dict):
            logger.log("保存されたエンジン設定が見つからないか、無効です。デフォルトで起動します。", level="INFO")
            return

        logger.log("保存されたエンジン設定を読み込んで適用します...", level="INFO")
        self._apply_config_to_engine(config)

    def get_preset_names(self) -> list[str]:
        """プリセット名の一覧を取得します。"""
        return list(self.settings_manager.get_presets().keys())

    def save_current_config_as_preset(self, name: str):
        """現在の設定をプリセットとして保存します。"""
        if not name:
            self.logger.log("プリセット名が空のため、保存をキャンセルしました。", "WARNING")
            return
        config = self.get_full_configuration()
        self.settings_manager.save_preset(name, config)
        self.logger.log(f"プリセット '{name}' を保存しました。", "INFO")

    def load_preset(self, name: str):
        """プリセットを読み込み、適用します。"""
        presets = self.settings_manager.get_presets()
        config = presets.get(name)
        if config:
            self.logger.log(f"プリセット '{name}' を読み込んでいます...", "INFO")
            self._apply_config_to_engine(config)
            self.configuration_applied.emit() # UI更新を通知
            self.trigger_render(full_recompute=True) # 再描画
        else:
            self.logger.log(f"プリセット '{name}' が見つかりませんでした。", "ERROR")

    def delete_preset(self, name: str):
        """プリセットを削除します。"""
        self.settings_manager.delete_preset(name)
        self.logger.log(f"プリセット '{name}' を削除しました。", "INFO")

    def export_presets(self, file_path: str) -> tuple[bool, str]:
        """
        現在のプリセットをJSONファイルにエクスポートします。
        Args:
            file_path (str): エクスポート先のJSONファイルのパス。
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)。
        """
        try:
            self.settings_manager.export_presets_to_file(Path(file_path))
            return True, f"プリセットを '{file_path}' にエクスポートしました。"
        except Exception as e:
            self.logger.log(f"プリセットのエクスポート中にエラーが発生しました: {e}", "ERROR")
            return False, f"プリセットのエクスポートに失敗しました: {e}"

    def import_presets(self, file_path: str, overwrite: bool) -> tuple[bool, str]:
        """
        JSONファイルからプリセットをインポートします。
        Args:
            file_path (str): インポートするJSONファイルのパス。
            overwrite (bool): 既存の同名プリセットを上書きするかどうか。
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)。
        """
        try:
            imported_names = self.settings_manager.import_presets_from_file(Path(file_path), overwrite)
            self.configuration_applied.emit() # UIを更新するためにシグナルを発行
            return True, f"プリセットをインポートしました: {', '.join(imported_names) if imported_names else '新しいプリセットはありませんでした。'}"
        except Exception as e:
            self.logger.log(f"プリセットのインポート中にエラーが発生しました: {e}", "ERROR")
            return False, f"プリセットのインポートに失敗しました: {e}"

    def set_main_window(self, main_window):
        """
        メインウィンドウの参照を設定し、初期ステータス表示を更新します。

        Args:
            main_window (MainWindow): アプリケーションのメインウィンドウインスタンス。
        """
        self.main_window = main_window
        self.update_status_display()

    # --- フラクタル共通パラメータ処理 ---
    def update_common_fractal_parameters(self, max_iterations: int, escape_radius: float | None = None, source: str | None = None):
        """
        共通のフラクタルパラメータ（最大反復回数、エスケープ半径）を更新します。
        中心座標と幅は、パンやズーム操作によって直接エンジンパラメータが更新されるため、
        このメソッドでは扱いません。UIからの最大反復回数の変更時に呼び出されます。

        Args:
            max_iterations (int): 新しい最大反復回数。
            escape_radius (float, optional): 新しいエスケープ半径。Noneの場合、エンジンは現在の値を使用するか、デフォルト値を使用します。
            source (str, optional): パラメータ更新のトリガー元を示す文字列。 Defaults to None.
        """
        if self.fractal_engine:
            current_params = self.fractal_engine.get_common_parameters()
            if current_params:
                self.fractal_engine.set_common_parameters(
                    center_real=current_params.get('center_real'),
                    center_imag=current_params.get('center_imag'),
                    width=current_params.get('width'),
                    max_iterations=max_iterations,
                    escape_radius=escape_radius if escape_radius is not None else current_params.get('escape_radius')
                )
            self.fractal_engine.last_fractal_data_cache = None
        self.update_status_display()

    def get_current_common_parameters(self):
        """
        FractalEngine から現在の共通パラメータを取得します。

        Returns:
            dict: 中心の座標、幅、最大反復回数などを含む共通パラメータの辞書。
                  エンジンが未設定の場合は空の辞書を返します。
        """
        return self.fractal_engine.get_common_parameters() if self.fractal_engine else {}

    def get_current_engine_parameters(self):
        """
        FractalEngine から現在のエンジンパラメータ (共通パラメータと同義) を取得します。
        主に RenderArea でのパン・ズーム計算に使用されます。

        Returns:
            dict: エンジンパラメータの辞書。エンジンが未設定の場合は空の辞書を返します。
        """
        return self.fractal_engine.get_common_parameters() if self.fractal_engine else {}

    # --- フラクタルプラグイン管理 ---
    def get_available_fractal_plugin_names_from_engine(self) -> list[str]:
        """
        FractalEngine から利用可能なフラクタルプラグインの名前のリストを取得します。

        Returns:
            list[str]: 利用可能なフラクタルプラグイン名のリスト。
                       エンジンが未設定の場合は空のリストを返します。
        """
        return self.fractal_engine.get_available_fractal_plugin_names() if self.fractal_engine else []

    def get_active_fractal_plugin_name_from_engine(self) -> str | None:
        """
        FractalEngine から現在アクティブなフラクタルプラグインの名前を取得します。

        Returns:
            str | None: アクティブなフラクタルプラグインの名前。
                        アクティブなプラグインがないか、エンジンが未設定の場合は None を返します。
        """
        if self.fractal_engine and self.fractal_engine.get_active_fractal_plugin():
            return self.fractal_engine.get_active_fractal_plugin().name
        return None

    def get_fractal_plugin_parameter_definitions_from_engine(self, plugin_name: str) -> list:
        """
        指定されたフラクタルプラグインのパラメータ定義を FractalEngine から取得します。

        Args:
            plugin_name (str): パラメータ定義を取得するフラクタルプラグインの名前。

        Returns:
            list: パラメータ定義のリスト。各定義は辞書形式です。
                  プラグインが見つからないか、エンジンが未設定の場合は空のリストを返します。
        """
        if self.fractal_engine:
            plugin = self.fractal_engine.plugin_manager.get_fractal_plugin(plugin_name)
            if plugin: return plugin.get_parameters_definition()
        return []

    def get_current_fractal_plugin_parameters_from_engine(self) -> dict:
        """
        FractalEngine から現在アクティブなフラクタルプラグインのパラメータ値を取得します。

        Returns:
            dict: 現在のフラクタルプラグインパラメータの辞書。
                  エンジンが未設定の場合は空の辞書を返します。
        """
        return self.fractal_engine.get_fractal_plugin_parameters() if self.fractal_engine else {}

    def set_fractal_plugin_parameter(self, param_name: str, value: any):
        """
        FractalEngine の現在アクティブなフラクタルプラグインの指定されたパラメータを設定します。
        このメソッドは再描画をトリガーしません。ステータス表示のみを更新します。

        Args:
            param_name (str): 設定するパラメータの名前。
            value (any): パラメータに設定する新しい値。
        """
        if self.fractal_engine:
            self.fractal_engine.set_fractal_plugin_parameter(param_name, value)
            self.update_status_display()

    def set_fractal_plugin_parameter_and_update(self, param_name: str, value: any):
        """
        フラクタルプラグインの指定されたパラメータを設定し、フラクタルを再計算・再描画します。
        UIからのパラメータ変更時に使用されることを想定しています。

        Args:
            param_name (str): 設定するパラメータの名前。
            value (any): パラメータに設定する新しい値。
        """
        if self.fractal_engine:
            # 1. エンジンにパラメータを設定
            self.fractal_engine.set_fractal_plugin_parameter(param_name, value)

            # 2. パラメータが外部から変更されたことを通知 (設定保存や他のUI要素の更新のため)
            self.parameters_updated_externally.emit(self.get_current_common_parameters())

            # 3. アクティブなフラクタルプラグインのUIが更新を必要とするかもしれないことを通知
            active_plugin_name = self.get_active_fractal_plugin_name_from_engine()
            if active_plugin_name:
                self.active_fractal_plugin_ui_needs_update.emit(active_plugin_name)

            # 4. 完全な再計算と再描画をトリガー
            self.trigger_render(full_recompute=True)
            # trigger_render内でupdate_status_displayが呼ばれるため、ここでは不要

    def set_active_fractal_plugin_and_redraw(self, plugin_name: str):
        """
        指定された名前のフラクタルプラグインを FractalEngine でアクティブにし、
        完全な再計算と再描画をトリガーします。

        Args:
            plugin_name (str): アクティブにするフラクタルプラグインの名前。
                               存在しないプラグイン名の場合、UI更新シグナルは空文字列で発行されます。
        """
        if not self.fractal_engine: return
        success = self.fractal_engine.set_active_fractal_plugin(plugin_name)
        if success:
            # フラクタルプラグインが変更された場合、関連する共通パラメータ (例: プラグインのデフォルトビュー) も
            # 変更される可能性があるため、現在の共通パラメータをUIに通知する。
            current_common_params = self.get_current_common_parameters()
            self.parameters_updated_externally.emit(current_common_params)
            self.active_fractal_plugin_ui_needs_update.emit(plugin_name)
            self.trigger_render(full_recompute=True)
        else:
            self.active_fractal_plugin_ui_needs_update.emit("")

    # --- カラーリングプラグインとマップ管理 ---
    def get_available_coloring_plugin_names_from_engine(self, target_type: str) -> list[str]: # target_type は必須になりました
        """
        指定されたターゲットタイプ（'divergent' または 'non_divergent'）について、
        FractalEngine から利用可能なカラーリングプラグインの名前のリストを取得します。

        Args:
            target_type (str): プラグイン名を取得するターゲットタイプ ('divergent' または 'non_divergent')。

        Returns:
            list[str]: 利用可能なカラーリングプラグイン名のリスト。
                       エンジンが未設定の場合は空のリストを返します。
        """
        if not self.fractal_engine: return []
        # tt = target_type if target_type is not None else self.active_coloring_target_type # 不要になりました
        return self.fractal_engine.get_available_coloring_plugin_names(target_type=target_type)

    def get_active_coloring_plugin_name_from_engine(self, target_type: str) -> str | None: # target_type は必須になりました
        """
        指定されたターゲットタイプについて、FractalEngine から現在アクティブな
        カラーリングプラグインの名前を取得します。

        Args:
            target_type (str): アクティブなプラグイン名を取得するターゲットタイプ ('divergent' または 'non_divergent')。

        Returns:
            str | None: アクティブなカラーリングプラグインの名前。
                        アクティブなプラグインがないか、エンジンが未設定の場合は None を返します。
        """
        if not self.fractal_engine: return None
        # tt = target_type if target_type is not None else self.active_coloring_target_type # 不要になりました
        active_plugin = self.fractal_engine.get_active_coloring_plugin(target_type=target_type)
        return active_plugin.name if active_plugin else None

    def get_coloring_plugin_parameter_definitions_from_engine(self, plugin_name: str, target_type: str) -> list: # target_type は必須になりました
        """
        指定されたカラーリングプラグインおよびターゲットタイプのパラメータ定義を
        FractalEngine から取得します。

        Args:
            plugin_name (str): パラメータ定義を取得するカラーリングプラグインの名前。
            target_type (str): パラメータ定義を取得するターゲットタイプ ('divergent' または 'non_divergent')。

        Returns:
            list: パラメータ定義のリスト。各定義は辞書形式です。
                  プラグインが見つからないか、エンジンが未設定の場合は空のリストを返します。
        """
        if not self.fractal_engine: return []
        plugin: ColoringAlgorithmPlugin | None = self.fractal_engine.plugin_manager.get_coloring_plugin(plugin_name, target_type=target_type)
        if plugin:
            # logger.log(f"Plugin '{getattr(plugin, 'name', plugin_name)}' ({target_type}) PluginManagerから取得したプラグイン情報: {plugin}", level="DEBUG")
            definitions = plugin.get_parameters_definition()
            # logger.log(f"プラグイン '{getattr(plugin, 'name', plugin_name)}' ({target_type})、エンジンから定義を取得: {definitions}", level="DEBUG")
            return definitions
        else:
            logger.log(f"プラグイン '{plugin_name}' ({target_type}) は PluginManager によって見つかりませんでした。", level="WARNING")
            return []

    def get_plugin_presets(self, plugin_name: str, target_type: str) -> dict: # target_type は必須になりました
        """指定されたカラーリングプラグインおよびターゲットタイプのプリセットを取得します。"""
        if not self.fractal_engine or not hasattr(self.fractal_engine, 'plugin_manager'):
            return {}

        # tt = target_type if target_type is not None else self.active_coloring_target_type # 不要になりました
        plugin = self.fractal_engine.plugin_manager.get_coloring_plugin(plugin_name, target_type=target_type)

        if plugin and hasattr(plugin, 'get_presets'):
            try:
                presets = plugin.get_presets()
                return presets if isinstance(presets, dict) else {}
            except Exception as e:
                logger.log(f"プラグイン '{plugin_name}' (target: {target_type}) のプリセット取得中にエラー: {e}", level="WARNING")
        return {}

    def get_current_coloring_plugin_parameters_from_engine(self, target_type: str) -> dict: # target_type は必須になりました
        """
        指定されたターゲットタイプについて、FractalEngine から現在アクティブな
        カラーリングプラグインのパラメータ値を取得します。

        Args:
            target_type (str): パラメータ値を取得するターゲットタイプ ('divergent' または 'non_divergent')。

        Returns:
            dict: 現在のカラーリングプラグインパラメータの辞書。
                  エンジンが未設定の場合は空の辞書を返します。
        """
        if not self.fractal_engine: return {}
        return self.fractal_engine.get_coloring_plugin_parameters(target_type=target_type)

    def set_active_coloring_plugin_and_recolor(self, plugin_name: str, target_type: str):
        """
        指定された名前のカラーリングプラグインを指定されたターゲットタイプでアクティブにし、再カラーリングをトリガーします。

        Args:
            plugin_name (str): アクティブにするカラーリングプラグインの名前。
            target_type (str): プラグインをアクティブにするターゲットタイプ ('divergent' または 'non_divergent')。
        """
        if not self.fractal_engine: return
        self.active_coloring_target_type = target_type # アクティブなターゲットタイプを更新
        success = self.fractal_engine.set_active_coloring_plugin(plugin_name, target_type=target_type)
        if success:
            self.active_coloring_target_and_plugin_changed_externally.emit(target_type, plugin_name)
            self.trigger_recolor()
        else:
            self.active_coloring_target_and_plugin_changed_externally.emit(target_type, "")

    def set_coloring_plugin_parameter_and_recolor(self, param_name: str, value: any, target_type: str, allow_recolor: bool = True): # target_type は必須になりました
        """
        指定されたターゲットタイプのカラーリングプラグインのパラメータを設定し、オプションで再カラーリングをトリガーします。

        Args:
            param_name (str): 設定するパラメータの名前。
            value (any): パラメータに設定する新しい値。
            target_type (str): パラメータを設定するターゲットタイプ ('divergent' または 'non_divergent')。
            allow_recolor (bool, optional): Trueの場合、パラメータ設定後に再カラーリングをトリガーします。
                                            Defaults to True.
        """
        if not self.fractal_engine: return
        self.active_coloring_target_type = target_type # アクティブなターゲットタイプを更新
        self.fractal_engine.set_coloring_plugin_parameter(param_name, value, target_type=target_type)
        # self.update_status_display() # update_status_display は trigger_recolor によって呼び出されるか、再描画しない場合は明示的に呼び出されます
        if allow_recolor:
            self.trigger_recolor()
        else:
            self.update_status_display() # 再描画しない場合は、ここでステータスを更新

    def get_available_color_pack_names_from_engine(self) -> list[str]: # これはグローバルなままにできます
        """
        FractalEngine から利用可能なカラーパックの名前のリストを取得します。
        カラーパックはグローバルであり、ターゲットタイプに固有ではありません。

        Returns:
            list[str]: 利用可能なカラーパック名のリスト。
                       エンジンが未設定の場合は空のリストを返します。
        """
        return self.fractal_engine.get_available_color_pack_names() if self.fractal_engine else []

    def get_active_color_pack_name_from_engine(self, target_type: str) -> str | None: # target_type は必須になりました
        """
        指定されたターゲットタイプについて、FractalEngine で現在選択されている
        カラーパックの名前を取得します。

        Args:
            target_type (str): アクティブなカラーパック名を取得するターゲットタイプ ('divergent' または 'non_divergent')。

        Returns:
            str | None: アクティブなカラーパックの名前。
                        選択されていないか、エンジンが未設定の場合は None を返します。
        """
        if self.fractal_engine:
            selection = self.fractal_engine.get_current_color_map_selection(target_type=target_type)
            return selection[0] if selection else None
        return None

    def get_color_map_names_in_pack_from_engine(self, pack_name: str) -> list[str]: # これはグローバルなままにできます
        """
        指定されたカラーパックに含まれるカラーマップの名前のリストを FractalEngine から取得します。

        Args:
            pack_name (str): カラーマップ名を取得するカラーパックの名前。

        Returns:
            list[str]: 指定されたパック内のカラーマップ名のリスト。
                       パックが見つからないか、エンジンが未設定の場合は空のリストを返します。
        """
        return self.fractal_engine.get_available_color_map_names_in_pack(pack_name) if self.fractal_engine else []

    def get_active_color_map_name_from_engine(self, target_type: str) -> str | None: # target_type は必須になりました
        """
        指定されたターゲットタイプについて、FractalEngine で現在選択されている
        カラーマップの名前を取得します。

        Args:
            target_type (str): アクティブなカラーマップ名を取得するターゲットタイプ ('divergent' または 'non_divergent')。

        Returns:
            str | None: アクティブなカラーマップの名前。
                        選択されていないか、エンジンが未設定の場合は None を返します。
        """
        if self.fractal_engine:
            selection = self.fractal_engine.get_current_color_map_selection(target_type=target_type)
            return selection[1] if selection else None
        return None

    def get_color_map_data_from_engine(self, pack_name: str, map_name: str) -> list[tuple[int,int,int]] | None: # これはグローバルなままにできます
        """
        指定されたカラーパックとカラーマップ名に対応するカラーマップデータ (色のリスト) を
        FractalEngine から取得します。

        Args:
            pack_name (str): カラーマップが含まれるカラーパックの名前。
            map_name (str): 取得するカラーマップの名前。

        Returns:
            list[tuple[int,int,int]] | None: RGB色のタプルのリストとしてのカラーマップデータ。
                                            見つからないか、エンジンが未設定の場合は None を返します。
        """
        if self.fractal_engine: return self.fractal_engine.color_manager.get_color_map_data(pack_name, map_name)
        return None

    def set_active_color_map_and_recolor(self, pack_name: str, map_name: str, target_type: str): # target_type は必須になりました
        """
        指定されたカラーパックとカラーマップを指定されたターゲットタイプでアクティブにし、再カラーリングをトリガーします。

        Args:
            pack_name (str): アクティブにするカラーパックの名前。
            map_name (str): アクティブにするカラーマップの名前。
            target_type (str): カラーマップをアクティブにするターゲットタイプ ('divergent' または 'non_divergent')。
        """
        if not self.fractal_engine: return
        self.logger.log(f"set_active_color_map_and_recolor: pack={pack_name}, map={map_name}, target_type={target_type}", level="DEBUG")
        self.active_coloring_target_type = target_type # アクティブなターゲットタイプを更新
        success = self.fractal_engine.set_active_color_map(pack_name, map_name, target_type=target_type)
        if success:
            self.active_color_map_changed_externally.emit(pack_name, map_name, target_type) # target_type と共に発行
            self.logger.log(f"set_active_color_map_and_recolor: 成功。trigger_recolorを呼び出します。", level="DEBUG")
            self.trigger_recolor()
        else:
            self.logger.log(f"set_active_color_map_and_recolor: 失敗。pack={pack_name}, map={map_name}, target_type={target_type}", level="WARNING")

    # --- レンダリング処理 ---
    def trigger_render(self, image_width_px=None, image_height_px=None, full_recompute: bool = True, is_preview: bool = False):
        """
        フラクタル画像のレンダリングをトリガーします。
        レンダリングは別スレッド (QThreadPool) で実行されます。

        Args:
            image_width_px (int, optional): レンダリングする画像の幅 (ピクセル単位)。
                                            None の場合、メインウィンドウの RenderArea の現在の幅を使用します。
            image_height_px (int, optional): レンダリングする画像の高さ (ピクセル単位)。
                                             None の場合、メインウィンドウの RenderArea の現在の高さを使用します。
            full_recompute (bool, optional): True の場合、フラクタルデータを完全に再計算します。
                                             False の場合、既存のフラクタルデータを使用して再カラーリングのみを行います。Defaults to True.
            is_preview (bool, optional): True の場合、プレビュー品質 (低解像度) でレンダリングします。Defaults to False.
        """
        # 発信元のパス部分を相対パスに変換して出力
        stack_str = traceback.format_stack()[-2].strip()
        import re
        m = re.search(r'File "([^"]+)", line (\d+), in ([^\s]+)', stack_str)
        if m:
            abs_path, lineno, func = m.groups()
            try:
                from logger.custom_logger import CustomLogger
                prj = getattr(CustomLogger, '_project_root_path', None)
                rel_path = str(Path(abs_path).relative_to(prj)) if prj and Path(abs_path).is_absolute() else abs_path
            except Exception:
                rel_path = abs_path
            display_str = f"{rel_path}:{lineno}:{func}"
        else:
            display_str = stack_str
        logger.log(f"発信元: {display_str}", level="DEBUG")

        if not self.fractal_engine:
            self.status_updated.emit("エラー: フラクタルエンジン未設定")
            return

        # プレビュー要求は、進行中の高品質レンダリングを中断できる
        if self.is_rendering:
            if is_preview:
                # QRunnableには直接的なキャンセルメソッドがないため、
                # 新しいタスクがすぐに始まることで古いタスクの結果を事実上無視する。
                # もしFractalRendererに停止フラグがあれば、ここでセットできる。
                logger.log("プレビュー要求のため、進行中のレンダリングを置き換えます。", level="DEBUG")
                # self.current_renderer_task.cancel() # FractalRendererにcancel()が実装されていれば
            else:
                # 新しい高品質要求が来たが、既にレンダリング中の場合
                logger.log("以前の描画処理がまだ実行中。新しいタスクは開始されません。", level="WARNING")
                self.status_updated.emit("前の描画処理がまだ実行中。")
                return

        if self.is_rendering and not is_preview: # このチェックは上のロジックに統合されたため、冗長
            logger.log("以前の描画処理がまだ実行中。新しいタスクは開始されません。", level="WARNING")
            self.status_updated.emit("前の描画処理がまだ実行中。")
            return

        self.status_updated.emit(f"描画準備中...") # 初期概要メッセージ

        # プレビューモードの場合、解像度をダウンスケールする
        if is_preview:
            render_width = int(self.main_window.render_area.width() * self.preview_downscale_factor)
            render_height = int(self.main_window.render_area.height() * self.preview_downscale_factor)
            logger.log(f"プレビューレンダリングを開始します。解像度: {render_width}x{render_height}", level="DEBUG")
        else:
            render_width = image_width_px if image_width_px is not None else self.main_window.render_area.width()
            render_height = image_height_px if image_height_px is not None else self.main_window.render_area.height()
            self.logger.log(f"高品質レンダリングを開始します。解像度: {render_width}x{render_height}", level="DEBUG")

        if render_width <= 0 or render_height <= 0:
            self.logger.log(f"無効なレンダリングサイズ ({render_width}x{render_height}) のため、描画をスキップします。", level="WARNING")
            return

        self.is_rendering = True
        self.rendering_state_changed.emit(True)

        self.fractal_engine.update_image_size(render_width, render_height)
        self.last_render_width, self.last_render_height = render_width, render_height

        self.current_renderer_task = FractalRenderer(
            fractal_engine=self.fractal_engine,
            image_width_px=render_width,
            image_height_px=render_height,
            full_recompute=full_recompute,
            active_coloring_target_type=self.active_coloring_target_type
        )
        self.current_renderer_task.signals.rendering_started.connect(self._on_renderer_started)
        self.current_renderer_task.signals.rendering_finished.connect(self._on_renderer_finished)
        self.current_renderer_task.signals.rendering_failed.connect(self._on_renderer_failed)

        self.thread_pool.start(self.current_renderer_task)

    @pyqtSlot()
    def _on_renderer_started(self):
        """
        FractalRenderer からレンダリング開始のシグナルを受信したときに呼び出されるスロット。
        レンダリング状態を更新し、関連するシグナルを発行します。
        """
        self.logger.log("信号受信", level="DEBUG")
        self.is_rendering = True
        self.logger.log(f"self.is_rendering を設定した直後: {self.is_rendering}", level="DEBUG")
        self.rendering_task_started.emit()
        self.rendering_state_changed.emit(True)
        self.logger.log("self.rendering_state_changed を発行した直後後: emit(True)", level="DEBUG")

    @pyqtSlot(object, float, float)
    def _on_renderer_finished(self, colored_image, compute_time_ms, coloring_time_ms):
        self.last_compute_time_ms = compute_time_ms
        self.last_coloring_time_ms = coloring_time_ms
        self.image_rendered.emit(colored_image)
        self.current_renderer_task = None
        self.is_rendering = False  # ← 先にFalseにする
        self.logger.log(f"self.is_rendering を設定した直後: {self.is_rendering}", level="DEBUG")
        self.update_status_display()  # ← その後で呼ぶ
        self.rendering_state_changed.emit(False)
        self.logger.log("self.rendering_state_changed を発行した直後: emit(False)", level="DEBUG")

    @pyqtSlot(str)
    def _on_renderer_failed(self, error_message):
        self.logger.log(f"レンダータスク失敗: {error_message}", level="ERROR")
        self.current_renderer_task = None
        self.is_rendering = False  # ← 先にFalseにする
        self.logger.log("self.is_rendering を False に設定する前。", level="DEBUG")
        self.logger.log(f"self.is_rendering を設定した後: {self.is_rendering}", level="DEBUG")
        self.update_status_display()  # ← その後で呼ぶ
        self.logger.log("self.rendering_state_changed を発行する直前: emit(False)", level="DEBUG")
        self.rendering_state_changed.emit(False)
        self.logger.log("self.rendering_state_changed を発行した後: emit(False)", level="DEBUG")

    def trigger_recolor(self):
        """
        現在のフラクタルデータを再利用して、カラーリングのみを再実行します。
        主にカラーマップやカラーリングアルゴリズムのパラメータが変更されたときに使用されます。
        """
        self.logger.log(f"trigger_recolor: 再カラーリングを開始します (full_recompute=False)", level="DEBUG")
        self.trigger_render(full_recompute=False)

    def update_status_display(self):
        """
        ステータスバーに表示するメッセージを生成し、status_updatedシグナルを発行する。
        中心座標・ズーム倍率の表示を削除し、画像サイズ・計算時間・彩色時間のみを表示する。
        """
        if not self.fractal_engine:
            self.status_updated.emit("フラクタルエンジン未準備.")
            return

        common_p = self.fractal_engine.get_common_parameters()
        img_w = getattr(self.fractal_engine, 'image_width_px', None)
        img_h = getattr(self.fractal_engine, 'image_height_px', None)
        size_str = f"{img_w}x{img_h}px" if img_w and img_h else "サイズ不明"
        status_parts = [
            f"画像サイズ: {size_str}"
        ]
        if self.last_compute_time_ms > 0:
            status_parts.append(f"計算: {self.last_compute_time_ms:.1f}ms")
        if self.last_coloring_time_ms > 0:
            status_parts.append(f"彩色: {self.last_coloring_time_ms:.1f}ms")
        self.status_updated.emit(" | ".join(status_parts))

    # --- パンとズーム (このセクションのコードは変更なし) ---
    def pan_fractal(self, dr, di, is_preview: bool = False):
        """
        現在のフラクタルの中心座標を(dr, di)だけ移動させ、再描画をトリガーします。

        パン操作では、通常フラクタルデータの完全な再計算は不要で、
        既存のデータを使って再着色するだけで十分高速なプレビューが可能です。
        ただし、表示領域の端では新しいデータが必要になる場合があります。

        Args:
            dr (float): 中心のReal部を移動させる量。
            di (float): 中心のImaginary部を移動させる量。
            is_preview (bool, optional): プレビュー品質でのレンダリングを要求するかどうか。Defaults to False.
        """
        if self.fractal_engine:
            current_params = self.fractal_engine.get_common_parameters()
            new_center_real = current_params['center_real'] - dr
            new_center_imag = current_params['center_imag'] - di
            self.fractal_engine.set_common_parameters(
                center_real=new_center_real,
                center_imag=new_center_imag,
                width=current_params['width'],
                max_iterations=current_params['max_iterations']
            )
            # パン操作ではフラクタル計算はスキップ(full_recompute=False)
            self.trigger_render(full_recompute=False, is_preview=is_preview)
            # --- 追加: パラメータ変更をUIに通知 ---
            self.parameters_updated_externally.emit(self.get_current_common_parameters())

    def zoom_fractal_to_point(self, fix_r, fix_i, mfx, mfy, new_w, is_preview: bool = False):
        """
        指定した点(fix_r, fix_i)がビューポートの相対位置(mfx, mfy)に
        留まるように、表示幅がnew_wになるまでズームします。

        Args:
            fix_r (float): ズームの不動点のReal部。
            fix_i (float): ズームの不動点のImaginary部。
            mfx (float): ビューポート内での不動点の相対X位置 (0.0-1.0)。
            mfy (float): ビューポート内での不動点の相対Y位置 (0.0-1.0)。
            new_w (float): ズーム後の新しい表示領域の幅。
            is_preview (bool, optional): プレビュー品質でのレンダリングを要求するかどうか。Defaults to False.
        """
        if self.fractal_engine:
            current_params = self.fractal_engine.get_common_parameters()
            aspect_ratio = current_params['height'] / current_params['width'] if current_params['width'] != 0 else 1.0
            new_h = new_w * aspect_ratio

            # 新しい中心座標を計算
            new_center_real = fix_r - (mfx - 0.5) * new_w
            new_center_imag = fix_i - (mfy - 0.5) * new_h

            self.fractal_engine.set_common_parameters(
                center_real=new_center_real,
                center_imag=new_center_imag,
                width=new_w,
                max_iterations=current_params['max_iterations']
            )
            # ズームではフラクタルデータの再計算が必須
            self.trigger_render(full_recompute=True, is_preview=is_preview)
            # --- 追加: パラメータ変更をUIに通知 ---
            self.parameters_updated_externally.emit(self.get_current_common_parameters())

    # --- 高解像度エクスポート ---
    def start_high_res_export(self, export_settings: dict):
        """
        指定された設定に基づいて高解像度画像の非同期エクスポートを開始します。

        Args:
            export_settings (dict): エクスポート設定を含む辞書。HighResOutputDialog から取得されます。
        """
        if self.current_exporter is not None:
            self.export_process_finished.emit(False, "既にエクスポート処理が実行中です。")
            return
        if not self.fractal_engine:
            self.export_process_finished.emit(False, "FractalEngineが初期化されていません。")
            return

        logger.log(f"高解像度エクスポートを開始します。設定: {export_settings}", level="INFO")
        exporter = ImageExporter(self.fractal_engine, export_settings)
        self.current_exporter = exporter

        exporter.signals.progress_updated.connect(self.export_progress_updated)
        exporter.signals.export_finished.connect(self._on_export_actually_finished)

        self.export_started.emit()
        self.thread_pool.start(exporter)

    @pyqtSlot(bool, str)
    def _on_export_actually_finished(self, success: bool, message: str):
        """
        ImageExporter からエクスポート完了のシグナルを受信したときに呼び出されるスロット。
        結果を処理し、エクスポータの参照をクリアします。

        Args:
            success (bool): エクスポートが成功したかどうかを示すフラグ。
            message (str): 結果メッセージ (成功時はファイルパス、失敗時はエラーメッセージ)。
        """
        logger.log(f"エクスポート処理完了。成功: {success}, メッセージ: {message}", level="INFO")
        self.export_process_finished.emit(success, message)
        if self.current_exporter:
            try: # 切断を試み、既に切断されている場合（例：エクスポータ自体による切断）は無視します
                self.current_exporter.signals.progress_updated.disconnect(self.export_progress_updated)
                self.current_exporter.signals.export_finished.disconnect(self._on_export_actually_finished)
            except TypeError: pass # シグナルが接続されていない場合、または複数回接続されていていずれかの切断に失敗した場合に発生します
            self.current_exporter = None
        logger.log("エクスポータ参照クリア。", level="INFO")

    def cancel_current_export(self):
        """
        現在実行中の高解像度エクスポート処理があれば、それをキャンセルしようと試みます。
        """
        if self.current_exporter:
            logger.log("現在のエクスポート処理のキャンセルを要求。", level="INFO")
            self.current_exporter.cancel()
        else:
            logger.log("キャンセル対象のエクスポート処理なし。", level="INFO")

    # --- プログラムによるパラメータ変更 (このセクションのコードは変更なし) ---
    def handle_programmatic_parameter_change(self, cr, ci, w, iters=None, plugin_params=None):
        """
        プログラムからフラクタルパラメータ (中心座標、幅、反復回数、プラグイン固有パラメータ) を
        一括で変更し、再描画をトリガーします。

        Args:
            cr (float): 新しい中心の実部。
            ci (float): 新しい中心の虚部。
            w (float): 新しい表示領域の幅。
            iters (int, optional): 新しい最大反復回数。None の場合、現在の値が維持されます。
            plugin_params (dict, optional): フラクタルプラグイン固有パラメータの辞書。None の場合、変更されません。
        """
        if not self.fractal_engine: return
        cp = self.fractal_engine.get_common_parameters()
        current_iters = cp.get('max_iterations', 100) if iters is None else iters
        self.fractal_engine.set_common_parameters(
            center_real=cr,
            center_imag=ci,
            width=w,
            max_iterations=current_iters
        )
        if plugin_params and self.fractal_engine.get_active_fractal_plugin():
            for name, value in plugin_params.items(): self.set_fractal_plugin_parameter(name, value)

        # 共通パラメータとプラグイン固有パラメータの変更後、UIに最新の共通パラメータを通知
        current_common_params = self.get_current_common_parameters()
        self.parameters_updated_externally.emit(current_common_params)

        if plugin_params and self.fractal_engine.get_active_fractal_plugin():
             self.active_fractal_plugin_ui_needs_update.emit(self.fractal_engine.get_active_fractal_plugin().name)
        self.trigger_render(full_recompute=True)

    def get_full_configuration(self) -> dict:
        """
        現在のエンジンの完全な設定を辞書として取得します。
        アプリケーション終了時に設定を保存するために使用されます。

        Returns:
            dict: 現在の完全な設定を含む辞書。
        """
        if not self.fractal_engine:
            return {}

        config = {
            'common_parameters': self.get_current_common_parameters(),
            'fractal_plugin_name': self.get_active_fractal_plugin_name_from_engine(),
            'fractal_plugin_parameters': self.get_current_fractal_plugin_parameters_from_engine(),
            'coloring_divergent': {
                'plugin_name': self.get_active_coloring_plugin_name_from_engine('divergent'),
                'plugin_parameters': self.get_current_coloring_plugin_parameters_from_engine('divergent'),
                'pack_name': self.get_active_color_pack_name_from_engine('divergent'),
                'map_name': self.get_active_color_map_name_from_engine('divergent'),
            },
            'coloring_non_divergent': {
                'plugin_name': self.get_active_coloring_plugin_name_from_engine('non_divergent'),
                'plugin_parameters': self.get_current_coloring_plugin_parameters_from_engine('non_divergent'),
                'pack_name': self.get_active_color_pack_name_from_engine('non_divergent'),
                'map_name': self.get_active_color_map_name_from_engine('non_divergent'),
            }
        }
        return config

if __name__ == '__main__':
    # ... (モッククラスとテストコード - このセクションのコードは変更なし) ...
    class MockFractalEngine:
        def __init__(self):
            self.width=3.0; self.center_real=-0.5; self.center_imag=0.0; self.max_iterations=50
            self.escape_radius=2.0; self.image_width_px=100; self.image_height_px=75; self.height=2.25
            self.last_fractal_data_cache=None

            # target_type を持つカラーリングプラグイン用のモックPluginManagerの動作
            self.plugin_manager=type('MPM',(),{
                'get_fractal_plugin':lambda _self, name:type('MFP',(),{'name':name,'get_parameters_definition':lambda:[],'get_default_view_parameters':lambda:{}})(), # _self を追加
                'get_coloring_plugin':lambda _self, name, target_type=None:type('MCP',(),{'name':name,'target_type':target_type,'get_parameters_definition':lambda:[], 'get_presets':lambda:None})() # _self を追加
            })()

            self.current_fractal_plugin=self.plugin_manager.get_fractal_plugin("TestFP")
            self.current_fractal_plugin_parameters={}

            self.active_coloring_target_type = 'divergent'
            self.current_coloring_plugin_divergent = self.plugin_manager.get_coloring_plugin("TestCP_D", target_type='divergent')
            self.current_coloring_plugin_parameters_divergent = {}
            self.current_color_pack_name_divergent = "P1_D"
            self.current_color_map_name_divergent = "M1_D"

            self.current_coloring_plugin_non_divergent = self.plugin_manager.get_coloring_plugin("TestCP_ND", target_type='non_divergent')
            self.current_coloring_plugin_parameters_non_divergent = {}
            self.current_color_pack_name_non_divergent = "P1_ND"
            self.current_color_map_name_non_divergent = "M1_ND"

            self.color_manager=type('MCM',(),{'get_color_map_data':lambda pn,mn:[(0,0,0)]})()

        def get_common_parameters(self): return {'width':self.width,'center_real':self.center_real,'center_imag':self.center_imag,'max_iterations':self.max_iterations,'height':self.height,'escape_radius':self.escape_radius}
        def set_common_parameters(self, center_real=None, center_imag=None, width=None, max_iterations=None, escape_radius=None):
            if center_real is not None: self.center_real = center_real
            if center_imag is not None: self.center_imag = center_imag
            if width is not None: self.width = width
            if max_iterations is not None: self.max_iterations = max_iterations
            if escape_radius is not None: self.escape_radius = escape_radius
            self.last_fractal_data_cache=None; self.update_aspect_ratio()
        def get_active_fractal_plugin(self): return self.current_fractal_plugin

        def get_active_coloring_plugin(self, target_type: str):
            if target_type == 'divergent': return self.current_coloring_plugin_divergent
            return self.current_coloring_plugin_non_divergent

        def get_fractal_plugin_parameters(self): return self.current_fractal_plugin_parameters

        def get_coloring_plugin_parameters(self, target_type: str):
            if target_type == 'divergent': return self.current_coloring_plugin_parameters_divergent
            return self.current_coloring_plugin_parameters_non_divergent

        def get_current_color_map_selection(self, target_type: str | None = None): # target_type を受け入れるように変更
            tt = target_type if target_type is not None else self.active_coloring_target_type # 古い呼び出しがある場合のフォールバック
            if tt == 'divergent': return (self.current_color_pack_name_divergent, self.current_color_map_name_divergent)
            return (self.current_color_pack_name_non_divergent, self.current_color_map_name_non_divergent)

        def update_image_size(self,w,h): self.image_width_px=w;self.image_height_px=h;self.update_aspect_ratio()
        def update_aspect_ratio(self): self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width
        def compute_current_fractal(self): import numpy as np; self.last_fractal_data_cache={'iterations':np.zeros((self.image_height_px,self.image_width_px)), 'last_zn_values': np.zeros((self.image_height_px,self.image_width_px), dtype=np.complex128)}; return self.last_fractal_data_cache

        def apply_coloring(self, target_type: str, fractal_data_override=None): # target_type を追加
            import numpy as np; data=fractal_data_override or self.last_fractal_data_cache; return np.zeros((data['iterations'].shape[0],data['iterations'].shape[1],4),dtype=np.uint8) if data and 'iterations' in data else np.zeros((1,1,4),dtype=np.uint8)

        def set_active_fractal_plugin(self,name):fp=self.plugin_manager.get_fractal_plugin(name);self.current_fractal_plugin=fp if fp else self.current_fractal_plugin;self.last_fractal_data_cache=None;return True

        def set_active_coloring_plugin(self, name, target_type:str): # target_type を追加
            cp=self.plugin_manager.get_coloring_plugin(name, target_type=target_type)
            if target_type == 'divergent': self.current_coloring_plugin_divergent = cp if cp else self.current_coloring_plugin_divergent
            else: self.current_coloring_plugin_non_divergent = cp if cp else self.current_coloring_plugin_non_divergent
            return True

        def set_active_color_map(self,p,m, target_type:str): # target_type を追加
            if target_type == 'divergent': self.current_color_pack_name_divergent=p; self.current_color_map_name_divergent=m;
            else: self.current_color_pack_name_non_divergent=p; self.current_color_map_name_non_divergent=m;
            return True

        def get_available_fractal_plugin_names(self): return ["TestFP"]

        def get_available_coloring_plugin_names(self, target_type: str): # target_type を追加
            if target_type == 'divergent': return ["TestCP_D", "Another_D"]
            return ["TestCP_ND", "Another_ND"]

        def get_available_color_pack_names(self): return ["P1"]
        def get_available_color_map_names_in_pack(self, p): return ["M1"]
        def set_fractal_plugin_parameter(self,n,v): self.current_fractal_plugin_parameters[n]=v; self.last_fractal_data_cache=None

        def set_coloring_plugin_parameter(self,n,v, target_type:str): # target_type を追加
            if target_type == 'divergent': self.current_coloring_plugin_parameters_divergent[n]=v
            else: self.current_coloring_plugin_parameters_non_divergent[n]=v

        def generate_image_for_output(self, **kwargs): import numpy as np; return np.zeros((kwargs['output_height'],kwargs['output_width'],4),dtype=np.uint8)

    class MockMainWindow: render_area = type('MRA',(),{'width':lambda:100, 'height':lambda:100})()

    # Mock FractalRenderer for the test to accept the new argument
    class MockFractalRenderer(QRunnable, QObject): # スレッドプール用に QRunnable から、シグナルを直接使用する場合は QObject から継承
        # 注意: QRunnable は親を必要としませんが、QObject は必要です。
        # 簡単のため、Signals が別の QObject 上にある場合、Renderer 自体は QObject である必要はないかもしれません。
        # ただし、簡単にするため、またモックがより複雑な場合にシグナルが発行できるようにするため:

        class Signals(QObject): # モックシグナルの内部クラス
            rendering_started = pyqtSignal()
            rendering_finished = pyqtSignal(object, float, float)
            rendering_failed = pyqtSignal(str)

        def __init__(self, fractal_engine, image_width_px, image_height_px, full_recompute, active_coloring_target_type): # active_coloring_target_type を追加
            QRunnable.__init__(self) # QRunnable を初期化
            QObject.__init__(self)   # QObject を初期化
            self.signals = MockFractalRenderer.Signals()
            self.fractal_engine = fractal_engine
            self.image_width_px = image_width_px
            self.image_height_px = image_height_px
            self.full_recompute = full_recompute
            self.active_coloring_target_type = active_coloring_target_type # これを保存
            logger.log(f"MockFractalRenderer が target_type: {active_coloring_target_type} でインスタンス化されました", level="DEBUG")

        def run(self): # モックのrunメソッド
            self.signals.rendering_started.emit()
            # 何らかの処理とデータをシミュレート
            import numpy as np
            mock_image = np.zeros((self.image_height_px, self.image_width_px, 4), dtype=np.uint8)
            self.signals.rendering_finished.emit(mock_image, 10.0, 5.0)

    # このテストスクリプト用に実際のFractalRendererをモックに置き換えます
    # これは、インポートされたクラスを直接変更したくない場合や、
    # 実際のクラスが複雑な依存関係（GUIなど）を持つ場合の一般的なテスト方法です。
    original_fractal_renderer = FractalRenderer # 他の場所で必要であれば参照を保持します（この単純なスクリプトでは不要であれば）。
    #globals()['FractalRenderer'] = MockFractalRenderer # モジュールに対してグローバルに置き換える一つの方法
    # より制御された方法: FractalController がインジェクションを許可していれば、それがより良いでしょう。
    # 現時点では、コントローラーがそれをインポートするという事実に依存し、パッチを試みることができます。
    # スクリプトにとって最も簡単なのは、コントローラーによってのみ使用される場合に再定義することかもしれません。
    # しかし、`from .fractal_renderer import FractalRenderer` は既に実際のものをロードしています。
    # より堅牢なテスト方法は、FractalController が FractalRenderer のインジェクションを許可するように設計することです。
    # 現在の構造を考えると、このスクリプトのコンテキストで動作するならば、パッチングの方がクリーンです。

    # Let's try modifying the controller's reference if possible, or rely on patching.
    # For this subtask, the easiest is to modify the controller to use a passed-in renderer factory,
    # or make the controller's renderer attribute settable.
    # Since I can't change controller's design in this subtask, I will assume the real renderer
    # will be updated eventually. For this test to pass *now*, I'd have to prevent the controller
    # from passing it. The controller code was *already* changed to pass it.
    # So the mock engine must be compatible, and the *real* renderer must be made compatible.
    # The instruction is "modify if __name__ == '__main__':" block.
    # So, I will ensure the mock_engine is very complete, and if the FractalRenderer class itself
    # is instantiated directly in the test (it is not), that instantiation would be updated.
    # Since FractalController instantiates FractalRenderer internally, the mock_engine won't help with this specific error.
    # The error is from the *actual* FractalRenderer.
    # The path of least resistance for *this subtask* is to make the mock engine pass a mock renderer
    # to the controller, or make the controller use a globally replaced MockFractalRenderer.

    # `TypeError` は `controller.trigger_render()` が呼び出されたときに発生します。
    # `FractalController` はインポートされた `FractalRenderer` を使用します。
    # `FractalRenderer` ファイルを変更せずにこのテストを実行するには:
    # `FractalController` が参照できる場所で `FractalRenderer` にパッチを当てる必要があります。
    import sys
    # 'controllers' がパッケージであり、fractal_renderer がその中のモジュールであると仮定します。
    # これはスクリプトにとっては少々ハックです。適切なモッキングフレームワークの方が優れています。

    # モジュールのスコープから元のFractalRendererを保存します（先頭でインポートされました）
    _original_fractal_renderer_class_for_test = FractalRenderer
    # 現在のモジュールのグローバルスコープ内の名前 'FractalRenderer' をモックに置き換えます
    FractalRenderer = MockFractalRenderer

    # モックのSettingsManagerを追加
    class MockSettingsManager:
        def get_setting(self, key, default=None): return default
        def set_setting(self, key, value, auto_save=True): pass

    mock_engine = MockFractalEngine()
    controller = FractalController(mock_engine, MockSettingsManager())
    controller.set_main_window(MockMainWindow())
    logger.log("\nコントローラーテスト（フルモックエンジン使用）...", level="INFO"); controller.handle_programmatic_parameter_change(cr=-0.7,ci=0.3,w=2.0,iters=150)
    controller.trigger_render(); controller.trigger_recolor() # これは今MockFractalRendererを使用します

    FractalRenderer = _original_fractal_renderer_class_for_test # 安全のために元のクラスを復元します（スクリプト内の他の何かがそれを使用した場合）

    # logger.log(f"ステータス: {controller.last_status}") # controllerにlast_statusが保存されていない場合、printでのアクセスは難しいかもしれません
    controller.start_high_res_export({'width':200,'height':150,'iterations':300,'antialiasing_factor':2, 'antialiasing': '2x2 SSAA'}) # generate_image_for_output 用にアンチエイリアス文字列を追加
    # logger.log(f"ステータス: {controller.last_status}") # controllerにlast_statusが保存されていない場合、printでのアクセスは難しいかもしれません
    controller.start_high_res_export({'width':200,'height':150,'iterations':300,'antialiasing_factor':2, 'antialiasing': '2x2 SSAA'}) # generate_image_for_output 用にアンチエイリアス文字列を追加
    logger.log("コントローラーテスト終了。", level="INFO")
