import numpy as np
import traceback
from pathlib import Path

from plugins.plugin_manager import PluginManager
from plugins.base_fractal_plugin import FractalPlugin
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
from coloring.color_manager import ColorManager
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class FractalEngine:
    """
    フラクタル画像の計算、カラーリング、および関連パラメータ管理を行うコアエンジン。

    プラグインシステムを介して様々なフラクタルアルゴリズムとカラーリング手法をサポートし、
    高解像度画像の出力機能も提供します。
    """
    def __init__(self, project_root_path: Path, image_width_px=800, image_height_px=600,
                 fractal_plugin_folder="plugins/fractals",  # project_root_pathからの相対パス
                 coloring_plugin_folder="plugins/coloring", # 同上
                 color_pack_folder="plugins/colorpacks"):   # 同上
        """
        FractalEngineを初期化します。

        Args:
            project_root_path (Path): プロジェクトのルートディレクトリへのパス。プラグインやカラーパックの読み込みに使用されます。
            image_width_px (int): プレビュー表示用のデフォルト画像幅 (ピクセル単位)。
            image_height_px (int): プレビュー表示用のデフォルト画像高さ (ピクセル単位)。
            fractal_plugin_folder (str): `project_root_path` からのフラクタルプラグインフォルダへの相対パス。
            coloring_plugin_folder (str): `project_root_path` からのカラーリングプラグインフォルダへの相対パス。
            color_pack_folder (str): `project_root_path` からのカラーパックフォルダへの相対パス。
        """
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
            divergent_coloring_plugin_folder_path="plugins/coloring/divergent", # Changed
            non_divergent_coloring_plugin_folder_path="plugins/coloring/non_divergent" # Changed
        )
        # ColorManagerもプロジェクトルートからの相対パスで初期化するのが望ましいです
        self.color_manager = ColorManager(color_packs_dir=str(project_root_path / color_pack_folder))

        self.current_fractal_plugin: FractalPlugin | None = None
        self.current_fractal_plugin_parameters: dict = {}

        self.active_coloring_target_type: str = 'divergent' # Default active target

        self.current_coloring_plugin_divergent: ColoringAlgorithmPlugin | None = None
        self.current_coloring_plugin_parameters_divergent: dict = {}
        self.current_color_pack_name_divergent: str | None = None
        self.current_color_map_name_divergent: str | None = None

        self.current_coloring_plugin_non_divergent: ColoringAlgorithmPlugin | None = None
        self.current_coloring_plugin_parameters_non_divergent: dict = {}
        self.current_color_pack_name_non_divergent: str | None = None
        self.current_color_map_name_non_divergent: str | None = None

        self.last_fractal_data_cache: dict | None = None

        self._initialize_default_plugins_and_map()

    def _initialize_default_plugins_and_map(self):
        """
        利用可能なプラグインとカラーマップから、デフォルトのものを選択して初期設定します。
        MandelbrotやGrayscaleなど、一般的なものが優先的に選択されます。
        DivergentとNon-Divergentの両方のカラーリングコンテキストを初期化します。
        """
        # Fractal Plugin
        available_fractal_plugins = self.get_available_fractal_plugin_names()
        if available_fractal_plugins:
            default_fractal = "Mandelbrot"
            if default_fractal in available_fractal_plugins: self.set_active_fractal_plugin(default_fractal)
            else: self.set_active_fractal_plugin(available_fractal_plugins[0])
        else: logger.log("フラクタルプラグインが見つかりません。", level="WARNING")

        # Divergent Coloring Plugin
        available_div_plugins = self.get_available_coloring_plugin_names(target_type='divergent')
        if available_div_plugins:
            default_div_coloring = "グレースケール (標準)" # Assuming this is a divergent plugin
            if default_div_coloring in available_div_plugins:
                self.set_active_coloring_plugin(default_div_coloring, target_type='divergent')
            elif "スムーズカラー" in available_div_plugins: # Assuming this is divergent
                 self.set_active_coloring_plugin("スムーズカラー", target_type='divergent')
            else:
                self.set_active_coloring_plugin(available_div_plugins[0], target_type='divergent')
        else:
            logger.log("発散部カラーリングプラグインが見つかりません。", level="WARNING")

        # Non-Divergent Coloring Plugin
        available_nondiv_plugins = self.get_available_coloring_plugin_names(target_type='non_divergent')
        if available_nondiv_plugins:
            default_nondiv_coloring = "反復収束速度" # Assuming this is non-divergent
            if default_nondiv_coloring in available_nondiv_plugins:
                self.set_active_coloring_plugin(default_nondiv_coloring, target_type='non_divergent')
            elif "複素ポテンシャル" in available_nondiv_plugins: # Assuming this is non-divergent
                 self.set_active_coloring_plugin("複素ポテンシャル", target_type='non_divergent')
            else:
                self.set_active_coloring_plugin(available_nondiv_plugins[0], target_type='non_divergent')
        else:
            logger.log("非発散部カラーリングプラグインが見つかりません。", level="WARNING")

        # Default Color Map (shared for now, or could be specific)
        # For simplicity, let's use one set of color map controls that applies to the *active* target type.
        # Or, we initialize both to the same default map. Let's initialize both.
        available_color_packs = self.get_available_color_pack_names()
        if available_color_packs:
            pack_to_try = "デフォルト"
            if pack_to_try not in available_color_packs: pack_to_try = available_color_packs[0]
            maps_in_pack = self.get_available_color_map_names_in_pack(pack_to_try)
            if maps_in_pack:
                self.set_active_color_map(pack_to_try, maps_in_pack[0], target_type='divergent')
                self.set_active_color_map(pack_to_try, maps_in_pack[0], target_type='non_divergent')
        else: logger.log("カラーパックが見つかりません。", level="WARNING")

        # Set the overall active target type (already defaults to 'divergent')
        # self.active_coloring_target_type = 'divergent'


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
        plugin = self.plugin_manager.get_fractal_plugin(plugin_name)
        if plugin:
            """
            指定された名前のフラクタルプラグインをアクティブにします。
            成功した場合、プラグインのデフォルトビューパラメータをエンジンに適用し、
            プラグイン固有のパラメータをデフォルト値で初期化します。

            Args:
                plugin_name (str): アクティブにするフラクタルプラグインの名前。
            Returns:
                bool: プラグインの設定に成功した場合はTrue、そうでない場合はFalse。
            """
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
            logger.log(f"発散部用アクティブカラーリングプラグインを '{plugin_name}' に設定しました。", level="INFO")
            return True
        elif target_type == 'non_divergent':
            self.current_coloring_plugin_non_divergent = plugin
            self.current_coloring_plugin_parameters_non_divergent.clear()
            for p_def in plugin.get_parameters_definition():
                self.current_coloring_plugin_parameters_non_divergent[p_def['name']] = p_def['default']
            logger.log(f"非発散部用アクティブカラーリングプラグインを '{plugin_name}' に設定しました。", level="INFO")
            return True
        else:
            logger.log(f"set_active_coloring_plugin のための無効なターゲットタイプ '{target_type}'", level="WARNING")
            return False

    def get_active_coloring_plugin(self, target_type: str) -> ColoringAlgorithmPlugin | None:
        if target_type == 'divergent':
            return self.current_coloring_plugin_divergent
        elif target_type == 'non_divergent':
            return self.current_coloring_plugin_non_divergent
        logger.log(f"無効なターゲットタイプ '{target_type}' が指定されました。", level="WARNING")
        return None

    def get_available_coloring_plugin_names(self, target_type: str) -> list[str]:
        """指定されたターゲットタイプで利用可能なカラーリングプラグインの名前のリストを返します。"""
        return [p.name for p in self.plugin_manager.get_available_coloring_plugins(target_type=target_type)]

    def get_current_coloring_plugin_parameter_definitions(self, target_type: str) -> list: # Added target_type
        """
        指定されたターゲットタイプでアクティブなカラーリングプラグインのパラメータ定義リストを返します。
        """
        plugin = self.get_active_coloring_plugin(target_type)
        return plugin.get_parameters_definition() if plugin else []

    def set_coloring_plugin_parameter(self, name: str, value: any, target_type: str): # Added target_type
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

    def get_coloring_plugin_parameters(self, target_type: str) -> dict: # Added target_type
        if target_type == 'divergent':
            return self.current_coloring_plugin_parameters_divergent.copy()
        elif target_type == 'non_divergent':
            return self.current_coloring_plugin_parameters_non_divergent.copy()
        logger.log(f"無効なターゲットタイプ '{target_type}' が指定されました。", level="WARNING")
        return {}

    def set_active_color_map(self, pack_name: str, map_name: str, target_type: str) -> bool: # Added target_type
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

    def get_current_color_map_selection(self, target_type: str) -> tuple[str | None, str | None]: # Added target_type
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

        if not active_plugin or data_to_color is None:
            logger.log(f"apply_coloring ({target_type}) 中止: プラグイン ({active_plugin is not None}) またはデータ ({data_to_color is not None}) がありません。", level="WARNING")
            return None

        color_map_list = []
        if pack_name and map_name:
            color_map_list = self.color_manager.get_color_map_data(pack_name, map_name)
        if not color_map_list : color_map_list = [(i,i,i) for i in range(0,256,16)] # 単純なフォールバック

        common_fp = self.get_common_parameters()
        # Ensure image dimensions in common_fp match the data being colored
        iterations_array = data_to_color.get('iterations')
        if iterations_array is not None and iterations_array.ndim == 2:
            common_fp['image_height_px'] = iterations_array.shape[0]
            common_fp['image_width_px'] = iterations_array.shape[1]
        else: # Fallback or if iterations is missing/malformed
            common_fp['image_height_px'] = self.image_height_px
            common_fp['image_width_px'] = self.image_width_px
            logger.log("apply_coloring: iterations_array が見つからないか、無効な形状です。デフォルトの画像サイズを使用します。", level="WARNING")


        try:
            return active_plugin.apply_coloring(
                data_to_color, common_fp, plugin_params, color_map_list
            )
        except Exception as e:
            logger.log(f"カラーリング中のエラー: {e}", level="ERROR")
            logger.log("トレースバック (直近の呼び出し):", level="ERROR") # トレースバックが出力されている事実をログに記録
            traceback.print_exc() # トレースバック情報を標準エラー出力に出力
            h = common_fp['image_height_px']; w = common_fp['image_width_px']
            err_img = np.full((h if h>0 else 1, w if w>0 else 1, 4), [255,0,0,255], dtype=np.uint8)
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

    def generate_image_for_output(self, output_width: int, output_height: int,
                                  common_params_override: dict,
                                  fractal_plugin_name_override: str | None = None, # 名前に変更
                                  fractal_plugin_params_override: dict | None = None,
                                  coloring_algo_name_override: str | None = None,
                                  coloring_algo_params_override: dict | None = None,
                                  color_pack_name_override: str | None = None,
                                  color_map_name_override: str | None = None,
                                  antialiasing_level: str = "なし"
                                  ) -> np.ndarray | None:
        """
        指定されたパラメータで高解像度のフラクタル画像を生成します。

        このメソッドは、現在のエンジンの状態を一時的に上書きする形で、
        特定の出力解像度、フラクタルパラメータ、カラーリング設定で画像を生成します。
        スーパーサンプリングアンチエイリアス (SSAA) もサポートします。

        Args:
            output_width (int): 出力画像の幅 (ピクセル単位)。
            output_height (int): 出力画像の高さ (ピクセル単位)。
            common_params_override (dict): `get_common_parameters` で返される形式の共通パラメータ。
                                         エンジンの現在の設定を上書きします。
            fractal_plugin_name_override (str | None): 使用するフラクタルプラグインの名前。Noneの場合、現在のプラグイン。
            fractal_plugin_params_override (dict | None): フラクタルプラグイン固有のパラメータ。Noneの場合、現在のパラメータまたはデフォルト。
            coloring_algo_name_override (str | None): 使用するカラーリングアルゴリズムの名前。Noneの場合、現在のアルゴリズム。
            coloring_algo_params_override (dict | None): カラーリングアルゴリズム固有のパラメータ。Noneの場合、現在のパラメータまたはデフォルト。
            color_pack_name_override (str | None): 使用するカラーパックの名前。Noneの場合、現在のカラーパック。
            color_map_name_override (str | None): 使用するカラーマップの名前。Noneの場合、現在のカラーマップ。
            antialiasing_level (str): アンチエイリアスレベル。"なし", "2x2 SSAA", "3x3 SSAA", "4x4 SSAA"。

        Returns:
            np.ndarray | None: 生成されたRGBA画像 (高さ x 幅 x 4, uint8)。
                               エラーが発生した場合はNone。
        """
        logger.log(f"高解像度出力開始 - ターゲット: {output_width}x{output_height}, AA: {antialiasing_level}", level="INFO")

        # 1. パラメータ準備
        final_common_params = self.get_common_parameters()
        final_common_params.update(common_params_override) # ダイアログ設定で上書き

        # フラクタルプラグインとそのパラメータを決定
        active_fractal_plugin = self.plugin_manager.get_fractal_plugin(fractal_plugin_name_override) if fractal_plugin_name_override else self.current_fractal_plugin
        if not active_fractal_plugin: logger.log("出力失敗、フラクタルプラグインが解決できませんでした。", level="ERROR"); return None

        final_fractal_plugin_params = {} # 空またはプラグインのデフォルトで開始
        base_plugin_param_defs = active_fractal_plugin.get_parameters_definition()
        for p_def in base_plugin_param_defs: final_fractal_plugin_params[p_def['name']] = p_def['default']
        if self.current_fractal_plugin and active_fractal_plugin.name == self.current_fractal_plugin.name: # 現在と同じ場合
            final_fractal_plugin_params.update(self.current_fractal_plugin_parameters) # 現在の設定をベースとして使用
        if fractal_plugin_params_override: final_fractal_plugin_params.update(fractal_plugin_params_override)

        # カラーリングプラグインとそのパラメータを決定 (アクティブターゲットタイプを考慮)
        # generate_image_for_output は単一のカラーリング設定セットを取る。
        # どのターゲットタイプを使用するかを決定する必要がある。コントローラの current active target type を使う。
        # このメソッドはコントローラからは呼ばれず、エクスポータから直接呼ばれるため、
        # self.active_coloring_target_type を信頼する。
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
            return None

        final_coloring_algo_params = {}
        base_coloring_param_defs = active_coloring_plugin.get_parameters_definition()
        for p_def in base_coloring_param_defs:
            final_coloring_algo_params[p_def['name']] = p_def['default']

        current_engine_cp_params = self.get_coloring_plugin_parameters(active_target_type_for_output)
        # Check if the plugin for override is the same as the one active for the target type
        active_plugin_for_current_target = self.get_active_coloring_plugin(active_target_type_for_output)
        if active_plugin_for_current_target and active_coloring_plugin.name == active_plugin_for_current_target.name :
             final_coloring_algo_params.update(current_engine_cp_params) # Start with current params if same plugin
        if coloring_algo_params_override: # Then apply specific overrides
            final_coloring_algo_params.update(coloring_algo_params_override)


        # カラーマップを決定 (正しいターゲットタイプ用)
        current_pack_name_for_target, current_map_name_for_target = self.get_current_color_map_selection(active_target_type_for_output)
        pack_name = color_pack_name_override if color_pack_name_override else current_pack_name_for_target
        map_name = color_map_name_override if color_map_name_override else current_map_name_for_target
        final_color_map_data = self.color_manager.get_color_map_data(pack_name, map_name) if pack_name and map_name else []
        if not final_color_map_data: final_color_map_data = [(i,i,i) for i in range(0,256,16)]

        # 2. スーパーサンプリング解像度
        aa_factor = self._get_antialiasing_factor(antialiasing_level)
        ss_width = output_width * aa_factor
        ss_height = output_height * aa_factor

        # 3. スーパーサンプリングされたアスペクト比に合わせて common_params.height を調整
        # これは重要です: common_params の 'height' は複素平面の高さです。
        # 計算されるピクセルグリッドのアスペクト比と一致する必要があります。
        original_engine_complex_height = final_common_params['height'] # エンジン状態が直接変更された場合に後で復元するため
        final_common_params['height'] = (final_common_params['width'] * ss_height) / ss_width if ss_width > 0 else final_common_params['width']

        logger.log(f"  - スーパーサンプリング解像度: {ss_width}x{ss_height} (AA係数: {aa_factor})", level="DEBUG")
        logger.log(f"  - フラクタルプラグイン: {active_fractal_plugin.name}, パラメータ: {final_fractal_plugin_params}", level="DEBUG")
        logger.log(f"  - カラーリングプラグイン: {active_coloring_plugin.name}, パラメータ: {final_coloring_algo_params}", level="DEBUG")
        logger.log(f"  - カラーマップ: {pack_name}/{map_name}", level="DEBUG")
        logger.log(f"  - 計算用共通パラメータ: 中心=({final_common_params['center_real']:.4f},{final_common_params['center_imag']:.4f}), 幅={final_common_params['width']:.3e}, 高さ(複素)={final_common_params['height']:.3e]}, 反復={final_common_params['max_iterations']}", level="DEBUG")

        # 4. フラクタル計算 (スーパーサンプリング解像度で)
        fractal_data_ss = active_fractal_plugin.compute_fractal(
            final_common_params, final_fractal_plugin_params, ss_width, ss_height
        )
        if fractal_data_ss is None: logger.log("スーパーサンプリングされたフラクタル計算に失敗しました。", level="ERROR"); return None

        # カラーリングプラグインが必要とする可能性があるため、画像寸法を common_params に追加
        final_common_params_for_coloring = final_common_params.copy()
        final_common_params_for_coloring['image_width_px'] = ss_width
        final_common_params_for_coloring['image_height_px'] = ss_height
        # 5. カラーリング (スーパーサンプリング解像度で)
        colored_image_ss_rgba = active_coloring_plugin.apply_coloring(
            fractal_data_ss, final_common_params_for_coloring, final_coloring_algo_params, final_color_map_data
        )
        if colored_image_ss_rgba is None: logger.log("スーパーサンプリングされたカラーリングに失敗しました。", level="ERROR"); return None

        # 6. ダウンサンプリング (AAが有効な場合)
        if aa_factor > 1:
            logger.log(f"  - {ss_width}x{ss_height} から {output_width}x{output_height} へダウンサンプリング中...", level="DEBUG")
            try:
                # リシェイプのためにRGBA (4チャンネル) を確認
                if colored_image_ss_rgba.shape[2] != 4: # カラーリングプラグインからは常に4チャンネルのはず
                    logger.log(f"カラーリングから4チャンネルを期待しましたが、{colored_image_ss_rgba.shape[2]} を取得しました", level="ERROR"); return None

                reshaped = colored_image_ss_rgba.reshape(output_height, aa_factor, output_width, aa_factor, 4)
                downsampled_image_rgba = reshaped.mean(axis=(1, 3)).astype(np.uint8)
            except ValueError as e:
                logger.log(f"ダウンサンプリングリシェイプ中のエラー: {e}。入力: {colored_image_ss_rgba.shape}, ターゲット: {output_height}x{output_width}, AA: {aa_factor}", level="ERROR"); return None
        else:
            downsampled_image_rgba = colored_image_ss_rgba

        logger.log(f"高解像度画像が正常に生成されました ({output_width}x{output_height})。", level="INFO")
        return downsampled_image_rgba


