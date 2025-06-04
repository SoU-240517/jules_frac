# coding: utf-8
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from models.fractal_engine import FractalEngine  # For type hinting
import time
from logger.custom_logger import CustomLogger


class FractalRendererSignals(QObject):
    rendering_started = pyqtSignal()
    rendering_finished = pyqtSignal(object, float, float)  # Rendered image data, computation time, coloring time
    rendering_failed = pyqtSignal(str)  # Error message

    def __init__(self, parent=None):
        super().__init__(parent)


class FractalRenderer(QRunnable):
    def __init__(self, fractal_engine: FractalEngine, image_width_px: int, image_height_px: int, full_recompute: bool):
        super().__init__()
        self.fractal_engine = fractal_engine
        self.image_width_px = image_width_px
        self.image_height_px = image_height_px
        self.full_recompute = full_recompute
        self.signals = FractalRendererSignals()
        self.logger = CustomLogger()

    def run(self):
        self.signals.rendering_started.emit()
        self.logger.log("FractalRenderer: Rendering started.", level="DEBUG")

        try:
            self.fractal_engine.image_width_px = self.image_width_px
            self.fractal_engine.image_height_px = self.image_height_px
            self.fractal_engine.update_aspect_ratio()

            fractal_data = None
            compute_time_ms = 0.0

            if self.full_recompute:
                start_t = time.perf_counter()
                fractal_data = self.fractal_engine.compute_current_fractal()
                compute_time_ms = (time.perf_counter() - start_t) * 1000
                if fractal_data is None:
                    self.logger.log("FractalRenderer: Computation failed.", level="ERROR")
                    self.signals.rendering_failed.emit("計算失敗")
                    return
            else:
                fractal_data = self.fractal_engine.last_fractal_data_cache
                if fractal_data is None:
                    self.logger.log("FractalRenderer: No cached data for recolor.", level="ERROR")
                    self.signals.rendering_failed.emit("再描画のためのキャッシュデータがありません")
                    return

            start_t_coloring = time.perf_counter()
            colored_image = self.fractal_engine.apply_coloring(fractal_data_override=fractal_data)
            coloring_time_ms = (time.perf_counter() - start_t_coloring) * 1000

            if colored_image is None:
                self.logger.log("FractalRenderer: Coloring failed.", level="ERROR")
                self.signals.rendering_failed.emit("カラーリング失敗")
                return

            self.logger.log(f"FractalRenderer: Rendering finished. Compute: {compute_time_ms:.1f}ms, Color: {coloring_time_ms:.1f}ms", level="INFO")
            try:
                self.signals.rendering_finished.emit(colored_image, compute_time_ms, coloring_time_ms)
            except RuntimeError as e_emit_finished:
                self.logger.log(f"FractalRenderer: Error emitting rendering_finished: {e_emit_finished}", level="ERROR")

        except Exception as e_outer:
            self.logger.log(f"FractalRenderer: Error during rendering: {e_outer}", level="ERROR", exc_info=True)
            try:
                self.signals.rendering_failed.emit(f"レンダリング中にエラーが発生しました: {e_outer}")
            except RuntimeError as e_emit_failed_outer:
                self.logger.log(f"FractalRenderer: Error emitting rendering_failed: {e_emit_failed_outer}", level="ERROR")
