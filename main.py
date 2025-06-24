from pathlib import Path
import sys
import numba
import shutil
import json

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

# --- 定数定義 ---
SETTINGS_FILE_NAME = "settings.jsonc"
INIT_ENGINE_SETTINGS_FILE_NAME = "resources/init_engine_settings.json"
PRESET_FILE_NAME = "resources/preset/preset_record.json"
DEFAULT_STYLESHEET_PATH = "resources/style.qss" # デフォルトのスタイルシートパス

logger = CustomLogger()
logger.set_project_root(_project_root) # プロジェクトルートを設定

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
            logger.log(f"スタイルシートを適用しました: {stylesheet_path}", level="INFO")
        except Exception as e:
            logger.log(f"スタイルシートの読み込みまたは適用中にエラーが発生しました: {e}", level="ERROR")
    else:
        logger.log(f"スタイルシートファイルが見つかりません: {stylesheet_path}", level="WARNING")

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

    # --- プリセットを専用ファイルからロード ---
    preset_file_path = _project_root / PRESET_FILE_NAME
    if preset_file_path.exists():
        try:
            with open(preset_file_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
            # settings.jsoncのpresetsを上書きする
            settings_manager.set_setting("presets", presets, auto_save=False)
            logger.log(f"プリセットをロードしました: {preset_file_path}", level="INFO")
        except Exception as e:
            logger.log(f"プリセットファイルの読み込みに失敗しました: {e}", level="ERROR")

    # --- 初期エンジン設定を専用ファイルからロード ---
    init_engine_settings_path = _project_root / INIT_ENGINE_SETTINGS_FILE_NAME
    if init_engine_settings_path.exists():
        try:
            # JSONC形式の可能性を考慮し、一時的なSettingsManagerで読み込む
            temp_settings_manager = SettingsManager(settings_filename=str(init_engine_settings_path))
            init_engine_settings = temp_settings_manager.get_all_settings()
            # settings.jsoncから読み込んだエンジン設定を上書きする
            settings_manager.set_setting("engine_settings", init_engine_settings, auto_save=False)
            logger.log(f"初期エンジン設定をロードしました: {init_engine_settings_path}", level="INFO")
        except Exception as e:
            logger.log(f"初期エンジン設定ファイルの読み込みに失敗しました: {e}", level="ERROR")

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
        # エンジン設定の保存 (settings.jsoncへ)
        app_config = settings_manager.get_setting("app_settings", {})
        should_save_engine = app_config.get("save_engine_settings", True)
        if should_save_engine:
            logger.log("アプリケーション終了前にエンジン設定を保存します...", level="INFO")
            engine_config = fractal_controller.get_full_configuration()
            settings_manager.set_setting("engine_settings", engine_config, auto_save=False)
            logger.log("エンジン設定を保存キューに追加しました。", level="INFO")
        else:
            logger.log("エンジン設定の保存はスキップされました (save_engine_settings is false)。", level="INFO")

        # プリセットの保存 (preset_record.jsonへ)
        presets = settings_manager.get_setting("presets", {})
        if presets:
            preset_file_path = _project_root / PRESET_FILE_NAME
            try:
                with open(preset_file_path, "w", encoding="utf-8") as f:
                    json.dump(presets, f, indent=4, ensure_ascii=False)
                logger.log(f"プリセットを保存しました: {preset_file_path}", level="INFO")
                # settings.jsoncからはpresetsを削除する
                settings_manager.set_setting("presets", {}, auto_save=False)
            except Exception as e:
                logger.log(f"プリセットの保存に失敗しました: {e}", level="ERROR")
        settings_manager.save_settings()

    app.aboutToQuit.connect(save_settings_on_exit)
    app.aboutToQuit.connect(lambda: clear_numba_cache_on_exit(settings_manager))

    # --- アプリケーションの実行 ---
    main_window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
