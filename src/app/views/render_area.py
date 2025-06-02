from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtGui import QImage, QPixmap, QCursor
from PyQt6.QtCore import Qt, QPointF
import numpy as np
from PIL import Image, ImageQt

class RenderArea(QLabel):
    def __init__(self, parent=None, fractal_controller=None):
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
        self.setText("フラクタル画像がここに表示されます。\nパラメータを設定し描画処理を開始してください。")
        self.setStyleSheet("background-color: #333333; color: #AAAAAA; border: 1px solid #454545; padding: 10px;")
        self.setWordWrap(True)

    def update_image(self, image_data_np):
        if image_data_np is None or image_data_np.size == 0:
            # print("RenderArea: No image data received. Displaying default background.")
            self.set_default_background()
            self._original_pixmap = None
            self.clear()
            return

        try:
            height, width, channels = image_data_np.shape
            if channels != 4:
                # print(f"RenderArea: Expected 4 channels (RGBA), but got {channels}.")
                self.set_default_background()
                self._original_pixmap = None
                self.clear()
                return
            if width == 0 or height == 0:
                # print(f"RenderArea: Invalid image dimensions ({width}x{height}).")
                self.set_default_background()
                self._original_pixmap = None
                self.clear()
                return

            pil_image = Image.fromarray(image_data_np, 'RGBA')
            qimage = ImageQt.ImageQt(pil_image)
            self._original_pixmap = QPixmap.fromImage(qimage)
            self._display_scaled_pixmap()
            # print(f"RenderArea: Image updated ({width}x{height}). Display size: {self.width()}x{self.height()}")
        except Exception as e:
            print(f"RenderArea: Error updating image - {e}")
            self.set_default_background()
            self._original_pixmap = None
            self.clear()

    def _display_scaled_pixmap(self):
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
        super().resizeEvent(event)
        if self._original_pixmap and not self._original_pixmap.isNull():
            self._display_scaled_pixmap()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.fractal_controller:
            if self.pixmap() and not self.pixmap().isNull():
                self.panning = True
                self.last_mouse_pos = event.position()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                event.accept()
                return
        event.ignore()

    def mouseMoveEvent(self, event):
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
        if not self.fractal_controller or (self.pixmap() and self.pixmap().isNull()):
            event.ignore()
            return

        delta_angle = event.angleDelta().y()
        if delta_angle == 0:
            event.ignore()
            return

        # Standard step for wheel is 120 units for 15 degrees
        num_steps = delta_angle / 120.0

        zoom_factor_per_std_step = 1.2 # Zoom 20% per standard wheel step (120 units)

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

        mouse_pos_pixel = event.position() # QPointF, position relative to this widget

        if self.width() == 0 or self.height() == 0: # Prevent division by zero if widget not sized
            event.ignore()
            return

        mouse_x_frac = mouse_pos_pixel.x() / self.width()
        mouse_y_frac = mouse_pos_pixel.y() / self.height()

        # Fractal coordinates of the mouse pointer
        mouse_real_coord = (current_center_real - current_width / 2.0) + (mouse_x_frac * current_width)
        # Y-axis for fractal imaginary part is often inverted relative to screen Y
        mouse_imag_coord = (current_center_imag + current_height / 2.0) - (mouse_y_frac * current_height)

        # Call controller method to handle zoom logic
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
    from PyQt6.QtCore import QObject, pyqtSignal # Added for MockController test

    class MockController(QObject):
        parameters_updated_externally = pyqtSignal()

        def __init__(self):
            super().__init__()
            self._params = {"center_real": -0.5, "center_imag": 0.0, "width": 3.0, "max_iterations": 100}
            # Approximate height based on a common aspect ratio for testing
            self._params["height"] = self._params["width"] * (0.75)
            self.image_width_px = 800 # Mock image pixel width for aspect calc in controller
            self.image_height_px = 600 # Mock image pixel height

        def get_current_engine_parameters(self):
            return self._params.copy()

        def pan_fractal(self, dr, di):
            self._params["center_real"] -= dr
            self._params["center_imag"] -= di
            print(f"MockController: Pan. New center: ({self._params['center_real']:.4f}, {self._params['center_imag']:.4f})")
            self.parameters_updated_externally.emit()

        def zoom_fractal_to_point(self, fixed_r, fixed_i, frac_x, frac_y, new_w):
            # Simplified zoom logic for mock - actual logic is in real controller
            old_w = self._params["width"]
            aspect = self.image_height_px / self.image_width_px
            new_h = new_w * aspect

            self._params["center_real"] = fixed_r - (frac_x - 0.5) * new_w
            self._params["center_imag"] = fixed_i + (frac_y - 0.5) * new_h
            self._params["width"] = new_w
            self._params["height"] = new_h # Update height as well
            print(f"MockController: Zoom. New width: {new_w:.4e}. New center: ({self._params['center_real']:.4f}, {self._params['center_imag']:.4f})")
            self.parameters_updated_externally.emit()

        def trigger_render(self, w, h):
             print(f"MockController: trigger_render called for {w}x{h}")

    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("RenderArea Wheel Zoom Test")
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

    print("\nRenderArea Wheel Zoom Test: Try scrolling the mouse wheel over the image.")
    print("The mock controller will print new width and center coordinates.")

    sys.exit(app.exec())
