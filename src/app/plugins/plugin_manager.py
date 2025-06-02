import os
import importlib.util
import inspect
from pathlib import Path

# 基底クラスのインポート
# プロジェクトの構造に合わせて調整が必要な場合がある
# 例: from src.app.plugins.base_plugin import FractalPlugin (プロジェクトルートから実行する場合)
# 例: from .base_plugin import FractalPlugin (このファイルと同じディレクトリか親をパッケージルートとする場合)
try:
    from .base_plugin import FractalPlugin
except ImportError:
    # フォールバックや別の方法を試みる (テスト実行時など)
    # このフォールバックは、このファイルが src/app/plugins 内にあることを想定
    from base_plugin import FractalPlugin


class PluginManager:
    """
    フラクタルプラグインを動的にロードし管理するクラス。
    """
    def __init__(self, plugin_folder_path: str = "src/app/plugins/fractals"):
        """
        PluginManagerを初期化します。

        引数:
            plugin_folder_path (str): プラグインファイルが格納されているフォルダへのパス。
                                     このパスはプロジェクトルートからの相対パスとして扱われます。
        """
        # プロジェクトルートを基準としたPathオブジェクトを作成
        # Path.cwd() は現在の作業ディレクトリであり、プロジェクトルートとは限らないため注意。
        # ここでは、実行時のカレントディレクトリがプロジェクトルートであることを期待するか、
        # main.pyなどで絶対パスを渡すことを推奨。
        # 簡単のため、渡されたパスをそのまま使う。
        self.plugin_folder = Path(plugin_folder_path)
        self.plugins = {}  # ロードされたプラグインインスタンスを格納: {name: instance}
        self.load_plugins()

    def load_plugins(self):
        """
        プラグインフォルダから全てのフラクタルプラグインをロードします。
        """
        self.plugins.clear()

        # plugin_folderが絶対パスでない場合、カレントディレクトリからの相対パスと解釈される。
        # これが意図通りか確認が必要。通常はmain.pyの位置などを基準に絶対パス化するのが堅牢。
        effective_plugin_folder = self.plugin_folder
        if not self.plugin_folder.is_absolute():
            # ここではカレントディレクトリを基準とする。
            # より堅牢なのは、アプリケーションのルートパスを別途取得し、それと結合すること。
            effective_plugin_folder = Path.cwd() / self.plugin_folder
            # print(f"PluginManager: プラグインフォルダの相対パスを解決: {effective_plugin_folder.resolve()}")


        print(f"PluginManager: プラグインフォルダ '{effective_plugin_folder.resolve()}' からプラグインをロード中...")

        if not effective_plugin_folder.is_dir():
            print(f"PluginManager: エラー - プラグインフォルダが見つかりません: {effective_plugin_folder.resolve()}")
            return

        for file_path in effective_plugin_folder.glob("*.py"):
            module_name = file_path.stem

            if module_name.startswith("__") or module_name == "base_plugin":
                continue

            try:
                spec = importlib.util.spec_from_file_location(module_name, str(file_path.resolve()))
                if spec is None or spec.loader is None:
                    print(f"PluginManager: 警告 - モジュールスペックの作成に失敗 - {file_path.name}")
                    continue

                module = importlib.util.module_from_spec(spec)
                # モジュールがロードされる前にsys.modulesに追加することが推奨される場合がある
                # sys.modules[module_name] = module
                spec.loader.exec_module(module)

                for name, cls in inspect.getmembers(module, inspect.isclass):
                    # issubclassのチェック、FractalPlugin自体でないこと、抽象クラスでないことを確認
                    if issubclass(cls, FractalPlugin) and cls is not FractalPlugin and not inspect.isabstract(cls):
                        try:
                            plugin_instance = cls()
                            if plugin_instance.name in self.plugins:
                                print(f"PluginManager: 警告 - プラグイン名 '{plugin_instance.name}' が重複。({file_path.name} は無視されます)")
                            else:
                                self.plugins[plugin_instance.name] = plugin_instance
                                print(f"PluginManager: プラグイン '{plugin_instance.name}' をロードしました ({file_path.name} より)。")
                        except Exception as e:
                            print(f"PluginManager: エラー - プラグイン '{name}' のインスタンス化に失敗 ({file_path.name}): {e}")
            except Exception as e:
                print(f"PluginManager: エラー - プラグインファイル '{file_path.name}' のロードに失敗: {e}")

        if not self.plugins:
            print("PluginManager: 有効なプラグインが見つかりませんでした。")

    def get_available_plugins(self) -> list[FractalPlugin]:
        """ロードされている全てのプラグインのリストを返します。"""
        return list(self.plugins.values())

    def get_plugin(self, name: str) -> FractalPlugin | None:
        """指定された名前のプラグインを返します。見つからない場合はNoneを返します。"""
        return self.plugins.get(name)

    def reload_plugins(self):
        """プラグインを再ロードします。"""
        print("PluginManager: プラグインを再ロードします...")
        self.load_plugins()

