import sys
import json
import shutil
from pathlib import Path
import numba

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from views.main_window import MainWindow
from models.fractal_engine import FractalEngine
from controllers.fractal_controller import FractalController
from settings_manager import SettingsManager
from logger.custom_logger import CustomLogger

# プロジェクトのルートディレクトリ（'src'の親）をsys.pathに追加
# これにより、'jules_frac' ディレクトリからの相対インポートや、そのサブディレクトリからのインポートが可能になる
_project_root = Path(__file__).resolve().parent # このスクリプトがあるディレクトリをプロジェクトルートとする
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# --- 定数定義 ---
SETTINGS_FILE_NAME = "settings.jsonc"
DEFAULT_STYLESHEET_PATH = "style.qss" # デフォルトのスタイルシートパス

logger = CustomLogger()
logger.set_project_root(_project_root) # プロジェクトルートを設定

# --- 共通: パスをプロジェクトルートからの相対パスに変換 ---
def _to_relpath(p):
    try:
        prj = _project_root
        if prj and Path(p).is_absolute():
            return str(Path(p).relative_to(prj))
    except Exception:
        pass
    return str(p)

def clear_numba_cache_on_exit(settings_manager: SettingsManager):
    """Numbaのキャッシュディレクトリを安全に削除する。"""
    numba_config = settings_manager.get_setting("app_settings.numba_settings", {})
    clear_cache = numba_config.get("clear_cache_on_exit", False)

    if not clear_cache:
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

def setup_application():
    """QApplicationインスタンスを作成し、High DPI設定を適用する。"""
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    return QApplication(sys.argv)

def apply_stylesheet(app, path):
    """外部ファイルからスタイルシートを読み込み、アプリケーションに適用する。"""
    stylesheet_path = Path(path)
    if stylesheet_path.exists():
        try:
            with open(stylesheet_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.log(f"スタイルシートを適用しました: {_to_relpath(stylesheet_path)}", level="INFO")
        except Exception as e:
            logger.log(f"スタイルシートの読み込みまたは適用中にエラーが発生しました: {e}", level="ERROR")
    else:
        logger.log(f"スタイルシートファイルが見つかりません: {_to_relpath(stylesheet_path)}", level="WARNING")

def setup_logging(settings_manager, logger_instance):
    """設定ファイルからロギング設定を読み込み、ロガーに適用する。"""
    # app_settingsからロギング設定を取得
    log_config = settings_manager.get_setting("app_settings.logging", {"level": "INFO", "enabled": True})
    log_level = log_config.get("level", "INFO")
    log_enabled = log_config.get("enabled", True)

    logger_instance.set_level(log_level)
    logger_instance.set_enabled(log_enabled)
    logger_instance.log(f"ロガー設定適用 [レベル: {log_level}, 有効: {log_enabled}]", level="DEBUG")

def main():
    """アプリケーションのメインエントリーポイント。"""
    app = setup_application()

    # --- 設定とロガーの初期化 ---
    settings_file_path = _project_root / SETTINGS_FILE_NAME
    settings_manager = SettingsManager(settings_filename=str(settings_file_path))
    setup_logging(settings_manager, logger)

    # --- サブキーで管理された設定の取得 ---
    # engine_settings, presets などは settings.jsonc のサブキーとして管理
    engine_settings = settings_manager.get_setting("engine_settings", {})
    presets = settings_manager.get_setting("presets", {})

    # --- Numbaキャッシュ設定の適用 ---
    numba_config = settings_manager.get_setting("app_settings.numba_settings", {"cache_enabled": True})
    numba.config.CACHE = numba_config.get("cache_enabled", True)
    logger.log(f"Numbaキャッシュ設定適用 [有効: {numba.config.CACHE}]", level="DEBUG")

    # --- スタイルシートの適用 ---
    app_config = settings_manager.get_setting("app_settings", {})
    stylesheet_file_path = _project_root / app_config.get("stylesheet_path", DEFAULT_STYLESHEET_PATH)
    apply_stylesheet(app, stylesheet_file_path)

    # --- MVCコンポーネントの作成 ---
    fractal_engine = FractalEngine(project_root_path=_project_root, settings_manager=settings_manager)
    fractal_controller = FractalController(fractal_engine, settings_manager)
    fractal_controller.apply_configuration_from_settings()

    main_window = MainWindow(fractal_controller, settings_manager)
    fractal_controller.set_main_window(main_window)

    # --- シグナルとスロットの接続 ---
    if hasattr(main_window, 'status_bar') and main_window.status_bar is not None:
        fractal_controller.status_updated.connect(main_window.update_status_bar)
    else:
        logger.log("警告: MainWindow.status_barが見つからないため、status_updatedシグナルを接続できません。", level="WARNING")

    # --- 終了時処理の接続 ---
    def save_settings_on_exit():
        """アプリケーション終了時に全ての設定を settings.jsonc に保存する。"""
        logger.log("終了処理を開始します。全ての設定を保存します...", level="INFO")
        # コントローラから最新のエンジン設定を取得し、settings.jsonc のサブキーに保存
        engine_config = fractal_controller.get_full_configuration()
        settings_manager.set_setting("engine_settings", engine_config, auto_save=False)
        # プリセットも同様に保存（必要なら）
        current_presets = settings_manager.get_setting("presets", {})
        settings_manager.set_setting("presets", current_presets, auto_save=False)
        # その他の app_settings なども自動的に SettingsManager が管理
        settings_manager.save_settings()

    app.aboutToQuit.connect(save_settings_on_exit)
    app.aboutToQuit.connect(lambda: clear_numba_cache_on_exit(settings_manager))

    main_window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
