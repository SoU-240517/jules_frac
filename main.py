import sys
from pathlib import Path # 設定用にパス操作を行うためのモジュール

# プロジェクトのルートディレクトリ（'src'の親）をsys.pathに追加
# これにより、'src' ディレクトリからの相対インポートや、'src.app...' のような絶対インポートが可能になる
_project_root = Path(__file__).resolve().parent # 'jules_frac' ディレクトリをプロジェクトルートとする
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PyQt6.QtWidgets import QApplication
from views.main_window import MainWindow
from models.fractal_engine import FractalEngine
from controllers.fractal_controller import FractalController
from utils.settings_manager import SettingsManager # SettingsManagerのインポート
from PyQt6.QtCore import Qt

if __name__ == '__main__':
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 設定マネージャーの初期化（ファイル名は任意）
    # アプリケーション名や組織名を使って標準的な場所に保存することも検討（QStandardPaths推奨）
    settings_file_name = "base_settings.json" # プロジェクトルートからの相対パス
    # テスト用に書き込み可能な場所（例：ユーザーのホームやアプリデータディレクトリ）に配置することを推奨
    # SettingsManager自体はユーザーのホーム/.fractalapp/に保存しようとする
    settings_file_path = _project_root / settings_file_name
    settings_manager = SettingsManager(settings_filename=str(settings_file_path))

    # モデル・コントローラーの作成
    # FractalEngineにプロジェクトルートパスを渡す
    fractal_engine = FractalEngine(project_root_path=_project_root)
    fractal_controller = FractalController(fractal_engine)

    # ダークテーマのスタイルシート（変更なし）
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
        QMenuBar::item::selected { /* ホバー時 */
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

    # MainWindowにSettingsManagerのインスタンスを渡す
    main_window = MainWindow(fractal_controller, settings_manager)
    fractal_controller.set_main_window(main_window)

    if hasattr(main_window, 'status_bar') and main_window.status_bar is not None: # status_barが存在するか確認
        fractal_controller.status_updated.connect(main_window.update_status_bar)
    else:
        print("警告: MainWindow.status_barが見つからない、または初期化されていないため、status_updatedシグナルを接続できません。")

    main_window.show()

    sys.exit(app.exec())
