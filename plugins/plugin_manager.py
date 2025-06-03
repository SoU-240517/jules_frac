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
                 coloring_plugin_folder_path: str = "plugins/coloring"): # project_root_path からの相対パス
        """
        PluginManager を初期化します。
        `fractal_plugin_folder_path` および `coloring_plugin_folder_path` は `project_root_path` からの相対パスです。
        """
        self.project_root = project_root_path
        self.fractal_plugin_folder = (self.project_root / fractal_plugin_folder_path).resolve()
        self.fractal_plugins: dict[str, FractalPlugin] = {}
        self.coloring_plugin_folder = (self.project_root / coloring_plugin_folder_path).resolve()
        self.coloring_plugins: dict[str, ColoringAlgorithmPlugin] = {}
        self.load_all_plugins()

    def load_all_plugins(self):
        """すべての種類のプラグインを読み込みます。"""
        logger.log("すべてのプラグインを読み込み中...", level="INFO")
        self._load_plugins_from_folder(
            self.fractal_plugin_folder,
            self.fractal_plugins,
            FractalPlugin,
            "Fractal"
        )
        self._load_plugins_from_folder(
            self.coloring_plugin_folder,
            self.coloring_plugins,
            ColoringAlgorithmPlugin,
            "Coloring Algorithm"
        )

    def _load_plugins_from_folder(self, folder_path: Path, target_dict: dict, base_class: type, plugin_type_name: str):
        """
        指定された folder_path から特定の base_class のプラグインを target_dict に読み込みます。
        """
        target_dict.clear()

        logger.log(f"'{folder_path}' から {plugin_type_name} プラグインを読み込み中...", level="INFO")

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
                                    logger.log(f"{file_path.name} から {plugin_type_name} プラグイン '{plugin_instance.name}' を読み込みました。", level="INFO")
                            except Exception as e:
                                logger.log(f"{file_path.name} から {plugin_type_name} プラグイン '{member_name}' のインスタンス化に失敗しました: {e}", level="ERROR")
                except Exception as e:
                    logger.log(f"{plugin_type_name} プラグインファイル '{file_path.name}' の読み込みに失敗しました: {e}", level="ERROR")

        if not target_dict:
            logger.log(f"'{folder_path}' に有効な {plugin_type_name} プラグインが見つかりませんでした。", level="WARNING")

    # フラクタルプラグイン固有のメソッド
    def get_available_fractal_plugins(self) -> list[FractalPlugin]:
        return list(self.fractal_plugins.values())

    def get_fractal_plugin(self, name: str) -> FractalPlugin | None:
        return self.fractal_plugins.get(name)

    # カラーリングアルゴリズムプラグイン固有のメソッド
    def get_available_coloring_plugins(self) -> list[ColoringAlgorithmPlugin]:
        return list(self.coloring_plugins.values())

    def get_coloring_plugin(self, name: str) -> ColoringAlgorithmPlugin | None:
        return self.coloring_plugins.get(name)

    def reload_all_plugins(self):
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

    test_coloring_dir = Path("temp_coloring_plugins_delete_me")
    test_coloring_dir.mkdir(exist_ok=True)
    dummy_gray_content = f"""
from {temp_base_dir.name}.base_coloring_plugin import ColoringAlgorithmPlugin # 調整済みインポート
import numpy as np
class TestGray(ColoringAlgorithmPlugin):
    @property
    def name(self): return "TestGrayscale"
    def get_parameters_definition(self): return []
    def apply_coloring(self,fd,cfp,ap,cm): return np.zeros((fd['iterations'].shape[0],fd['iterations'].shape[1],4),dtype=np.uint8)
"""
    with open(test_coloring_dir / "test_gray_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_gray_content)

    logger.log(f"  一時プラグインディレクトリを作成しました: {test_fractal_dir.resolve()}, {test_coloring_dir.resolve()}", level="INFO")

    # スタンドアロンテストの場合、project_root は現在のディレクトリであり、
    # プラグインフォルダパスはこれに対する相対パスです。
    manager = PluginManager(
        project_root_path=Path.cwd(), # テストは CWD が一時ディレクトリの作成場所であることを前提としています
        fractal_plugin_folder_path=test_fractal_dir.name, # CWD からの相対パス文字列として渡します
        coloring_plugin_folder_path=test_coloring_dir.name # CWD からの相対パス文字列として渡します
    )

    logger.log("\n利用可能なフラクタルプラグイン:", level="INFO")
    for p in manager.get_available_fractal_plugins(): logger.log(f"  - {p.name}", level="INFO")
    assert manager.get_fractal_plugin("TestMandelbrot") is not None, "TestMandelbrot が読み込まれていません"

    logger.log("\n利用可能なカラーリングプラグイン:", level="INFO")
    for p in manager.get_available_coloring_plugins(): logger.log(f"  - {p.name}", level="INFO")
    assert manager.get_coloring_plugin("TestGrayscale") is not None, "TestGrayscale が読み込まれていません"

    logger.log("\nプラグイン再読み込みテスト...", level="INFO")
    manager.reload_all_plugins()
    assert manager.get_fractal_plugin("TestMandelbrot") is not None, "再読み込み後 TestMandelbrot が読み込まれていません"
    assert manager.get_coloring_plugin("TestGrayscale") is not None, "再読み込み後 TestGrayscale が読み込まれていません"
    logger.log("プラグインが正常に再読み込みされました。", level="INFO")

    # 一時ディレクトリとファイルをクリーンアップします
    import shutil
    try:
        shutil.rmtree(test_fractal_dir)
        shutil.rmtree(test_coloring_dir)
        shutil.rmtree(temp_base_dir)
        # sys.path.pop(0) # sys.path から temp_base_dir を削除します
        logger.log("\n一時テストディレクトリとファイルをクリーンアップしました。", level="INFO")
    except Exception as e:
        logger.log(f"\nクリーンアップ中のエラー: {e}", level="ERROR")

    logger.log("\nPluginManager テストが完了しました。", level="INFO")
