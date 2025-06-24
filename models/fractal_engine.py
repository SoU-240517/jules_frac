import numpy as np
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from plugins.plugin_manager import PluginManager
from plugins.base_fractal_plugin import FractalPlugin
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
from coloring.color_manager import ColorManager
from logger.custom_logger import CustomLogger

if TYPE_CHECKING:
    from utils.settings_manager import SettingsManager

logger = CustomLogger()

class FractalEngine:
    """
    フラクタル画像の計算、カラーリング、および関連パラメータ管理を行うコアエンジン。

    プラグインシステムを介して様々なフラクタルアルゴリズムとカラーリング手法をサポートし、
    高解像度画像の出力機能も提供します。
    """
    def __init__(self, project_root_path: Path, image_width_px=800, image_height_px=600,
                 settings_manager: 'SettingsManager | None' = None, fractal_plugin_folder="plugins/fractals",  # project_root_pathからの相対パス
                 coloring_plugin_folder="plugins/coloring", # 同上
                 color_pack_folder="plugins/colorpacks"):   # 同上
        """
        FractalEngineを初期化します。

        Args:
            project_root_path (Path): プロジェクトのルートディレクトリへのパス。プラグインやカラーパックの読み込みに使用されます。
            settings_manager (SettingsManager, optional): 設定管理クラスのインスタンス。
            image_width_px (int): プレビュー表示用のデフォルト画像幅 (ピクセル単位)。
            image_height_px (int): プレビュー表示用のデフォルト画像高さ (ピクセル単位)。
            fractal_plugin_folder (str): `project_root_path` からのフラクタルプラグインフォルダへの相対パス。
            coloring_plugin_folder (str): `project_root_path` からのカラーリングプラグインフォルダへの相対パス。
            color_pack_folder (str): `project_root_path` からのカラーパックフォルダへの相対パス。
        """
        self.settings_manager: 'SettingsManager | None' = settings_manager
        self.max_iterations = 100
        self.center_real = -0.5
        self.center_imag = 0.0
        self.width = 3.0
        self.escape_radius = 2.0

        self.image_width_px = image_width_px if image_width_px > 0 else 800
        self.image_height_px = image_height_px if image_height_px > 0 else 600
        self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width

        self.plugin_manager = PluginManager(
            project_root_path=project_root_path,
            fractal_plugin_folder_path=fractal_plugin_folder,
            divergent_coloring_plugin_folder_path="plugins/coloring/divergent",
            non_divergent_coloring_plugin_folder_path="plugins/coloring/non_divergent"
        )
        # ColorManagerもプロジェクトルートからの相対パスで初期化するのが望ましいです
        self.color_manager = ColorManager(color_packs_dir=str(project_root_path / color_pack_folder))

        self.current_fractal_plugin: FractalPlugin | None = None
        self.current_fractal_plugin_parameters: dict = {}

        self.active_coloring_target_type: str = 'divergent' # デフォルトのアクティブターゲット、ロードされた設定によって上書きされる場合があります

        self.current_coloring_plugin_divergent: ColoringAlgorithmPlugin | None = None
        self.current_coloring_plugin_parameters_divergent: dict = {}
        self.current_color_pack_name_divergent: str | None = None
        self.current_color_map_name_divergent: str | None = None

        self.current_coloring_plugin_non_divergent: ColoringAlgorithmPlugin | None = None
        self.current_coloring_plugin_parameters_non_divergent: dict = {}
        self.current_color_pack_name_non_divergent: str | None = None
        self.current_color_map_name_non_divergent: str | None = None

        self.last_fractal_data_cache: dict | None = None

        # 設定のロードを試みる
        if self.settings_manager:
            engine_saved_settings = self.settings_manager.get_setting("engine_settings")
            if engine_saved_settings and isinstance(engine_saved_settings, dict):
                self.load_settings(engine_saved_settings)
                logger.log("エンジン設定適用完了", level="INFO")
            else:
                logger.log("保存されたエンジン設定が見つからないか形式が不正です。デフォルト設定を試みます。", level="INFO")
        else:
            logger.log("SettingsManager が未提供のため、デフォルト設定を試みます。", level="INFO")

        # デフォルトプラグインとカラーマップの初期化 (まだ設定されていない場合)
        self._initialize_default_plugins_and_map()

    def _initialize_default_plugins_and_map(self):
        """
        利用可能なプラグインとカラーマップから、デフォルトのものを選択して初期設定します。
        Mandelbrotやスムーズカラーなど、一般的なものが優先的に選択されます。
        DivergentとNon-Divergentの両方のカラーリングコンテキストを初期化します。
        """
        # フラクタルプラグイン
        if self.current_fractal_plugin is None:
            available_fractal_plugins = self.get_available_fractal_plugin_names()
            if available_fractal_plugins:
                default_fractal = "Mandelbrot"
                if default_fractal in available_fractal_plugins: self.set_active_fractal_plugin(default_fractal)
                else: self.set_active_fractal_plugin(available_fractal_plugins[0])
            else: logger.log("フラクタルプラグインが見つかりません。フラクタル機能のデフォルト設定をスキップします。", level="WARNING")

        # 発散部カラーリングプラグイン
        if self.current_coloring_plugin_divergent is None:
            available_div_plugins = self.get_available_coloring_plugin_names(target_type='divergent')
            if available_div_plugins:
                default_div_coloring = "スムーズカラー"
                if default_div_coloring in available_div_plugins:
                    self.set_active_coloring_plugin(default_div_coloring, target_type='divergent')
                else:
                    self.set_active_coloring_plugin(available_div_plugins[0], target_type='divergent')
            else:
                logger.log("発散部カラーリングプラグインが見つかりません。発散部カラーリングのデフォルト設定をスキップします。", level="WARNING")

        # 非発散部カラーリングプラグイン
        if self.current_coloring_plugin_non_divergent is None:
            available_nondiv_plugins = self.get_available_coloring_plugin_names(target_type='non_divergent')
            if available_nondiv_plugins:
                default_nondiv_coloring = "複素ポテンシャル"
                if default_nondiv_coloring in available_nondiv_plugins:
                    self.set_active_coloring_plugin(default_nondiv_coloring, target_type='non_divergent')
                else:
                    self.set_active_coloring_plugin(available_nondiv_plugins[0], target_type='non_divergent')
            else:
                logger.log("非発散部カラーリングプラグインが見つかりません。非発散部カラーリングのデフォルト設定をスキップします。", level="WARNING")

        # デフォルトカラーマップ
        available_color_packs = self.get_available_color_pack_names()

        if self.current_color_pack_name_divergent is None or self.current_color_map_name_divergent is None:
            if available_color_packs:
                pack_to_try = "デフォルト"
                if pack_to_try not in available_color_packs: pack_to_try = available_color_packs[0]
                maps_in_pack = self.get_available_color_map_names_in_pack(pack_to_try)
                if maps_in_pack:
                    self.set_active_color_map(pack_to_try, maps_in_pack[0], target_type='divergent')

        if self.current_color_pack_name_non_divergent is None or self.current_color_map_name_non_divergent is None:
            if available_color_packs:
                pack_to_try = "デフォルト"
                if pack_to_try not in available_color_packs: pack_to_try = available_color_packs[0]
                maps_in_pack = self.get_available_color_map_names_in_pack(pack_to_try)
                if maps_in_pack:
                    self.set_active_color_map(pack_to_try, maps_in_pack[0], target_type='non_divergent')

        if not available_color_packs and \
           (self.current_color_pack_name_divergent is None or self.current_color_map_name_divergent is None or \
            self.current_color_pack_name_non_divergent is None or self.current_color_map_name_non_divergent is None):
             logger.log("カラーパックが見つかりません。カラーマップのデフォルト設定の一部または全てをスキップしました。", level="WARNING")

    def update_image_size(self, image_width_px, image_height_px):
        """
        プレビュー画像のピクセルサイズを更新し、アスペクト比を再計算します。

        Args:
            image_width_px (int): 新しい画像幅 (ピクセル単位)。
            image_height_px (int): 新しい画像高さ (ピクセル単位)。
        """
        self.image_width_px = image_width_px if image_width_px > 0 else self.image_width_px
        self.image_height_px = image_height_px if image_height_px > 0 else self.image_height_px
        self.update_aspect_ratio()

    def update_aspect_ratio(self):
        """
        現在の画像ピクセルサイズに基づいて、複素平面上の表示領域の高さを更新します。
        複素平面上の幅 (`self.width`) は変更しません。
        """
        if self.image_width_px > 0 and self.image_height_px > 0 :
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else: self.height = self.width

    def set_common_parameters(self, center_real, center_imag, width, max_iterations, escape_radius=None):
        """
        フラクタル計算の共通パラメータを設定します。

        Args:
            center_real (float): 複素平面上の中心点のReal部。
            center_imag (float): 複素平面上の中心点のImaginary部。
            width (float): 複素平面上の表示領域の幅。高さはアスペクト比から自動計算されます。
            max_iterations (int): 最大反復回数。
            escape_radius (float, optional): 発散判定の半径。Noneの場合は現在の値を維持します。
        """
        self.center_real=center_real; self.center_imag=center_imag; self.width=width; self.max_iterations=max_iterations
        if escape_radius is not None: self.escape_radius = escape_radius
        self.update_aspect_ratio()
        self.last_fractal_data_cache = None # キャッシュを無効化

    def get_common_parameters(self) -> dict:
        """
        現在のフラクタル計算の共通パラメータを取得します。

        Returns:
            dict: 以下のキーを含む辞書:
                  'center_real', 'center_imag', 'width', 'height',
                  'max_iterations', 'escape_radius'
        """
        return {'center_real': self.center_real, 'center_imag': self.center_imag,
                'width': self.width, 'height': self.height,
                'max_iterations': self.max_iterations, 'escape_radius': self.escape_radius}

    def set_active_fractal_plugin(self, plugin_name: str) -> bool:
        """指定された名前のフラクタルプラグインをアクティブにします。

        成功した場合、プラグインのデフォルトビューパラメータをエンジンに適用し、
        プラグイン固有のパラメータをデフォルト値で初期化します。

        Args:
            plugin_name (str): アクティブにするフラクタルプラグインの名前。
        Returns:
            bool: プラグインの設定に成功した場合はTrue、そうでない場合はFalse。
        """
        plugin = self.plugin_manager.get_fractal_plugin(plugin_name)
        if plugin:
            self.current_fractal_plugin = plugin
            defaults = plugin.get_default_view_parameters()
            self.center_real = defaults.get('center_real', self.center_real)
            self.center_imag = defaults.get('center_imag', self.center_imag)
            self.width = defaults.get('width', self.width)
            self.max_iterations = defaults.get('max_iterations', self.max_iterations)
            self.update_aspect_ratio()
            self.current_fractal_plugin_parameters.clear()
            for p_def in plugin.get_parameters_definition():
                self.current_fractal_plugin_parameters[p_def['name']] = p_def['default']
            self.last_fractal_data_cache = None
            return True
        return False

    def get_active_fractal_plugin(self) -> FractalPlugin | None:
        """現在アクティブなフラクタルプラグインのインスタンスを返します。"""
        return self.current_fractal_plugin

    def get_available_fractal_plugin_names(self) -> list[str]:
        """利用可能なすべてのフラクタルプラグインの名前のリストを返します。"""
        return [p.name for p in self.plugin_manager.get_available_fractal_plugins()]

    def get_current_fractal_plugin_parameter_definitions(self) -> list:
        """
        現在アクティブなフラクタルプラグインのパラメータ定義リストを返します。
        各定義は、名前、型、デフォルト値などを含む辞書です。
        アクティブなプラグインがない場合は空のリストを返します。
        """
        return self.current_fractal_plugin.get_parameters_definition() if self.current_fractal_plugin else []

    def set_fractal_plugin_parameter(self, name: str, value: any):
        """
        現在アクティブなフラクタルプラグインの指定されたパラメータ値を設定します。

        Args:
            name (str): 設定するパラメータの名前。
            value (any): 設定する値。
        """
        if self.current_fractal_plugin and name in self.current_fractal_plugin_parameters:
            self.current_fractal_plugin_parameters[name] = value
            self.last_fractal_data_cache = None

    def get_fractal_plugin_parameters(self) -> dict:
        """
        現在アクティブなフラクタルプラグインのパラメータとその現在の値の辞書を返します。
        """
        return self.current_fractal_plugin_parameters.copy()

    def set_active_coloring_plugin(self, plugin_name: str, target_type: str) -> bool:
        """
        指定されたターゲットタイプに対して、指定された名前のカラーリングプラグインをアクティブにします。
        成功した場合、そのターゲットタイプ用のプラグイン固有パラメータをデフォルト値で初期化します。

        Args:
            plugin_name (str): アクティブにするカラーリングプラグインの名前。
            target_type (str): 'divergent' または 'non_divergent'。
        Returns:
            bool: プラグインの設定に成功した場合はTrue、そうでない場合はFalse。
        """
        plugin = self.plugin_manager.get_coloring_plugin(plugin_name, target_type=target_type)
        if not plugin:
            logger.log(f"プラグイン '{plugin_name}' (target: {target_type}) が見つかりません。", level="WARNING")
            return False

        if target_type == 'divergent':
            self.current_coloring_plugin_divergent = plugin
            self.current_coloring_plugin_parameters_divergent.clear()
            for p_def in plugin.get_parameters_definition():
                self.current_coloring_plugin_parameters_divergent[p_def['name']] = p_def['default']
            logger.log(f"'{plugin_name}' に設定", level="INFO")
            return True
        elif target_type == 'non_divergent':
            self.current_coloring_plugin_non_divergent = plugin
            self.current_coloring_plugin_parameters_non_divergent.clear()
            for p_def in plugin.get_parameters_definition():
                self.current_coloring_plugin_parameters_non_divergent[p_def['name']] = p_def['default']
            logger.log(f"'{plugin_name}' に設定", level="INFO")
            return True
        else:
            logger.log(f"set_active_coloring_plugin のための無効なターゲットタイプ '{target_type}'", level="WARNING")
            return False

    def get_active_coloring_plugin(self, target_type: str) -> ColoringAlgorithmPlugin | None:
        """指定されたターゲットタイプで現在アクティブなカラーリングプラグインのインスタンスを返します。

        Args:
            target_type (str): 'divergent' または 'non_divergent'。
        Returns:
            ColoringAlgorithmPlugin | None: アクティブなカラーリングプラグイン。見つからない場合はNone。
        """
        if target_type == 'divergent':
            return self.current_coloring_plugin_divergent
        elif target_type == 'non_divergent':
            return self.current_coloring_plugin_non_divergent
        logger.log(f"無効なターゲットタイプ '{target_type}' が指定されました。", level="WARNING")
        return None

    def get_available_coloring_plugin_names(self, target_type: str) -> list[str]:
        """指定されたターゲットタイプで利用可能なカラーリングプラグインの名前のリストを返します。"""
        return [p.name for p in self.plugin_manager.get_available_coloring_plugins(target_type=target_type)]

    def get_current_coloring_plugin_parameter_definitions(self, target_type: str) -> list: # target_type を追加
        """
        指定されたターゲットタイプでアクティブなカラーリングプラグインのパラメータ定義リストを返します。
        """
        plugin = self.get_active_coloring_plugin(target_type)
        return plugin.get_parameters_definition() if plugin else []

    def set_coloring_plugin_parameter(self, name: str, value: any, target_type: str): # target_type を追加
        """
        指定されたターゲットタイプのアクティブなカラーリングプラグインのパラメータ値を設定します。
        """
        params_dict = None
        plugin = None
        if target_type == 'divergent':
            params_dict = self.current_coloring_plugin_parameters_divergent
            plugin = self.current_coloring_plugin_divergent
        elif target_type == 'non_divergent':
            params_dict = self.current_coloring_plugin_parameters_non_divergent
            plugin = self.current_coloring_plugin_non_divergent

        if plugin and params_dict is not None and name in params_dict:
            params_dict[name] = value
        else:
            logger.log(f"パラメータ '{name}' をターゲットタイプ '{target_type}' に設定できませんでした。", level="WARNING")

    def get_coloring_plugin_parameters(self, target_type: str) -> dict:
        if target_type == 'divergent':
            return self.current_coloring_plugin_parameters_divergent.copy()
        elif target_type == 'non_divergent':
            return self.current_coloring_plugin_parameters_non_divergent.copy()
        logger.log(f"無効なターゲットタイプ '{target_type}' が指定されました。", level="WARNING")
        return {}

    def set_active_color_map(self, pack_name: str, map_name: str, target_type: str) -> bool: # target_type を追加
        """
        指定されたターゲットタイプのアクティブなカラーマップを設定します。
        """
        map_data = self.color_manager.get_color_map_data(pack_name, map_name)
        if map_data:
            if target_type == 'divergent':
                self.current_color_pack_name_divergent = pack_name
                self.current_color_map_name_divergent = map_name
                return True
            elif target_type == 'non_divergent':
                self.current_color_pack_name_non_divergent = pack_name
                self.current_color_map_name_non_divergent = map_name
                return True
            else:
                logger.log(f"カラーマップ設定のための無効なターゲットタイプ '{target_type}'", level="WARNING")
                return False
        return False

    def get_available_color_pack_names(self) -> list[str]: return self.color_manager.get_available_color_pack_names()

    def get_available_color_map_names_in_pack(self, pack_name: str) -> list[str]:
        """
        指定されたカラーパック内の利用可能なカラーマップ名のリストを返します。

        Args:
            pack_name (str): カラーパックの名前。
        Returns:
            list[str]: カラーマップ名のリスト。
        """
        return self.color_manager.get_color_maps_in_pack(pack_name)

    def get_current_color_map_selection(self, target_type: str) -> tuple[str | None, str | None]: # target_type を追加
        """
        指定されたターゲットタイプで現在選択されているカラーパック名とカラーマップ名をタプルで返します。
        """
        if target_type == 'divergent':
            return self.current_color_pack_name_divergent, self.current_color_map_name_divergent
        elif target_type == 'non_divergent':
            return self.current_color_pack_name_non_divergent, self.current_color_map_name_non_divergent
        logger.log(f"カラーマップ選択取得のための無効なターゲットタイプ '{target_type}'", level="WARNING")
        return None, None

    def compute_current_fractal(self) -> dict | None:
        """
        現在アクティブなフラクタルプラグインとパラメータを使用してフラクタルデータを計算します。
        計算結果は内部キャッシュ (`last_fractal_data_cache`) にも保存されます。

        Returns:
            dict | None: 計算されたフラクタルデータ (通常 'iterations', 'last_values' を含む辞書)。
                         計算に失敗した場合はNone。
        """
        if not self.current_fractal_plugin: return None
        common_params = self.get_common_parameters()
        try:
            self.last_fractal_data_cache = self.current_fractal_plugin.compute_fractal(
                common_params, self.current_fractal_plugin_parameters,
                self.image_width_px, self.image_height_px
            )
            return self.last_fractal_data_cache
        except Exception as e:
            logger.log(f"計算中のエラー: {e}", level="ERROR")
            self.last_fractal_data_cache = None
            return None

    def apply_coloring(self, target_type: str, fractal_data_override: dict | None = None) -> np.ndarray | None:
        """
        指定されたフラクタルデータ（またはキャッシュされたデータ）に、
        指定されたターゲットタイプのアクティブなカラーリングプラグインとカラーマップを適用します。

        Args:
            target_type (str): 'divergent' または 'non_divergent'。
            fractal_data_override (dict | None, optional):
                カラーリングに使用するフラクタルデータ。Noneの場合、最後に計算された
                `last_fractal_data_cache` を使用します。
        Returns:
            np.ndarray | None: RGBA形式 (高さ x 幅 x 4) のカラーリングされた画像データ (uint8)。
                               カラーリングに失敗した場合はNone、またはエラーを示す赤い画像。
        """
        data_to_color = fractal_data_override if fractal_data_override is not None else self.last_fractal_data_cache

        active_plugin = self.get_active_coloring_plugin(target_type)
        plugin_params = self.get_coloring_plugin_parameters(target_type)
        pack_name, map_name = self.get_current_color_map_selection(target_type)

        if not active_plugin or not data_to_color:
            logger.log(f"apply_coloring ({target_type}) 中止: プラグイン ({active_plugin is not None}) またはデータ ({data_to_color is not None}) がありません。", level="WARNING")
            return None

        # 共通パラメータを構築
        common_params = self.get_common_parameters()
        # common_params の 'height' と 'width' を、これから処理する画像のピクセル寸法で上書きする
        iterations_array = data_to_color.get('iterations')
        if iterations_array is not None and iterations_array.ndim == 2:
            height_px, width_px = iterations_array.shape
            common_params['height'] = height_px
            common_params['width'] = width_px
        else:
            logger.log("apply_coloring: iterations_array が見つからないか、無効な形状です。デフォルトの画像サイズを使用します。", level="WARNING")
            common_params['height'] = self.image_height_px
            common_params['width'] = self.image_width_px

        try:
            return active_plugin.apply_coloring(
                fractal_data=data_to_color,
                common_fractal_params=common_params,
                algorithm_params=plugin_params,
                color_map_data=self.color_manager.get_color_map_data(pack_name, map_name) if pack_name and map_name else []
            )
        except Exception as e:
            logger.log(f"カラーリングプラグイン '{active_plugin.name}' の実行中にエラーが発生しました: {e}", level="ERROR")
            logger.log("トレースバック (直近の呼び出し):", level="ERROR")
            traceback.print_exc()
            h = common_params.get('height', self.image_height_px)
            w = common_params.get('width', self.image_width_px)
            err_img = np.full((h if h > 0 else 1, w if w > 0 else 1, 4), [255, 0, 0, 255], dtype=np.uint8)
            return err_img

    def _get_antialiasing_factor(self, antialiasing_level_str: str) -> int:
        """
        アンチエイリアスレベルの文字列から、スーパーサンプリングの係数を返します。

        Args:
            antialiasing_level_str (str): "なし", "2x2 SSAA", "3x3 SSAA", "4x4 SSAA" のいずれか。
        Returns:
            int: スーパーサンプリング係数 (1, 2, 3, または 4)。
        """
        if antialiasing_level_str == "2x2 SSAA": return 2
        if antialiasing_level_str == "3x3 SSAA": return 3
        if antialiasing_level_str == "4x4 SSAA": return 4
        return 1

    def _prepare_output_parameters(self, output_width: int, output_height: int, common_params_override: dict, fractal_plugin_name_override: str | None, fractal_plugin_params_override: dict | None, coloring_algo_name_override: str | None, coloring_algo_params_override: dict | None, color_pack_name_override: str | None, color_map_name_override: str | None, antialiasing_level: str) -> tuple[dict, FractalPlugin, dict, ColoringAlgorithmPlugin, dict, list, int, int, int]:
        """
        出力画像生成のための全パラメータを準備し、必要なインスタンスやデータを返す。
        """
        final_common_params = self.get_common_parameters()
        final_common_params.update(common_params_override)
        active_fractal_plugin = self.plugin_manager.get_fractal_plugin(fractal_plugin_name_override) if fractal_plugin_name_override else self.current_fractal_plugin
        if not active_fractal_plugin:
            logger.log("出力失敗、フラクタルプラグインが解決できませんでした。", level="ERROR")
            raise ValueError("フラクタルプラグインが解決できません")
        final_fractal_plugin_params = {p_def['name']: p_def['default'] for p_def in active_fractal_plugin.get_parameters_definition()}
        if self.current_fractal_plugin and active_fractal_plugin.name == self.current_fractal_plugin.name:
            final_fractal_plugin_params.update(self.current_fractal_plugin_parameters)
        if fractal_plugin_params_override:
            final_fractal_plugin_params.update(fractal_plugin_params_override)
        active_target_type_for_output = self.active_coloring_target_type
        final_coloring_plugin_name_to_use = coloring_algo_name_override
        if final_coloring_plugin_name_to_use is None:
            active_plugin_for_target = self.get_active_coloring_plugin(active_target_type_for_output)
            if active_plugin_for_target:
                final_coloring_plugin_name_to_use = active_plugin_for_target.name
        active_coloring_plugin = None
        if final_coloring_plugin_name_to_use:
            active_coloring_plugin = self.plugin_manager.get_coloring_plugin(final_coloring_plugin_name_to_use, target_type=active_target_type_for_output)
        if not active_coloring_plugin:
            logger.log(f"出力失敗、カラーリングプラグイン '{final_coloring_plugin_name_to_use}' (target: {active_target_type_for_output}) が解決できませんでした。", level="ERROR")
            raise ValueError("カラーリングプラグインが解決できません")
        final_coloring_algo_params = {p_def['name']: p_def['default'] for p_def in active_coloring_plugin.get_parameters_definition()}
        current_engine_cp_params = self.get_coloring_plugin_parameters(active_target_type_for_output)
        active_plugin_for_current_target = self.get_active_coloring_plugin(active_target_type_for_output)
        if active_plugin_for_current_target and active_coloring_plugin.name == active_plugin_for_current_target.name:
            final_coloring_algo_params.update(current_engine_cp_params)
        if coloring_algo_params_override:
            final_coloring_algo_params.update(coloring_algo_params_override)
        current_pack_name_for_target, current_map_name_for_target = self.get_current_color_map_selection(active_target_type_for_output)
        pack_name = color_pack_name_override if color_pack_name_override else current_pack_name_for_target
        map_name = color_map_name_override if color_map_name_override else current_map_name_for_target
        final_color_map_data = self.color_manager.get_color_map_data(pack_name, map_name) if pack_name and map_name else []
        if not final_color_map_data:
            final_color_map_data = [(i,i,i) for i in range(0,256,16)]
        aa_factor = self._get_antialiasing_factor(antialiasing_level)
        ss_width = output_width * aa_factor
        ss_height = output_height * aa_factor
        original_engine_complex_height = final_common_params['height']
        final_common_params['height'] = (final_common_params['width'] * ss_height) / ss_width if ss_width > 0 else final_common_params['width']
        return (final_common_params, active_fractal_plugin, final_fractal_plugin_params, active_coloring_plugin, final_coloring_algo_params, final_color_map_data, aa_factor, ss_width, ss_height)

    def _compute_fractal_for_output(self, plugin: FractalPlugin, params: dict, common_params: dict, width: int, height: int) -> dict | None:
        try:
            return plugin.compute_fractal(common_params, params, width, height)
        except Exception as e:
            logger.log(f"スーパーサンプリングされたフラクタル計算に失敗: {e}", level="ERROR")
            return None

    def _apply_coloring_for_output(self, plugin: ColoringAlgorithmPlugin, params: dict, common_params: dict, fractal_data: dict, color_map_data: list) -> np.ndarray | None:
        try:
            common_params_for_coloring = common_params.copy()
            common_params_for_coloring['image_width_px'] = common_params['width']
            common_params_for_coloring['image_height_px'] = common_params['height']
            return plugin.apply_coloring(fractal_data, common_params_for_coloring, params, color_map_data)
        except Exception as e:
            logger.log(f"スーパーサンプリングされたカラーリングに失敗: {e}", level="ERROR")
            return None

    def _downsample_image(self, image: np.ndarray, output_width: int, output_height: int, aa_factor: int) -> np.ndarray:
        if aa_factor > 1:
            try:
                if image.shape[2] != 4:
                    logger.log(f"カラーリングから4チャンネルを期待しましたが、{image.shape[2]} を取得しました", level="ERROR")
                    return image
                reshaped = image.reshape(output_height, aa_factor, output_width, aa_factor, 4)
                return reshaped.mean(axis=(1, 3)).astype(np.uint8)
            except ValueError as e:
                logger.log(f"ダウンサンプリングリシェイプ中のエラー: {e}。入力: {image.shape}, ターゲット: {output_height}x{output_width}, AA: {aa_factor}", level="ERROR")
                return image
        else:
            return image

    def generate_image_for_output(self, output_width: int, output_height: int,
                                  common_params_override: dict,
                                  fractal_plugin_name_override: str | None = None,
                                  fractal_plugin_params_override: dict | None = None,
                                  coloring_algo_name_override: str | None = None,
                                  coloring_algo_params_override: dict | None = None,
                                  color_pack_name_override: str | None = None,
                                  color_map_name_override: str | None = None,
                                  antialiasing_level: str = "なし"
                                  ) -> np.ndarray | None:
        logger.log(f"高解像度出力開始 - ターゲット: {output_width}x{output_height}, AA: {antialiasing_level}", level="INFO")
        try:
            (final_common_params, active_fractal_plugin, final_fractal_plugin_params, active_coloring_plugin, final_coloring_algo_params, final_color_map_data, aa_factor, ss_width, ss_height) = self._prepare_output_parameters(
                output_width, output_height, common_params_override, fractal_plugin_name_override, fractal_plugin_params_override, coloring_algo_name_override, coloring_algo_params_override, color_pack_name_override, color_map_name_override, antialiasing_level)
            logger.log(f"  - スーパーサンプリング解像度: {ss_width}x{ss_height} (AA係数: {aa_factor})", level="DEBUG")
            logger.log(f"  - フラクタルプラグイン: {active_fractal_plugin.name}, パラメータ: {final_fractal_plugin_params}", level="DEBUG")
            logger.log(f"  - カラーリングプラグイン: {active_coloring_plugin.name}, パラメータ: {final_coloring_algo_params}", level="DEBUG")
            logger.log(f"  - カラーマップ: {color_pack_name_override}/{color_map_name_override}", level="DEBUG")
            logger.log(f"  - 計算用共通パラメータ: 中心=({final_common_params['center_real']:.4f},{final_common_params['center_imag']:.4f}), 幅={final_common_params['width']:.3e}, 高さ(複素)={final_common_params['height']:.3e]}, 反復={final_common_params['max_iterations']}", level="DEBUG")
            fractal_data_ss = self._compute_fractal_for_output(active_fractal_plugin, final_fractal_plugin_params, final_common_params, ss_width, ss_height)
            if fractal_data_ss is None:
                return None
            colored_image_ss_rgba = self._apply_coloring_for_output(active_coloring_plugin, final_coloring_algo_params, final_common_params, fractal_data_ss, final_color_map_data)
            if colored_image_ss_rgba is None:
                return None
            downsampled_image_rgba = self._downsample_image(colored_image_ss_rgba, output_width, output_height, aa_factor)
            logger.log(f"高解像度画像が正常に生成されました ({output_width}x{output_height})。", level="INFO")
            return downsampled_image_rgba
        except Exception as e:
            logger.log(f"generate_image_for_output中にエラー: {e}", level="ERROR")
            return None

    # --- 設定の保存/読み込み ---
    def save_settings(self) -> dict:
        """現在のエンジンの設定を辞書としてシリアライズします。"""
        settings = {
            "common_parameters": self.get_common_parameters(),
            "active_fractal_plugin_name": self.current_fractal_plugin.name if self.current_fractal_plugin else None,
            "fractal_plugin_parameters": self.current_fractal_plugin_parameters,

            "active_coloring_target_type": self.active_coloring_target_type,

            "coloring_plugin_divergent_name": self.current_coloring_plugin_divergent.name if self.current_coloring_plugin_divergent else None,
            "coloring_plugin_divergent_params": self.current_coloring_plugin_parameters_divergent,
            "color_pack_divergent_name": self.current_color_pack_name_divergent,
            "color_map_divergent_name": self.current_color_map_name_divergent,

            "coloring_plugin_non_divergent_name": self.current_coloring_plugin_non_divergent.name if self.current_coloring_plugin_non_divergent else None,
            "coloring_plugin_non_divergent_params": self.current_coloring_plugin_parameters_non_divergent,
            "color_pack_non_divergent_name": self.current_color_pack_name_non_divergent,
            "color_map_non_divergent_name": self.current_color_map_name_non_divergent,

            # 画像サイズは必要に応じてcommon_parametersの一部とするか、別途保存できます
            "image_width_px": self.image_width_px,
            "image_height_px": self.image_height_px,
        }
        logger.log("エンジン設定をシリアライズしました。", level="DEBUG")
        return settings

    def load_settings(self, settings: dict):
        """辞書からエンジンの設定を復元します。"""
        if not isinstance(settings, dict):
            logger.log("load_settings: settings が辞書ではありません。ロードをスキップします。", level="WARNING")
            return
        try:
            cp = settings.get("common_parameters")
            if cp and isinstance(cp, dict):
                self.set_common_parameters(
                    center_real=cp.get('center_real', self.center_real),
                    center_imag=cp.get('center_imag', self.center_imag),
                    width=cp.get('width', self.width),
                    max_iterations=cp.get('max_iterations', self.max_iterations),
                    escape_radius=cp.get('escape_radius', self.escape_radius)
                )

            fp_name = settings.get("active_fractal_plugin_name")
            if fp_name:
                if self.set_active_fractal_plugin(fp_name): # これによりデフォルトのプラグインパラメータも設定されます
                    fp_params = settings.get("fractal_plugin_parameters")
                    if fp_params and isinstance(fp_params, dict): # 保存されたパラメータでデフォルトを上書き
                        for name, value in fp_params.items():
                            self.set_fractal_plugin_parameter(name, value)

            # 発散部のカラーリング設定を復元
            cpd_name = settings.get("coloring_plugin_divergent_name")
            if cpd_name:
                if self.set_active_coloring_plugin(cpd_name, target_type='divergent'):
                    cpd_params = settings.get("coloring_plugin_divergent_params")
                    if cpd_params and isinstance(cpd_params, dict):
                        for name, value in cpd_params.items():
                             self.set_coloring_plugin_parameter(name, value, target_type='divergent')

            cpd_pack = settings.get("color_pack_divergent_name")
            cpd_map = settings.get("color_map_divergent_name")
            if cpd_pack and cpd_map:
                # 設定する前にパックとマップが存在することを確認
                if cpd_pack in self.get_available_color_pack_names() and \
                   cpd_map in self.get_available_color_map_names_in_pack(cpd_pack):
                    self.set_active_color_map(cpd_pack, cpd_map, target_type='divergent')
                else:
                    logger.log(f"発散部: 保存されたカラーマップ {cpd_pack}/{cpd_map} が見つかりません。", level="WARNING")

            # 非発散部のカラーリング設定を復元
            cpnd_name = settings.get("coloring_plugin_non_divergent_name")
            if cpnd_name:
                if self.set_active_coloring_plugin(cpnd_name, target_type='non_divergent'):
                    cpnd_params = settings.get("coloring_plugin_non_divergent_params")
                    if cpnd_params and isinstance(cpnd_params, dict):
                        for name, value in cpnd_params.items():
                             self.set_coloring_plugin_parameter(name, value, target_type='non_divergent')

            cpnd_pack = settings.get("color_pack_non_divergent_name")
            cpnd_map = settings.get("color_map_non_divergent_name")
            if cpnd_pack and cpnd_map:
                if cpnd_pack in self.get_available_color_pack_names() and \
                   cpnd_map in self.get_available_color_map_names_in_pack(cpnd_pack):
                    self.set_active_color_map(cpnd_pack, cpnd_map, target_type='non_divergent')
                else:
                    logger.log(f"非発散部: 保存されたカラーマップ {cpnd_pack}/{cpnd_map} が見つかりません。", level="WARNING")

            # 特定のタイプがロードされた後にアクティブなターゲットタイプを復元
            self.active_coloring_target_type = settings.get("active_coloring_target_type", self.active_coloring_target_type)

            # 画像サイズを復元（オプション、UIで処理可能）
            # 設定前にこれらが正であることを確認
            loaded_width = settings.get("image_width_px", self.image_width_px)
            if loaded_width > 0: self.image_width_px = loaded_width
            loaded_height = settings.get("image_height_px", self.image_height_px)
            if loaded_height > 0: self.image_height_px = loaded_height
            self.update_aspect_ratio() # 'height'（複素平面）が更新されることを確認

            self.last_fractal_data_cache = None # キャッシュを無効化
            logger.log("エンジン設定読込完了", level="INFO")
        except Exception as e:
            logger.log(f"エンジン設定読込中にエラー発生: {e}", level="ERROR")
            traceback.print_exc()

