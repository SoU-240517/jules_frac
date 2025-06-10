import os
import importlib.util
import sys
import inspect
from pathlib import Path

# アプリケーションの構造に基づいた絶対インポートを使用します。
# main.py で _project_root (jules_frac ディレクトリ) が sys.path に追加されるため、
# src.app.plugins.base_fractal_plugin のように参照可能です。
from plugins.base_fractal_plugin import FractalPlugin
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class PluginManager:
    """
    フラクタルおよびカラーリングアルゴリズムプラグインの動的読み込みを管理します。
    """
    def __init__(self,
                 project_root_path: Path,
                 fractal_plugin_folder_path: str = "plugins/fractals", # project_root_path からの相対パス
                 divergent_coloring_plugin_folder_path: str = "plugins/coloring/divergent", # 同上
                 non_divergent_coloring_plugin_folder_path: str = "plugins/coloring/non_divergent"): # 同上
        """
        PluginManager を初期化します。
        `fractal_plugin_folder_path`, `divergent_coloring_plugin_folder_path`,
        および `non_divergent_coloring_plugin_folder_path` は `project_root_path` からの相対パスです。
        """
        self.project_root = project_root_path
        self.fractal_plugin_folder = (self.project_root / fractal_plugin_folder_path).resolve()
        self.fractal_plugins: dict[str, FractalPlugin] = {}
        self.divergent_coloring_plugin_folder = (self.project_root / divergent_coloring_plugin_folder_path).resolve()
        self.non_divergent_coloring_plugin_folder = (self.project_root / non_divergent_coloring_plugin_folder_path).resolve()
        self.coloring_plugins: dict[str, ColoringAlgorithmPlugin] = {} # 単一の辞書で管理
        self.load_all_plugins()

    def load_all_plugins(self):
        """すべての種類のプラグインを読み込みます。"""
        logger.log("全プラグイン読込中...", level="INFO")
        self.fractal_plugins.clear()
        self.coloring_plugins.clear()

        self._load_plugins_from_folder(
            self.fractal_plugin_folder,
            self.fractal_plugins,
            FractalPlugin,
            "Fractal"
        )
        self._load_plugins_from_folder(
            self.divergent_coloring_plugin_folder,
            self.coloring_plugins, #同じ辞書に追加
            ColoringAlgorithmPlugin,
            "Divergent Coloring Algorithm"
        )
        self._load_plugins_from_folder(
            self.non_divergent_coloring_plugin_folder,
            self.coloring_plugins, #同じ辞書に追加
            ColoringAlgorithmPlugin,
            "Non-Divergent Coloring Algorithm"
        )

    def _load_plugins_from_folder(self, folder_path: Path, target_dict: dict, base_class: type, plugin_type_name: str):
        """
        指定された folder_path から特定の base_class のプラグインを target_dict に読み込みます。
        このメソッドは呼び出し側で target_dict.clear() を行うことを想定しています。
        """
        # target_dict.clear() # 呼び出し側 (load_all_plugins) でクリアするよう変更

        logger.log(f"{plugin_type_name} プラグインを読込中...", level="INFO")

        if not folder_path.is_dir():
            logger.log(f"{plugin_type_name} プラグインフォルダが見つかりません: {folder_path}", level="ERROR")
            return

        # プラグインは 'src.' からの絶対インポートを使用するため、sys.path の変更は不要です。
        for file_path in folder_path.glob("*.py"):
                module_name = file_path.stem

                if module_name.startswith("__") or module_name in ["base_fractal_plugin", "base_coloring_plugin"]:
                    continue
                try:
                    spec = importlib.util.spec_from_file_location(module_name, str(file_path.resolve()))
                    if spec is None or spec.loader is None:
                        logger.log(f"{file_path.name} のモジュール仕様を作成できませんでした", level="WARNING")
                        continue

                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for member_name, cls in inspect.getmembers(module, inspect.isclass):
                        # ---- デバッグ用コード開始 ----
                        # print(f"PluginManager デバッグ: クラス '{cls.__module__}.{cls.__name__}' (id: {id(cls)}) を確認中")
                        # print(f"PluginManager デバッグ: 基底クラス '{base_class.__module__}.{base_class.__name__}' (id: {id(base_class)}) と比較")
                        # is_sub = False
                        # try:
                        #     is_sub = issubclass(cls, base_class)
                        # except TypeError as te:
                        #     print(f"PluginManager デバッグ: issubclass の確認で TypeError が発生: {te}")
                        # print(f"PluginManager デバッグ: issubclass(cls, base_class) -> {is_sub}")
                        # print(f"PluginManager デバッグ: cls is base_class -> {cls is base_class}")
                        # print(f"PluginManager デバッグ: inspect.isabstract(cls) -> {inspect.isabstract(cls)}")
                        # ---- デバッグ用コード終了 ----
                        if issubclass(cls, base_class) and cls is not base_class and not inspect.isabstract(cls):
                            try:
                                plugin_instance = cls()
                                if plugin_instance.name in target_dict:
                                    logger.log(f"{plugin_type_name} プラグイン名 '{plugin_instance.name}' が重複しています。"
                                          f"{file_path.name} を無視し、既存のものを使用します。", level="WARNING")
                                else:
                                    target_dict[plugin_instance.name] = plugin_instance
                                    logger.log(f"'{plugin_instance.name}' を読込完了", level="DEBUG")
                            except Exception as e:
                                logger.log(f"{file_path.name} から {plugin_type_name} プラグイン '{member_name}' のインスタンス化に失敗: {e}", level="ERROR")
                except Exception as e:
                    logger.log(f"{plugin_type_name} プラグインファイル '{file_path.name}' の読込失敗: {e}", level="ERROR")

        if not target_dict:
            logger.log(f"'{folder_path}' に有効な {plugin_type_name} プラグインが見つかりませんでした。", level="WARNING")

    # フラクタルプラグイン固有のメソッド
    def get_available_fractal_plugins(self) -> list[FractalPlugin]:
        return list(self.fractal_plugins.values())

    def get_fractal_plugin(self, name: str) -> FractalPlugin | None:
        return self.fractal_plugins.get(name)

    # カラーリングアルゴリズムプラグイン固有のメソッド
    def get_available_coloring_plugins(self, target_type: str | None = None) -> list[ColoringAlgorithmPlugin]:
        """
        利用可能なカラーリングプラグインのリストを返します。
        target_type が指定された場合、そのタイプに一致するプラグインのみを返します。
        """
        plugins = list(self.coloring_plugins.values())
        if target_type:
            return [p for p in plugins if p.target_type == target_type]
        return plugins

    def get_coloring_plugin(self, name: str, target_type: str | None = None) -> ColoringAlgorithmPlugin | None:
        """
        指定された名前のカラーリングプラグインを取得します。
        target_type が指定された場合、プラグインのタイプも一致する必要があります。
        """
        plugin = self.coloring_plugins.get(name)
        if plugin and target_type:
            if plugin.target_type == target_type:
                pass # プラグインが見つかり、タイプも一致
            else:
                # logger.log(f"PluginManager.get_coloring_plugin: Plugin '{name}' found, but target_type mismatch (expected '{target_type}', got '{plugin.target_type}').", level="DEBUG") # このログは重複するので削除
                return None # 名前は一致したが、タイプが異なる

        if plugin:
            try:
                params = plugin.get_parameters_definition()
                logger.log(f"'{getattr(plugin, 'target_type', 'N/A')}'用プラグインあり: '{plugin.name}'", level="DEBUG")
            except Exception as e:
                logger.log(f"'{plugin.name}' のパラメータ取得中にエラー: {e}", level="ERROR")
        else:
            logger.log(f"名前 '{name}' およびターゲット '{target_type}' に該当するプラグインが見つかりません。", level="WARNING")
        return plugin

    def reload_all_plugins(self):
        """すべてのプラグインをディスクから再読み込みします。

        既存のプラグインリストはクリアされ、再度プラグインフォルダをスキャンして読み込みます。
        プラグインファイルの変更をアプリケーション実行中に反映させたい場合などに使用します。
        """
        logger.log("すべてのプラグインを再読み込み中...", level="INFO")
        self.load_all_plugins()

