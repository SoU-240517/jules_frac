import sys
import os

# スクリプトが直接実行された場合にsys.pathを調整し、
# プロジェクトルート (jules_frac) からの絶対インポートを可能にします。
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # .../jules_frac/views
    PARENT_DIR = os.path.dirname(SCRIPT_DIR)  # .../jules_frac
    if PARENT_DIR not in sys.path:
        sys.path.insert(0, PARENT_DIR)

from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtGui import QImage, QPixmap, QCursor
from PyQt6.QtCore import Qt, QPointF
import numpy as np
from PIL import Image, ImageQt
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class RenderArea(QLabel):
    """
    フラクタル画像を表示し、ユーザーインタラクション (パン、ズーム) を処理するウィジェット。

    QLabel を継承し、NumPy 配列として提供される画像データを表示します。
    マウスイベントを処理して、フラクタルコントローラーを介した画像のナビゲーションを可能にします。
    """
    def __init__(self, parent=None, fractal_controller=None):
        """
        RenderArea を初期化します。

        Args:
            parent (QWidget, optional): 親ウィジェット。 Defaults to None.
            fractal_controller (FractalController, optional): フラクタル計算とナビゲーションを処理するコントローラー。 Defaults to None.
        """
        super().__init__(parent)
        self.fractal_controller = fractal_controller

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._original_pixmap = None
        self.set_default_background()

        self.panning = False
        self.last_mouse_pos = None
        self.setMouseTracking(True)

    def set_default_background(self):
        """
        画像がロードされていない場合に表示されるデフォルトの背景テキストとスタイルを設定します。
        """
        self.setText("フラクタル画像がここに表示されます。\nパラメータを設定し描画処理を開始してください。")
        self.setStyleSheet("background-color: #333333; color: #AAAAAA; border: 1px solid #454545; padding: 10px;")
        self.setWordWrap(True)

    def update_image(self, image_data_np):
        """
        表示する画像を NumPy 配列から更新します。

        Args:
            image_data_np (np.ndarray | None): RGBA 形式 (高さ x 幅 x 4) の画像データ。
                                               None または空のデータの場合、デフォルトの背景が表示されます。
        """
        if image_data_np is None or image_data_np.size == 0:
            # print("RenderArea: 画像データを受信しませんでした。デフォルトの背景を表示します。")
            # 画像データが受信されなかった場合はデフォルト背景を表示
            self.set_default_background()
            self._original_pixmap = None
            self.clear()
            return

        try:
            height, width, channels = image_data_np.shape
            if channels != 4:
                # print(f"RenderArea: 4チャンネル(RGBA)を期待しましたが、{channels}チャンネルでした。")
                # RGBAの4チャンネルでない場合はデフォルト背景を表示
                self.set_default_background()
                self._original_pixmap = None
                self.clear()
                return
            if width == 0 or height == 0:
                # print(f"RenderArea: 無効な画像サイズ ({width}x{height})。")
                # 幅または高さが0の場合はデフォルト背景を表示
                self.set_default_background()
                self._original_pixmap = None
                self.clear()
                return

            pil_image = Image.fromarray(image_data_np, 'RGBA')
            qimage = ImageQt.ImageQt(pil_image)
            self._original_pixmap = QPixmap.fromImage(qimage)
            self._display_scaled_pixmap()
            # print(f"RenderArea: 画像更新 ({width}x{height})。表示サイズ: {self.width()}x{self.height()}")
            # 画像が更新された際のデバッグメッセージ
        except Exception as e:
            logger.log(f"画像更新中にエラーが発生しました - {e}", level="ERROR")
            self.set_default_background()
            self._original_pixmap = None
            self.clear()

    def _display_scaled_pixmap(self):
        """
        現在の `_original_pixmap` をウィジェットのサイズに合わせてスケーリングし、表示します。
        アスペクト比は維持されます。
        """
        if self._original_pixmap and not self._original_pixmap.isNull():
            scaled_pixmap = self._original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            self.setStyleSheet("")
        else:
            self.set_default_background()

    def resizeEvent(self, event):
        """
        ウィジェットがリサイズされたときに呼び出されます。
        表示されている画像を新しいサイズに合わせて再スケーリングします。

        Args:
            event (QResizeEvent): リサイズイベントオブジェクト。
        """
        super().resizeEvent(event)
        if self._original_pixmap and not self._original_pixmap.isNull():
            self._display_scaled_pixmap()

    def mousePressEvent(self, event):
        """
        マウスボタンが押されたときに呼び出されます。左ボタンでパン操作を開始します。
        Args:
            event (QMouseEvent): マウスプレスイベントオブジェクト。
        """
        if event.button() == Qt.MouseButton.LeftButton and self.fractal_controller:
            if self.pixmap() and not self.pixmap().isNull():
                self.panning = True
                self.last_mouse_pos = event.position()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                event.accept()
                return
        event.ignore()

    def mouseMoveEvent(self, event):
        """
        マウスが移動したときに呼び出されます。
        パン操作中は画像の中心を移動し、そうでない場合はカーソル形状を更新します。

        Args:
            event (QMouseEvent): マウスムーブイベントオブジェクト。
        """
        if self.panning and (event.buttons() & Qt.MouseButton.LeftButton) and self.fractal_controller:
            if self.last_mouse_pos is None:
                self.last_mouse_pos = event.position()
                event.ignore()
                return

            current_pos = event.position()
            delta_qpoint = current_pos - self.last_mouse_pos

            engine_params = self.fractal_controller.get_current_engine_parameters()
            if not engine_params or self.width() == 0 or self.height() == 0:
                event.ignore()
                return

            fractal_width_complex = engine_params['width']
            fractal_height_complex = engine_params.get('height',
                                                      fractal_width_complex * self.height() / self.width() if self.width() > 0 else 0)
            if fractal_height_complex == 0:
                event.ignore()
                return

            delta_real = (delta_qpoint.x() / self.width()) * fractal_width_complex
            delta_imag = (-delta_qpoint.y() / self.height()) * fractal_height_complex

            self.fractal_controller.pan_fractal(delta_real, delta_imag)

            self.last_mouse_pos = current_pos
            event.accept()
        elif not self.panning:
            if self.pixmap() and not self.pixmap().isNull() and self.fractal_controller:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            event.ignore()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """
        マウスボタンが離されたときに呼び出されます。
        左ボタンが離された場合、パン操作を終了します。

        Args:
            event (QMouseEvent): マウスリリースイベントオブジェクト。
        """
        if event.button() == Qt.MouseButton.LeftButton and self.panning:
            self.panning = False
            if self.pixmap() and not self.pixmap().isNull() and self.fractal_controller:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            event.accept()
        else:
            event.ignore()

    def wheelEvent(self, event):
        """
        マウスホイールが回転したときに呼び出されます。
        画像のズームイン・ズームアウトを行います。ズームの中心はマウスカーソルの位置です。

        Args:
            event (QWheelEvent): ホイールイベントオブジェクト。
        """
        if not self.fractal_controller or (self.pixmap() and self.pixmap().isNull()):
            event.ignore()
            return

        delta_angle = event.angleDelta().y()
        if delta_angle == 0:
            event.ignore()
            return

        # マウスホイールの標準ステップは120単位（15度）
        num_steps = delta_angle / 120.0

        zoom_factor_per_std_step = 1.2 # 標準ホイールステップごとに20%ズーム

        effective_zoom_factor = zoom_factor_per_std_step ** num_steps

        current_params = self.fractal_controller.get_current_engine_parameters()
        if not current_params:
            event.ignore()
            return

        current_width = current_params['width']
        current_height = current_params['height']
        current_center_real = current_params['center_real']
        current_center_imag = current_params['center_imag']

        new_width = current_width / effective_zoom_factor

        mouse_pos_pixel = event.position() # QPointF, このウィジェット内での位置

        if self.width() == 0 or self.height() == 0: # ウィジェットのサイズが0の場合は除外
            event.ignore()
            return

        mouse_x_frac = mouse_pos_pixel.x() / self.width()
        mouse_y_frac = mouse_pos_pixel.y() / self.height()

        # マウス位置のフラクタル座標
        mouse_real_coord = (current_center_real - current_width / 2.0) + (mouse_x_frac * current_width)
        # フラクタルの虚数軸は画面Yと逆向きの場合が多い
        mouse_imag_coord = (current_center_imag + current_height / 2.0) - (mouse_y_frac * current_height)

        # コントローラのズーム処理を呼び出し
        self.fractal_controller.zoom_fractal_to_point(
            mouse_real_coord,
            mouse_imag_coord,
            mouse_x_frac,
            mouse_y_frac,
            new_width
        )
        event.accept()


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from PyQt6.QtCore import QObject, pyqtSignal # MockControllerテスト用に追加

    class MockController(QObject):
        parameters_updated_externally = pyqtSignal()

        def __init__(self):
            super().__init__()
            self._params = {"center_real": -0.5, "center_imag": 0.0, "width": 3.0, "max_iterations": 100}
            # テスト用に一般的なアスペクト比で高さを近似
            self._params["height"] = self._params["width"] * (0.75)
            self.image_width_px = 800 # コントローラ内でのアスペクト計算用のダミー画像幅
            self.image_height_px = 600 # ダミー画像高さ

        def get_current_engine_parameters(self):
            return self._params.copy()

        def pan_fractal(self, dr, di):
            self._params["center_real"] -= dr
            self._params["center_imag"] -= di
            logger.log(f"MockController: パン。新しい中心: ({self._params['center_real']:.4f}, {self._params['center_imag']:.4f})", level="DEBUG")
            self.parameters_updated_externally.emit()

        def zoom_fractal_to_point(self, fixed_r, fixed_i, frac_x, frac_y, new_w):
            # モック用の簡易ズーム処理（本来のロジックは実コントローラ側）
            old_w = self._params["width"]
            aspect = self.image_height_px / self.image_width_px
            new_h = new_w * aspect

            self._params["center_real"] = fixed_r - (frac_x - 0.5) * new_w
            self._params["center_imag"] = fixed_i + (frac_y - 0.5) * new_h
            self._params["width"] = new_w
            self._params["height"] = new_h # 高さも更新
            logger.log(f"MockController: ズーム。新しい幅: {new_w:.4e} 新しい中心: ({self._params['center_real']:.4f}, {self._params['center_imag']:.4f})", level="DEBUG")
            self.parameters_updated_externally.emit()

        def trigger_render(self, w, h):
             logger.log(f"MockController: trigger_renderが呼ばれました（{w}x{h}）", level="DEBUG")

    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("RenderArea ホイールズームテスト")
    main_win.resize(400, 300)

    mock_ctrl = MockController()
    render_area = RenderArea(main_win, fractal_controller=mock_ctrl)
    main_win.setCentralWidget(render_area)
    main_win.show()

    def create_dummy_image_data(width, height, r_seed=0, g_seed=128, b_seed=255):
        img_data = np.zeros((height, width, 4), dtype=np.uint8)
        for y_coord in range(height):
            for x_coord in range(width):
                img_data[y_coord, x_coord, 0] = int(x_coord * 255 / width + r_seed) % 256
                img_data[y_coord, x_coord, 1] = int(y_coord * 255 / height + g_seed) % 256
                img_data[y_coord, x_coord, 2] = int((x_coord + y_coord) * 255 / (width + height) + b_seed) % 256
                img_data[y_coord, x_coord, 3] = 255
        return img_data

    dummy_data = create_dummy_image_data(320, 240)
    render_area.update_image(dummy_data)

    logger.log("\nRenderArea ホイールズームテスト: 画像上でマウスホイールを回してください。", level="INFO")
    logger.log("モックコントローラが新しい幅と中心座標を出力します。", level="INFO")

    sys.exit(app.exec())
