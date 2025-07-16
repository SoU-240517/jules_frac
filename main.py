import sys
import json
import shutil
from pathlib import Path
import numba
from typing import Tuple

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from views.main_window import MainWindow
from models.fractal_engine import FractalEngine
from controllers.fractal_controller import FractalController
from settings_manager import SettingsManager
from logger.custom_logger import CustomLogger
from views.colormap_editor.utils import get_project_root, to_relpath, log_exceptions
# Numbaユーティリティのインポート
from utils.numba_utils import clear_numba_cache_on_exit

# プロジェクトのルートディレクトリを取得
_project_root = get_project_root()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# --- 定数定義 ---
SETTINGS_FILE_NAME = "settings.jsonc"
DEFAULT_STYLESHEET_PATH = "views/style.qss" # デフォルトのスタイルシートパス


def get_logger(project_root: Path) -> CustomLogger:
    """
    CustomLoggerのインスタンスを初期化し、プロジェクトルートを設定して返します。

    Args:
        project_root (Path): プロジェクトのルートディレクトリのパス

    Returns:
        CustomLogger: 初期化済みのロガーインスタンス
    """
    logger = CustomLogger()
    logger.set_project_root(project_root)
    return logger

logger = get_logger(_project_root)


def setup_application() -> QApplication:
    """
    QApplicationインスタンスを作成し、High DPI対応の設定を適用します。
    これにより、画面の高解像度環境でもUIが綺麗に表示されます。

    Returns:
        QApplication: アプリケーションインスタンス
    """
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    return QApplication(sys.argv)