if __name__ == '__main__':
    # テストには、CWDからの相対的なデフォルトの場所にプラグインとカラーパックが必要です
    # 例: CWD = プロジェクトルートの場合、"src/app/plugins/fractals" のようなパスが有効です。
    logger.log("FractalEngine (generate_image_for_output を含む) スタンドアロンテスト", level="INFO")
    # スタンドアロンテストの場合、CWDがプロジェクトルートであると仮定します
    test_project_root = Path.cwd()
    logger.log(f"  テスト用のプロジェクトルート: {test_project_root}", level="INFO")
    engine = FractalEngine(project_root_path=test_project_root, image_width_px=80, image_height_px=60) # 画面表示用の小さなデフォルト値

    if not engine.get_active_fractal_plugin() or not engine.get_active_coloring_plugin('divergent'): # 発散部を確認
        logger.log("デフォルトプラグインが読み込まれていません。パスまたはプラグインの可用性を確認してください。テストを完全に続行できません。", level="WARNING")
    else:
        logger.log(f"アクティブなフラクタルプラグイン: {engine.get_active_fractal_plugin().name}", level="INFO")
        active_coloring_div = engine.get_active_coloring_plugin('divergent')
        if active_coloring_div:
            logger.log(f"アクティブな発散部カラーリングプラグイン: {active_coloring_div.name}", level="INFO")
        cp_div, cm_div = engine.get_current_color_map_selection('divergent')
        logger.log(f"アクティブな発散部カラーマップ: {cp_div} - {cm_div}", level="INFO")

        output_params = {
            'max_iterations': 200, # 出力用の反復回数を上書き
            # 他の共通パラメータは、上書きされない限りエンジンの現在の状態を使用します
        }

        # 高解像度出力のテスト
        logger.log("\n160x120 画像を 2x2 SSAA で生成中...", level="INFO")
        output_image = engine.generate_image_for_output(
            output_width=160, output_height=120,
            common_params_override=output_params,
            # 現在のプラグインとそのパラメータ、および現在のカラーマップを使用
            antialiasing_level="2x2 SSAA"
        )
        if output_image is not None:
            logger.log(f"  出力画像が生成されました。形状: {output_image.shape}, Dtype: {output_image.dtype}", level="INFO")
            assert output_image.shape == (120, 160, 4)
            # import matplotlib.pyplot as plt # 必要に応じて視覚的な確認用
            # plt.imshow(output_image); plt.show()
        else:
            logger.log("  高解像度画像の生成に失敗しました。", level="ERROR")

    # TODO: save_settings と load_settings のテストを実装したらここに追加

    logger.log("\nFractalEngine テストが完了しました。", level="INFO")
