import sys
from pathlib import Path # For path manipulation if needed for settings

# Add the project root directory (parent of 'src') to sys.path
# This allows 'from src.app...' imports when running main.py directly
# from within the src/ directory.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PyQt6.QtWidgets import QApplication
from src.app.views.main_window import MainWindow
from src.app.models.fractal_engine import FractalEngine
from src.app.controllers.fractal_controller import FractalController
from src.app.utils.settings_manager import SettingsManager # Import SettingsManager
from PyQt6.QtCore import Qt

if __name__ == '__main__':
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 設定マネージャーの初期化 (ファイル名は任意)
    # アプリケーション名や組織名を使って標準的な場所に保存することも検討 (QStandardPaths)
    settings_file_name = "base_settings.json"
    # For testing, ensure it's in a writable location, e.g., user's home or app data dir
    # The SettingsManager itself now tries to save in user's home/.fractalapp/
    settings_file_path = _project_root / settings_file_name
    settings_manager = SettingsManager(settings_filename=str(settings_file_path))

    # モデル、コントローラーの作成
    # FractalEngineのコンストラクタで各プラグインフォルダのデフォルトパスが使われる
    fractal_engine = FractalEngine()
    fractal_controller = FractalController(fractal_engine)

    # ダークテーマのスタイルシート (変更なし)
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
        QMenuBar::item {
            background-color: #3c3c3c;
            color: #e0e0e0;
        }
        QMenuBar::item::selected { /* hover */
            background-color: #505050;
        }
        QMenuBar::item::pressed { /* click */
            background-color: #555555;
        }
        QMenu {
            background-color: #3c3c3c;
            border: 1px solid #505050;
            color: #e0e0e0;
        }
        QMenu::item::selected {
            background-color: #505050;
            color: #ffffff;
        }
        QPushButton {
            background-color: #505050;
            border: 1px solid #606060;
            padding: 5px;
            min-width: 70px;
        }
        QPushButton:hover {
            background-color: #606060;
        }
        QPushButton:pressed {
            background-color: #404040;
        }
        QScrollArea {
            border: 1px solid #3c3c3c;
        }
        QLabel {
            color: #e0e0e0;
        }
        QSplitter::handle {
            background-color: #3c3c3c;
            border: 1px solid #505050;
        }
        QSplitter::handle:horizontal { width: 2px; }
        QSplitter::handle:vertical { height: 2px; }
        QSplitter::handle:hover { background-color: #505050; }
    """)

    # MainWindowに SettingsManager のインスタンスを渡す
    main_window = MainWindow(fractal_controller, settings_manager)
    fractal_controller.set_main_window(main_window)

    if hasattr(main_window, 'status_bar') and main_window.status_bar is not None: # Ensure status_bar exists
        fractal_controller.status_updated.connect(main_window.update_status_bar)
    else:
        print("Warning: MainWindow.status_bar not found or not initialized, cannot connect status_updated signal.")


    main_window.show()

    sys.exit(app.exec())