def apply_stylesheet(app: QApplication, path: str) -> None:
    """
    指定したパスのスタイルシート（QSSファイル）を読み込み、アプリケーション全体に適用します。
    ファイルが存在しない場合や読み込みエラー時はロギングします。

    Args:
        app (QApplication): スタイルを適用するアプリケーションインスタンス
        path (str): スタイルシートファイルのパス
    """
    stylesheet_path = Path(path)
    if stylesheet_path.exists():
        try:
            with open(stylesheet_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.log(f"スタイルシートを適用しました: {to_relpath(stylesheet_path)}", level="INFO")
        except Exception as e:
            logger.log(f"スタイルシートの読み込みまたは適用中にエラーが発生しました: {e}", level="ERROR")
    else:
        logger.log(f"スタイルシートファイルが見つかりません: {to_relpath(stylesheet_path)}", level="WARNING")


def setup_logging(settings_manager: SettingsManager, logger_instance: CustomLogger) -> None:
    """
    設定ファイルからロギング設定（レベル・有効/無効）を取得し、ロガーに適用します。

    Args:
        settings_manager (SettingsManager): 設定管理インスタンス
        logger_instance (CustomLogger): 設定を適用するロガー
    """
    log_config = settings_manager.get_setting("app_settings.logging", {"level": "INFO", "enabled": True})
    log_level = log_config.get("level", "INFO")
    log_enabled = log_config.get("enabled", True)

    logger_instance.set_level(log_level)
    logger_instance.set_enabled(log_enabled)
    logger_instance.log(f"ロガー設定適用 [レベル: {log_level}, 有効: {log_enabled}]", level="DEBUG")


def get_settings_manager() -> SettingsManager:
    """
    SettingsManagerを初期化して返します。
    設定ファイルのパスはプロジェクトルート直下のsettings.jsoncです。

    Returns:
        SettingsManager: 設定管理インスタンス
    """
    settings_file_path = _project_root / SETTINGS_FILE_NAME
    return SettingsManager(settings_filename=str(settings_file_path))


def get_stylesheet_path(settings_manager: SettingsManager) -> Path:
    """
    設定ファイルからスタイルシートのパスを取得します。
    設定がなければデフォルトのパスを返します。

    Args:
        settings_manager (SettingsManager): 設定管理インスタンス
    Returns:
        Path: スタイルシートファイルのパス
    """
    app_config = settings_manager.get_setting("app_settings", {})
    return _project_root / app_config.get("stylesheet_path", DEFAULT_STYLESHEET_PATH)


def init_mvc_components(settings_manager: SettingsManager) -> Tuple[FractalEngine, FractalController, MainWindow]:
    """
    フラクタルエンジン・コントローラ・メインウィンドウの各MVCコンポーネントを初期化し、返します。

    Args:
        settings_manager (SettingsManager): 設定管理インスタンス
    Returns:
        Tuple[FractalEngine, FractalController, MainWindow]: 初期化済みの各コンポーネント
    """
    fractal_engine = FractalEngine(project_root_path=_project_root, settings_manager=settings_manager)
    fractal_controller = FractalController(fractal_engine, settings_manager)
    fractal_controller.apply_configuration_from_settings()
    main_window = MainWindow(fractal_controller, settings_manager)
    fractal_controller.set_main_window(main_window)
    return fractal_engine, fractal_controller, main_window


def connect_signals(fractal_controller: FractalController, main_window: MainWindow) -> None:
    """
    コントローラとメインウィンドウの間で、状態更新のシグナルとスロットを接続します。
    ステータスバーが存在しない場合は警告をロギングします。

    Args:
        fractal_controller (FractalController): フラクタルコントローラ
        main_window (MainWindow): メインウィンドウ
    """
    if hasattr(main_window, 'status_bar') and main_window.status_bar is not None:
        fractal_controller.status_updated.connect(main_window.update_status_bar)
    else:
        logger.log("警告: MainWindow.status_barが見つからないため、status_updatedシグナルを接続できません。", level="WARNING")


def register_exit_handlers(app: QApplication, settings_manager: SettingsManager, fractal_controller: FractalController) -> None:
    """
    アプリケーション終了時に設定保存やNumbaキャッシュクリアなどの後処理を登録します。

    Args:
        app (QApplication): アプリケーションインスタンス
        settings_manager (SettingsManager): 設定管理インスタンス
        fractal_controller (FractalController): フラクタルコントローラ
    """
    def save_settings_on_exit() -> None:
        """
        アプリケーション終了時に全ての設定をsettings.jsoncに保存します。
        エンジン設定・プリセットなどを最新状態で保存します。
        """
        logger.log("終了処理を開始します。全ての設定を保存します...", level="INFO")
        engine_config = fractal_controller.get_full_configuration()
        settings_manager.set_setting("engine_settings", engine_config, auto_save=False)
        current_presets = settings_manager.get_setting("presets", {})
        settings_manager.set_setting("presets", current_presets, auto_save=False)
        settings_manager.save_settings()
    app.aboutToQuit.connect(save_settings_on_exit)
    app.aboutToQuit.connect(lambda: clear_numba_cache_on_exit(settings_manager, logger))


def configure_numba(settings_manager: SettingsManager) -> None:
    """
    Numbaのキャッシュ設定を設定ファイルから取得し、Numbaに適用します。

    Args:
        settings_manager (SettingsManager): 設定管理インスタンス
    """
    numba_config = settings_manager.get_setting("app_settings.numba_settings", {"cache_enabled": True})
    numba.config.CACHE = numba_config.get("cache_enabled", True)
    logger.log(f"Numbaキャッシュ設定適用 [有効: {numba.config.CACHE}]", level="DEBUG")


@log_exceptions(logger)
def main():
    """
    アプリケーションのメインエントリーポイントです。
    各種初期化、設定の読み込み、MVC構成要素の生成、シグナル接続、終了時処理登録など、
    アプリ全体の起動処理をまとめて行います。

    プログラムの流れ：
      1. QApplicationの初期化（高DPI対応）
      2. 設定ファイルの読み込みとロガー設定
      3. Numbaキャッシュ設定の適用
      4. スタイルシートの適用
      5. MVCコンポーネント（エンジン・コントローラ・ウィンドウ）の生成
      6. シグナルとスロットの接続
      7. 終了時の後処理登録
      8. メインウィンドウの表示とアプリ実行
    """
    app = setup_application()
    settings_manager = get_settings_manager()
    setup_logging(settings_manager, logger)
    configure_numba(settings_manager)
    apply_stylesheet(app, get_stylesheet_path(settings_manager))
    fractal_engine, fractal_controller, main_window = init_mvc_components(settings_manager)
    connect_signals(fractal_controller, main_window)
    register_exit_handlers(app, settings_manager, fractal_controller)
    main_window.show()
    sys.exit(app.exec())

# --- エントリーポイント ---
if __name__ == '__main__':
    main()