if __name__ == '__main__':
    logger.log("PluginManager スタンドアロンテスト", level="INFO")
    # このテストは、スクリプト実行場所からの相対的な特定のディレクトリ構造、
    # またはデフォルトパス "src/app/plugins/fractals" および "src/app/plugins/coloring" が存在し、
    # 有効なプラグインとその基底クラスが含まれていることを前提としています。

    # より堅牢なテストのためには、一時的なプラグインディレクトリとファイルを作成してください。
    # デフォルトパスが意図したとおりに機能するためには、このスクリプトをプロジェクトルートから実行する必要があります。

    current_dir = Path.cwd()
    logger.log(f"  現在の作業ディレクトリ: {current_dir}", level="INFO")

    # ダミーの基底ファイルが存在しない場合に作成します (プロジェクトルート以外からのスタンドアロンテスト用)
    temp_base_dir = Path("temp_plugin_bases_delete_me")
    temp_base_dir.mkdir(exist_ok=True)
    base_plugin_content = """
from abc import ABC, abstractmethod
import numpy as np
class FractalPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    @property
    def target_type(self) -> str: return 'divergent' # モックに target_type を追加
    @abstractmethod
    def get_parameters_definition(self) -> list: pass
    @abstractmethod
    def compute_fractal(self,c,p,w,h) -> dict: return {'iterations': np.zeros((h,w),dtype=np.int32)}
    @abstractmethod
    def get_default_view_parameters(self) -> dict: pass
"""
    with open(temp_base_dir / "base_plugin.py", "w", encoding="utf-8") as f:
        f.write(base_plugin_content)

    base_coloring_content = """
from abc import ABC, abstractmethod
import numpy as np
class ColoringAlgorithmPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    @abstractmethod
    def get_parameters_definition(self) -> list: pass
    @abstractmethod
    def apply_coloring(self,fd,cfp,ap,cm) -> np.ndarray: return np.zeros((fd['iterations'].shape[0],fd['iterations'].shape[1],4),dtype=np.uint8)
"""
    with open(temp_base_dir / "base_coloring_plugin.py", "w", encoding="utf-8") as f:
        f.write(base_coloring_content)

    # PluginManager がフォールバック経由で基底クラスをインポートできるように、temp_base_dir を sys.path に追加します
    import sys
    sys.path.insert(0, str(temp_base_dir.resolve()))

    # テスト用にダミーのプラグインディレクトリとプラグインを作成します
    test_fractal_dir = Path("temp_fractal_plugins_delete_me")
    test_fractal_dir.mkdir(exist_ok=True)
    dummy_mandel_content = f"""
from {temp_base_dir.name}.base_plugin import FractalPlugin # 一時的な構造のための調整済みインポート
import numpy as np
class TestMandel(FractalPlugin):
    @property
    def name(self): return "TestMandelbrot"
    def get_parameters_definition(self): return []
    def compute_fractal(self,c,p,w,h): return {{'iterations': np.zeros((h,w),dtype=np.int32), 'last_z_modulus_sq': np.zeros((h,w),dtype=np.float64)}}
    def get_default_view_parameters(self): return {{}}
"""
    with open(test_fractal_dir / "test_mandel_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_mandel_content)

    # Divergent Coloring Plugins
    test_divergent_coloring_dir = Path("temp_divergent_coloring_plugins_delete_me")
    test_divergent_coloring_dir.mkdir(exist_ok=True)
    dummy_gray_divergent_content = f"""
from {temp_base_dir.name}.base_coloring_plugin import ColoringAlgorithmPlugin # 調整済みインポート
import numpy as np
class TestGrayDivergent(ColoringAlgorithmPlugin):
    @property
    def name(self): return "TestGrayscaleDivergent"
    # target_type はデフォルトの 'divergent' を使用します
    def get_parameters_definition(self): return []
    def apply_coloring(self,fd,cfp,ap,cm): return np.zeros((fd['iterations'].shape[0],fd['iterations'].shape[1],4),dtype=np.uint8)
"""
    with open(test_divergent_coloring_dir / "test_gray_divergent_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_gray_divergent_content)

    # Non-Divergent Coloring Plugins
    test_non_divergent_coloring_dir = Path("temp_non_divergent_coloring_plugins_delete_me")
    test_non_divergent_coloring_dir.mkdir(exist_ok=True)
    dummy_color_non_divergent_content = f"""
from {temp_base_dir.name}.base_coloring_plugin import ColoringAlgorithmPlugin # 調整済みインポート
import numpy as np
class TestColorNonDivergent(ColoringAlgorithmPlugin):
    @property
    def name(self): return "TestColorNonDivergent"
    @property
    def target_type(self): return 'non_divergent' # target_type を上書き
    def get_parameters_definition(self): return []
    def apply_coloring(self,fd,cfp,ap,cm): return np.zeros((fd['iterations'].shape[0],fd['iterations'].shape[1],4),dtype=np.uint8)
"""
    with open(test_non_divergent_coloring_dir / "test_color_non_divergent_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_color_non_divergent_content)

    logger.log(f"  一時プラグインディレクトリを作成しました: {test_fractal_dir.resolve()}, {test_divergent_coloring_dir.resolve()}, {test_non_divergent_coloring_dir.resolve()}", level="INFO")

    # スタンドアロンテストの場合、project_root は現在のディレクトリであり、
    # プラグインフォルダパスはこれに対する相対パスです。
    manager = PluginManager(
        project_root_path=Path.cwd(), # テストは CWD が一時ディレクトリの作成場所であることを前提としています
        fractal_plugin_folder_path=test_fractal_dir.name,
        divergent_coloring_plugin_folder_path=test_divergent_coloring_dir.name,
        non_divergent_coloring_plugin_folder_path=test_non_divergent_coloring_dir.name
    )

    logger.log("\n利用可能なフラクタルプラグイン:", level="INFO")
    for p in manager.get_available_fractal_plugins(): logger.log(f"  - {p.name}", level="INFO")
    assert manager.get_fractal_plugin("TestMandelbrot") is not None, "TestMandelbrot が読み込まれていません"

    logger.log("\n利用可能なカラーリングプラグイン (すべて):", level="INFO")
    all_coloring_plugins = manager.get_available_coloring_plugins()
    for p in all_coloring_plugins: logger.log(f"  - {p.name} (type: {p.target_type})", level="INFO")
    assert len(all_coloring_plugins) == 2, "すべてのカラーリングプラグインが読み込まれていません"
    assert manager.get_coloring_plugin("TestGrayscaleDivergent") is not None
    assert manager.get_coloring_plugin("TestColorNonDivergent") is not None

    logger.log("\n利用可能なカラーリングプラグイン (divergent のみ):", level="INFO")
    divergent_plugins = manager.get_available_coloring_plugins(target_type='divergent')
    for p in divergent_plugins: logger.log(f"  - {p.name} (type: {p.target_type})", level="INFO")
    assert len(divergent_plugins) == 1, "Divergent プラグインのフィルタリングが正しくありません"
    assert divergent_plugins[0].name == "TestGrayscaleDivergent"

    logger.log("\n利用可能なカラーリングプラグイン (non_divergent のみ):", level="INFO")
    non_divergent_plugins = manager.get_available_coloring_plugins(target_type='non_divergent')
    for p in non_divergent_plugins: logger.log(f"  - {p.name} (type: {p.target_type})", level="INFO")
    assert len(non_divergent_plugins) == 1, "Non-Divergent プラグインのフィルタリングが正しくありません"
    assert non_divergent_plugins[0].name == "TestColorNonDivergent"

    logger.log("\n特定のカラーリングプラグイン取得テスト:", level="INFO")
    assert manager.get_coloring_plugin("TestGrayscaleDivergent", target_type='divergent') is not None, "Divergent プラグインを type指定で取得できませんでした"
    assert manager.get_coloring_plugin("TestGrayscaleDivergent", target_type='non_divergent') is None, "Divergent プラグインを誤ったtype指定で取得してしまいました"
    assert manager.get_coloring_plugin("TestColorNonDivergent", target_type='non_divergent') is not None, "Non-Divergent プラグインを type指定で取得できませんでした"
    assert manager.get_coloring_plugin("TestColorNonDivergent", target_type='divergent') is None, "Non-Divergent プラグインを誤ったtype指定で取得してしまいました"
    assert manager.get_coloring_plugin("NonExistentPlugin") is None, "存在しないプラグインを取得してしまいました"


    logger.log("\nプラグイン再読み込みテスト...", level="INFO")
    manager.reload_all_plugins()
    assert manager.get_fractal_plugin("TestMandelbrot") is not None, "再読み込み後 TestMandelbrot が読み込まれていません"
    assert manager.get_coloring_plugin("TestGrayscaleDivergent", target_type='divergent') is not None, "再読み込み後 TestGrayscaleDivergent が読み込まれていません"
    assert manager.get_coloring_plugin("TestColorNonDivergent", target_type='non_divergent') is not None, "再読み込み後 TestColorNonDivergent が読み込まれていません"
    assert len(manager.get_available_coloring_plugins()) == 2, "再読み込み後、すべてのカラーリングプラグイン数が正しくありません"
    logger.log("プラグインが正常に再読み込みされました。", level="INFO")

    # 一時ディレクトリとファイルをクリーンアップします
    import shutil
    try:
        shutil.rmtree(test_fractal_dir)
        shutil.rmtree(test_divergent_coloring_dir)
        shutil.rmtree(test_non_divergent_coloring_dir)
        shutil.rmtree(temp_base_dir)
        # sys.path.pop(0) # sys.path から temp_base_dir を削除します
        logger.log("\n一時テストディレクトリとファイルをクリーンアップしました。", level="INFO")
    except Exception as e:
        logger.log(f"\nクリーンアップ中のエラー: {e}", level="ERROR")

    logger.log("\nPluginManager テストが完了しました。", level="INFO")