if __name__ == '__main__':
    # テストには、CWDからの相対的なデフォルトの場所にプラグインとカラーパックが必要です
    # 例: CWD = プロジェクトルートの場合、"src/app/plugins/fractals" のようなパスが有効です。
    logger.log("FractalEngine (generate_image_for_output を含む) スタンドアロンテスト", level="INFO")
    # スタンドアロンテストの場合、CWDがプロジェクトルートであると仮定します
    test_project_root = Path.cwd()
    logger.log(f"  テスト用のプロジェクトルート: {test_project_root}", level="INFO")
    engine = FractalEngine(project_root_path=test_project_root, image_width_px=80, image_height_px=60) # 画面表示用の小さなデフォルト値

    if not engine.get_active_fractal_plugin() or not engine.get_active_coloring_plugin():
        logger.log("デフォルトプラグインが読み込まれていません。パスまたはプラグインの可用性を確認してください。テストを完全に続行できません。", level="WARNING")
    else:
        logger.log(f"アクティブなフラクタルプラグイン: {engine.get_active_fractal_plugin().name}", level="INFO")
        logger.log(f"アクティブなカラーリングプラグイン: {engine.get_active_coloring_plugin().name}", level="INFO")
        cp, cm = engine.get_current_color_map_selection()
        logger.log(f"アクティブなカラーマップ: {cp} - {cm}", level="INFO")

        output_params = {
            'max_iterations': 200, # 出力用の反復回数を上書き
            # 他の共通パラメータは、上書きされない限りエンジンの現在の状態を使用します
        }

        # 高解像度出力のテスト (例: Mandelbrot と Grayscale)
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

    # TODO: Add save_settings and load_settings tests here once implemented

    # --- Save/Load Settings ---
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

            # image size is part of common_parameters if needed, or can be saved separately
            "image_width_px": self.image_width_px,
            "image_height_px": self.image_height_px,
        }
        logger.log("設定を保存しました。", level="DEBUG")
        return settings

    def load_settings(self, settings: dict):
        """辞書からエンジンの設定を復元します。"""
        try:
            cp = settings.get("common_parameters")
            if cp:
                self.set_common_parameters(
                    center_real=cp.get('center_real', -0.5),
                    center_imag=cp.get('center_imag', 0.0),
                    width=cp.get('width', 3.0),
                    max_iterations=cp.get('max_iterations', 100),
                    escape_radius=cp.get('escape_radius', 2.0)
                )

            fp_name = settings.get("active_fractal_plugin_name")
            if fp_name:
                if self.set_active_fractal_plugin(fp_name): # This also sets default plugin params
                    fp_params = settings.get("fractal_plugin_parameters")
                    if fp_params: # Override defaults with saved params
                        for name, value in fp_params.items():
                            self.set_fractal_plugin_parameter(name, value)

            # Restore coloring settings for divergent
            cpd_name = settings.get("coloring_plugin_divergent_name")
            if cpd_name:
                if self.set_active_coloring_plugin(cpd_name, target_type='divergent'):
                    cpd_params = settings.get("coloring_plugin_divergent_params")
                    if cpd_params:
                        for name, value in cpd_params.items():
                             self.set_coloring_plugin_parameter(name, value, target_type='divergent')

            cpd_pack = settings.get("color_pack_divergent_name")
            cpd_map = settings.get("color_map_divergent_name")
            if cpd_pack and cpd_map:
                self.set_active_color_map(cpd_pack, cpd_map, target_type='divergent')

            # Restore coloring settings for non-divergent
            cpnd_name = settings.get("coloring_plugin_non_divergent_name")
            if cpnd_name:
                if self.set_active_coloring_plugin(cpnd_name, target_type='non_divergent'):
                    cpnd_params = settings.get("coloring_plugin_non_divergent_params")
                    if cpnd_params:
                        for name, value in cpnd_params.items():
                             self.set_coloring_plugin_parameter(name, value, target_type='non_divergent')

            cpnd_pack = settings.get("color_pack_non_divergent_name")
            cpnd_map = settings.get("color_map_non_divergent_name")
            if cpnd_pack and cpnd_map:
                self.set_active_color_map(cpnd_pack, cpnd_map, target_type='non_divergent')

            # Restore active target type AFTER specific types are loaded
            self.active_coloring_target_type = settings.get("active_coloring_target_type", 'divergent')

            # Restore image size (optional, could be handled by UI)
            self.image_width_px = settings.get("image_width_px", self.image_width_px)
            self.image_height_px = settings.get("image_height_px", self.image_height_px)
            self.update_aspect_ratio() # Ensure 'height' (complex plane) is updated

            self.last_fractal_data_cache = None # Invalidate cache
            logger.log("設定をロードしました。", level="INFO")
        except Exception as e:
            logger.log(f"設定のロード中にエラーが発生しました: {e}", level="ERROR")
            traceback.print_exc()


    logger.log("\nFractalEngine テストが完了しました。", level="INFO")
