from math import log
import sys
from pathlib import Path
import shutil
import numba

# Numbaのキャッシュ機能をグローバルに有効化する
# この設定は、個々の @jit(cache=True) よりも優先されることを期待
numba.config.CACHE = True

# プロジェクトのルートディレクトリ（'src'の親）をsys.pathに追加
# これにより、'jules_frac' ディレクトリからの相対インポートや、そのサブディレクトリからのインポートが可能になる
_project_root = Path(__file__).resolve().parent # このスクリプトがあるディレクトリをプロジェクトルートとする
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PyQt6.QtWidgets import QApplication
from views.main_window import MainWindow
from models.fractal_engine import FractalEngine
from controllers.fractal_controller import FractalController
from utils.settings_manager import SettingsManager
from PyQt6.QtCore import Qt

from logger.custom_logger import CustomLogger

logger = CustomLogger()
logger.set_project_root(_project_root) # プロジェクトルートを設定

def clear_numba_cache_on_exit():
    """Numbaのキャッシュディレクトリを安全に削除する。"""
    # この機能は現在無効化されています。キャッシュをクリアしたい場合は、手動で__pycache__フォルダを削除するか、この関数のコメントアウトを解除してください。
    return
    logger.log("Numbaキャッシュのクリアを試みます...", level="INFO")
    try:
        numba_cache_dir_path_str = numba.config.CACHE_DIR
        if numba_cache_dir_path_str:
            numba_cache_dir = Path(numba_cache_dir_path_str)
            if numba_cache_dir.exists() and numba_cache_dir.is_dir():
                logger.log(f"Numbaキャッシュディレクトリをクリアします: {numba_cache_dir}", level="INFO")
                shutil.rmtree(numba_cache_dir, ignore_errors=True)
                logger.log(f"Numbaキャッシュディレクトリをクリアしました。", level="INFO")
            else:
                logger.log(f"Numbaキャッシュディレクトリが見つからないか、ディレクトリではありません: {numba_cache_dir}", level="INFO")
        else:
            logger.log(f"Numbaキャッシュディレクトリが設定されていません (numba.config.CACHE_DIR is None)。", level="INFO")
    except ImportError:
        logger.log("Numbaまたはshutilモジュールが見つからないため、Numbaキャッシュをクリアできません。", level="WARNING")
    except Exception as e:
        logger.log(f"Numbaキャッシュディレクトリのクリア中にエラーが発生しました: {e}", level="WARNING")

if __name__ == '__main__':
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    settings_file_name = "base_settings.json" # 設定ファイル名
    settings_file_path = _project_root / settings_file_name # SettingsManager で使用するための絶対パス
    settings_manager = SettingsManager(settings_filename=str(settings_file_path))

    # --- ロガー設定のロードと適用 ---
    # CustomLogger はシングルトンなので、モジュールレベルの `logger` インスタンスは SettingsManager の初期化時にデフォルトで作成されます。
    # CustomLogger の初期化時には、SettingsManager から設定を読み込もうとしますが、
    # その時点ではSettingsManagerが完全に初期化されていない可能性があるため、デフォルト値で起動します。
    # ここで、完全に初期化されたSettingsManagerから設定を明示的に適用します。
    # "logging" セクション全体を取得し、存在しない場合のデフォルト値を指定します。
    log_config = settings_manager.get_setting("logging", {"level": "INFO", "enabled": True})
    log_level_to_set = log_config.get("level", "INFO")
    log_enabled_to_set = log_config.get("enabled", True)

    logger.set_level(log_level_to_set) # 設定ファイルから読み込んだレベルを適用
    logger.set_enabled(log_enabled_to_set)
    # 実際にDEBUGレベルでログが出力されるかは、ファイル内の設定とここでの設定によります。
    logger.log(f"ロガー設定適用 [レベル: {log_level_to_set}, 有効: {log_enabled_to_set}]", level="DEBUG")
    # --- ロガー設定完了 ---

    # --- Numbaキャッシュのクリア ---
    # パフォーマンス向上のため、キャッシュの自動クリアは無効化されています。
    # clear_numba_cache_on_exit()
    # --- Numbaキャッシュのクリア完了 ---

    # モデル・コントローラーの作成
    fractal_engine = FractalEngine(project_root_path=_project_root, settings_manager=settings_manager)
    fractal_controller = FractalController(fractal_engine)

    # ダークテーマのスタイルシート
    app.setStyleSheet("""
        QWidget {
            background-color: #2e2e2e;
            color: #e0e0e0;
            font-size: 10pt;
        }
        QMainWindow {
            background-color: #252525;
        }
        QMenuBar {
            background-color: #3c3c3c;
        }
        QMenuBar::item { /* メニュー項目の通常状態 */
            background-color: #3c3c3c;
            color: #e0e0e0;
        }
        QMenuBar::item::selected { /* メニュー項目のホバー時 */
            background-color: #505050;
        }
        QMenuBar::item::pressed { /* クリック時 */
            background-color: #555555;
        }
        QMenu {
            background-color: #3c3c3c;
            border: 1px solid #505050;
            color: #e0e0e0;
        }
        QMenu::item::selected { /* サブメニュー項目のホバー時 */
            background-color: #505050;
            color: #ffffff;
        }
        QPushButton {
            background-color: #505050;
            border: 1px solid #606060;
            padding: 5px;
            min-width: 70px;
        }
        QPushButton:hover { /* ボタンのホバー時 */
            background-color: #606060;
        }
        QPushButton:pressed { /* ボタンのクリック時 */
            background-color: #404040;
        }
        QScrollArea {
            border: 1px solid #3c3c3c;
        }
        QLabel {
            color: #e0e0e0;
        }
        QSplitter::handle { /* スプリッターのハンドル */
            background-color: #3c3c3c;
            border: 1px solid #505050;
        }
        QSplitter::handle:horizontal { width: 2px; }
        QSplitter::handle:vertical { height: 2px; }
        QSplitter::handle:hover { background-color: #505050; }
    """)

    # MainWindowにSettingsManagerのインスタンスを渡す
    main_window = MainWindow(fractal_controller, settings_manager)
    fractal_controller.set_main_window(main_window)

    if hasattr(main_window, 'status_bar') and main_window.status_bar is not None: # status_barが存在するか確認
        fractal_controller.status_updated.connect(main_window.update_status_bar)
    else:
        logger.log("警告: MainWindow.status_barが見つからない、または初期化されていないため、status_updatedシグナルを接続できません。", level="WARNING")

    main_window.show()

    # アプリケーションの終了時にキャッシュをクリアするシグナルを接続
    # パフォーマンス向上のため、キャッシュの自動クリアは無効化されています。
    # app.aboutToQuit.connect(clear_numba_cache_on_exit)

    def save_engine_settings_on_exit():
        # base_settings.json から save_engine_settings の値を取得
        # デフォルト値は True (従来通りの動作)
        should_save_engine_settings = settings_manager.get_setting("save_engine_settings", True)

        if should_save_engine_settings:
            logger.log("アプリケーション終了前にエンジン設定を保存します...", level="INFO")
            engine_config = fractal_engine.save_settings()
            settings_manager.set_setting("engine_settings", engine_config, auto_save=False) # auto_save=Falseにして最後にまとめて保存
            settings_manager.save_settings() # ここでウィンドウ設定なども含めて全て保存
            logger.log("エンジン設定を保存しました。", level="INFO")
        else:
            logger.log("エンジン設定の保存はスキップされました (save_engine_settings is false)。", level="INFO")

    app.aboutToQuit.connect(save_engine_settings_on_exit)
    sys.exit(app.exec())