if __name__ == '__main__':
    print("PluginManager 単体テスト:")
    print("このテストは、特定のディレクトリ構造とプラグインファイルが存在することを前提としています。")
    print("プロジェクトルートから `python -m src.app.plugins.plugin_manager` のように実行するか、")
    print("適切なテスト環境をセットアップして実行してください。")

    # 簡易テスト用のセットアップ (プロジェクトルートからの実行を模倣)
    # 1. src/app/plugins/fractals/ にダミープラグインを置く
    # 2. src/app/plugins/base_plugin.py が存在することを確認

    # このテストを実行するには、このファイル (plugin_manager.py) が
    # src/app/plugins/ ディレクトリにあり、
    # base_plugin.py が同じディレクトリにあり、
    # src/app/plugins/fractals/ ディレクトリが存在し、
    # そこにテスト用プラグイン (例: mandelbrot_plugin.py) がある必要があります。

    # 以下のコードは、このファイルが src/app/plugins/ にあると仮定して、
    # src/app/plugins/fractals をプラグインフォルダとして PluginManager をテストします。
    # 実行前に、src/app/plugins/fractals ディレクトリを作成し、
    # 何かダミーのプラグインファイル (FractalPluginを継承したもの) を入れてください。

    current_file_path = Path(__file__).resolve() # plugin_manager.py の絶対パス
    # src/app/plugins/ を想定
    plugins_dir = current_file_path.parent
    # src/app/ を想定
    app_dir = plugins_dir.parent
    # src/ を想定
    src_dir = app_dir.parent
    # プロジェクトルートを src の親と仮定
    project_root = src_dir.parent

    # テスト用のプラグインフォルダパス (プロジェクトルートからの相対パス)
    test_plugin_folder = "src/app/plugins/fractals"

    print(f"  プロジェクトルート (推定): {project_root}")
    print(f"  プラグインフォルダ (テスト用): {Path(test_plugin_folder).resolve()}")

    # ダミーのフラクタルプラグインファイルを作成 (テスト時のみ)
    fractals_test_path = project_root / test_plugin_folder
    fractals_test_path.mkdir(parents=True, exist_ok=True)

    dummy_plugin_content_for_test = f"""
from ..base_plugin import FractalPlugin # from src.app.plugins.base_plugin import FractalPlugin でも可
import numpy as np

class MyManagerTestPlugin(FractalPlugin):
    @property
    def name(self) -> str: return "ManagerTestPlugin"
    def get_parameters_definition(self) -> list: return []
    def compute_fractal(self, cp, pp, w, h) -> np.ndarray: return np.zeros((h,w), dtype=np.int32)
    def get_default_view_parameters(self) -> dict: return {{'center_real':0,'center_imag':0,'width':2}}
"""
    with open(fractals_test_path / "my_manager_test_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_plugin_content_for_test)

    # base_plugin.py が plugins_dir にあることを確認
    if not (plugins_dir / "base_plugin.py").exists():
        print(f"エラー: base_plugin.py が {plugins_dir} に見つかりません。テストをスキップします。")
    else:
        print("\nPluginManager のインスタンス化とプラグインロードのテスト...")
        try:
            # PluginManagerのインスタンス化 (プロジェクトルートからのパスで)
            manager = PluginManager(plugin_folder_path=test_plugin_folder)

            available_plugins = manager.get_available_plugins()
            if available_plugins:
                print(f"  利用可能なプラグイン: {[p.name for p in available_plugins]}")
                test_plugin = manager.get_plugin("ManagerTestPlugin")
                if test_plugin:
                    print(f"  '{test_plugin.name}' プラグインの取得に成功しました。")
                    print(f"    デフォルトビュー: {test_plugin.get_default_view_parameters()}")
                else:
                    print("  'ManagerTestPlugin' が見つかりませんでした。")
            else:
                print("  テストプラグインは見つかりませんでした。")

            print("\n  リロードテスト...")
            manager.reload_plugins()
            available_plugins_after_reload = manager.get_available_plugins()
            print(f"  リロード後の利用可能なプラグイン: {[p.name for p in available_plugins_after_reload]}")


        except ImportError as e:
            print(f"  インポートエラーが発生しました: {e}")
            print("  このテストは、特定のプロジェクト構造とPYTHONPATH設定に依存します。")
            print("  `PYTHONPATH=. python src/app/plugins/plugin_manager.py` のように実行してみてください。")
        except Exception as e:
            print(f"  テスト中に予期せぬエラーが発生しました: {e}")

    # クリーンアップ
    # try:
    #     os.remove(fractals_test_path / "my_manager_test_plugin.py")
    #     # os.rmdir(fractals_test_path) # 空でないと消せない
    # except OSError as e:
    #     print(f"クリーンアップエラー: {e}")
    print("\nPluginManager 単体テスト終了。")
