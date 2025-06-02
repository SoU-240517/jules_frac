import sys
from PyQt6.QtWidgets import QApplication
from src.app.views.main_window import MainWindow
from src.app.models.fractal_engine import FractalEngine
from src.app.controllers.fractal_controller import FractalController
from PyQt6.QtCore import Qt

if __name__ == '__main__':
    # 高DPI対応 (Qt5以降では多くの場合自動ですが、明示的に設定)
    # PyQt6ではAA_EnableHighDpiScalingはデフォルトで有効な場合が多い
    # AA_UseHighDpiPixmapsは高解像度のアイコンなどに影響
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # モデルとコントローラーの作成
    fractal_engine = FractalEngine()
    fractal_controller = FractalController(fractal_engine)

    # ダークテーマのスタイルシートを設定
    # (スタイルシートのコードは変更なしのため省略)
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
        /* QLabel specific styles should be carefully managed. */
        /* For instance, ParameterPanel's labels will inherit QWidget's color. */
        /* RenderArea has its own style, so it won't be affected by a global QLabel style here. */

        /* Style for QSplitter handle */
        QSplitter::handle {
            background-color: #3c3c3c;
            border: 1px solid #505050;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }
        QSplitter::handle:hover {
            background-color: #505050;
        }

        /* Ensure specific labels like those in ParameterPanel get the theme's text color */
        QLabel {
            color: #e0e0e0;
            /* background-color: transparent; /* This might be too broad if not careful */
        }
    """)

    main_window = MainWindow(fractal_controller) # MainWindowにコントローラを渡す
    fractal_controller.set_main_window(main_window) # ControllerにMainWindowをセット

    # MainWindowのステータスバー更新シグナルを接続
    fractal_controller.status_updated.connect(main_window.update_status_bar)

    main_window.show()

    # 初期描画をトリガー (オプション)
    # ウィンドウが表示されてRenderAreaのサイズが確定した後に呼び出すのが理想
    # main_window.request_initial_render()
    # または、表示直後に一度コントローラーからトリガーする (サイズはRenderAreaから取得を試みる)
    # QtCore.QTimer.singleShot(0, lambda: fractal_controller.trigger_render()) # 次のイベントサイクルで実行

    sys.exit(app.exec())
