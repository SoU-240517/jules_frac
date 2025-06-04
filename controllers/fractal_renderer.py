# coding: utf-8
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from models.fractal_engine import FractalEngine  # For type hinting
import time
import numpy as np # NumPy をインポート
from logger.custom_logger import CustomLogger


class FractalRendererSignals(QObject):
    rendering_started = pyqtSignal()
    rendering_finished = pyqtSignal(object, float, float)  # Rendered image data, computation time, coloring time
    rendering_failed = pyqtSignal(str)  # Error message

    def __init__(self, parent=None):
        super().__init__(parent)


class FractalRenderer(QRunnable):
    def __init__(self, fractal_engine: FractalEngine, image_width_px: int, image_height_px: int, full_recompute: bool, active_coloring_target_type: str):
        super().__init__()
        self.fractal_engine = fractal_engine
        self.image_width_px = image_width_px
        self.image_height_px = image_height_px
        self.full_recompute = full_recompute
        self.active_coloring_target_type = active_coloring_target_type # Store this
        self.signals = FractalRendererSignals()
        self.logger = CustomLogger()

    def run(self):
        self.signals.rendering_started.emit()
        self.logger.log("FractalRenderer: Rendering started.", level="DEBUG")

        try:
            self.fractal_engine.image_width_px = self.image_width_px
            self.fractal_engine.image_height_px = self.image_height_px
            self.fractal_engine.update_aspect_ratio()

            compute_time_ms = 0.0
            start_t = time.perf_counter()
            # FractalEngine.compute_current_fractal は full_recompute 引数を取らないと仮定
            # エンジン側でキャッシュ管理を行うか、常に再計算するとする
            # ここでは、self.full_recompute を使ってキャッシュの有無を条件分岐するロジックは削除
            fractal_data = self.fractal_engine.compute_current_fractal()
            compute_time_ms = (time.perf_counter() - start_t) * 1000

            if fractal_data is None:
                self.logger.log("FractalRenderer: Computation failed or returned None.", level="ERROR")
                self.signals.rendering_failed.emit("計算失敗 (データなし)")
                return

            is_diverged_mask = fractal_data.get('is_diverged')
            if is_diverged_mask is None:
                self.logger.log("FractalRenderer: 'is_diverged' mask not found in fractal_data.", level="ERROR")
                # エラー処理: 例えば、全域を発散していない（またはしている）として扱うか、エラー画像を出す
                # ここでは、全域を非発散として扱い、単一のカラーリングを試みる（またはエラーにする）
                # より堅牢なのはエラー画像を返すことかもしれない
                self.signals.rendering_failed.emit("計算データエラー (is_divergedマスクなし)")
                return

            if not isinstance(is_diverged_mask, np.ndarray):
                self.logger.log(f"FractalRenderer: 'is_diverged' mask is not a NumPy array. Type: {type(is_diverged_mask)}", level="ERROR")
                self.signals.rendering_failed.emit("計算データ型エラー (is_divergedマスク不正)")
                return

            coloring_time_start = time.perf_counter()

            colored_image_divergent = self.fractal_engine.apply_coloring(
                target_type='divergent', fractal_data_override=fractal_data
            )
            colored_image_non_divergent = self.fractal_engine.apply_coloring(
                target_type='non_divergent', fractal_data_override=fractal_data
            )

            coloring_time_ms = (time.perf_counter() - coloring_time_start) * 1000

            if colored_image_divergent is None or colored_image_non_divergent is None:
                self.logger.log("FractalRenderer: One or both coloring results are None.", level="ERROR")
                # エラー処理: 片方だけでもあればそれを使うか、エラー画像を出す
                # ここではエラーとする
                self.signals.rendering_failed.emit("カラーリング失敗 (片方または両方の結果がNone)")
                return

            # Ensure images are RGBA before combining, if they are not already
            # Assuming apply_coloring returns HxWx4 (RGBA)
            if colored_image_divergent.shape[-1] != 4 or colored_image_non_divergent.shape[-1] != 4:
                self.logger.log("FractalRenderer: Coloring results are not RGBA.", level="ERROR")
                self.signals.rendering_failed.emit("カラーリング結果フォーマットエラー")
                return

            # is_diverged_mask の形状をRGBA画像に合わせる (H, W) -> (H, W, 1)
            # これにより、(H,W,1) と (H,W,4) の間でブロードキャストが可能になる
            is_diverged_mask_rgba = is_diverged_mask[..., np.newaxis]

            final_image = np.where(
                is_diverged_mask_rgba,
                colored_image_divergent,
                colored_image_non_divergent
            )

            self.logger.log(f"FractalRenderer: Rendering finished. Compute: {compute_time_ms:.1f}ms, Color: {coloring_time_ms:.1f}ms", level="INFO")
            try:
                self.signals.rendering_finished.emit(final_image.astype(np.uint8), compute_time_ms, coloring_time_ms)
            except RuntimeError as e_emit_finished:
                self.logger.log(f"FractalRenderer: Error emitting rendering_finished: {e_emit_finished}", level="ERROR")

        except Exception as e_outer:
            self.logger.log(f"FractalRenderer: Error during rendering: {e_outer}", level="ERROR", exc_info=True)
            try:
                self.signals.rendering_failed.emit(f"レンダリング中にエラーが発生しました: {e_outer}")
            except RuntimeError as e_emit_failed_outer:
                self.logger.log(f"FractalRenderer: Error emitting rendering_failed: {e_emit_failed_outer}", level="ERROR")
