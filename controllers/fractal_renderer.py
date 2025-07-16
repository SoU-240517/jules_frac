# coding: utf-8
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from models.fractal_engine import FractalEngine  # 型ヒント用
import time
import numpy as np # NumPy をインポート
from logger.custom_logger import CustomLogger
from typing import Any


class FractalRendererSignals(QObject):
    """
    FractalRendererからのシグナルを定義するクラスです。
    レンダリング処理の進行状況や結果、エラー発生時などを通知します。
    """
    rendering_started = pyqtSignal()  # レンダリング処理開始時に通知
    rendering_finished = pyqtSignal(object, float, float)  # レンダリング完了時（画像データ, 計算時間, カラーリング時間）
    rendering_failed = pyqtSignal(str)  # レンダリング失敗時（エラーメッセージ）

    def __init__(self, parent=None):
        """
        FractalRendererSignals を初期化します。

        Args:
            parent: 親QObject（省略可）
        """
        super().__init__(parent)


class FractalRenderer(QRunnable):
    """
    フラクタル画像のレンダリング処理を別スレッドで実行するクラスです。
    QRunnableを継承し、FractalEngineを用いてフラクタル計算・カラーリングを行い、
    結果をシグナルで通知します。
    """
    def __init__(self, fractal_engine: FractalEngine, image_width_px: int, image_height_px: int, full_recompute: bool, active_coloring_target_type: str):
        """
        FractalRenderer を初期化します。

        Args:
            fractal_engine (FractalEngine): フラクタル計算エンジン。
            image_width_px (int): レンダリングする画像の幅 (ピクセル単位)。
            image_height_px (int): レンダリングする画像の高さ (ピクセル単位)。
            full_recompute (bool): フラクタルデータを完全に再計算するかどうか。
            active_coloring_target_type (str): 現在アクティブなカラーリングターゲットタイプ（'divergent' または 'non_divergent'）。
        """
        super().__init__()
        self.fractal_engine = fractal_engine  # フラクタル計算エンジン
        self.image_width_px = image_width_px  # 画像幅（ピクセル）
        self.image_height_px = image_height_px  # 画像高さ（ピクセル）
        self.full_recompute = full_recompute  # 完全再計算フラグ
        self.active_coloring_target_type = active_coloring_target_type  # カラーリングターゲット
        self.signals = FractalRendererSignals()  # シグナル管理
        self.logger = CustomLogger()  # ロガー

    def run(self):
        """
        メインのレンダリング処理を実行します。
        フラクタル計算・カラーリングを行い、成功時は画像データと計算時間を通知、
        失敗時はエラーメッセージを通知します。
        """
        self.signals.rendering_started.emit()
        self.logger.log("レンダリング開始", level="INFO")

        try:
            # 画像サイズ・アスペクト比をエンジンに反映
            self.fractal_engine.image_width_px = self.image_width_px
            self.fractal_engine.image_height_px = self.image_height_px
            self.fractal_engine.update_aspect_ratio()

            compute_time_ms = 0.0
            start_t = time.perf_counter()
            # フラクタルデータ計算
            fractal_data = self.fractal_engine.compute_current_fractal()
            compute_time_ms = (time.perf_counter() - start_t) * 1000

            if fractal_data is None:
                self.logger.log("FractalRenderer: 計算に失敗したか、Noneが返されました。", level="ERROR")
                self.signals.rendering_failed.emit("計算失敗 (データなし)")
                return

            is_diverged_mask = fractal_data.get('is_diverged')
            if is_diverged_mask is None:
                self.logger.log("FractalRenderer: 'is_diverged' マスクがfractal_data内で見つかりません。", level="ERROR")
                self.signals.rendering_failed.emit("計算データエラー (is_divergedマスクなし)")
                return

            if not isinstance(is_diverged_mask, np.ndarray):
                self.logger.log(f"FractalRenderer: 'is_diverged' マスクがNumPy配列ではありません。型: {type(is_diverged_mask)}", level="ERROR")
                self.signals.rendering_failed.emit("計算データ型エラー (is_divergedマスク不正)")
                return

            coloring_time_start = time.perf_counter()

            # 発散・非発散領域ごとにカラーリング
            colored_image_divergent = self.fractal_engine.apply_coloring(
                target_type='divergent', fractal_data_override=fractal_data
            )
            colored_image_non_divergent = self.fractal_engine.apply_coloring(
                target_type='non_divergent', fractal_data_override=fractal_data
            )

            coloring_time_ms = (time.perf_counter() - coloring_time_start) * 1000

            if colored_image_divergent is None or colored_image_non_divergent is None:
                self.logger.log("FractalRenderer: 一方または両方のカラーリング結果がNoneです。", level="ERROR")
                self.signals.rendering_failed.emit("カラーリング失敗 (片方または両方の結果がNone)")
                return

            # RGBA画像であることを確認
            if colored_image_divergent.shape[-1] != 4 or colored_image_non_divergent.shape[-1] != 4:
                self.logger.log("FractalRenderer: カラーリング結果がRGBAではありません。", level="ERROR")
                self.signals.rendering_failed.emit("カラーリング結果フォーマットエラー")
                return

            # is_diverged_mask の形状をRGBA画像に合わせる (H, W) -> (H, W, 1)
            is_diverged_mask_rgba = is_diverged_mask[..., np.newaxis]

            # 発散領域・非発散領域を合成して最終画像を生成
            final_image = np.where(
                is_diverged_mask_rgba,
                colored_image_divergent,
                colored_image_non_divergent
            )

            self.logger.log(f"レンダリング完了。計算時間: {compute_time_ms:.1f}ms, 着色時間: {coloring_time_ms:.1f}ms", level="INFO")
            try:
                self.signals.rendering_finished.emit(final_image.astype(np.uint8), compute_time_ms, coloring_time_ms)
            except RuntimeError as e_emit_finished:
                self.logger.log(f"レンダリング完了の発行中にエラーが発生しました: {e_emit_finished}", level="ERROR")

        except Exception as e_outer:
            self.logger.log(f"レンダリング中にエラーが発生しました: {e_outer}", level="ERROR", exc_info=True)
            try:
                self.signals.rendering_failed.emit(f"レンダリング中にエラーが発生しました: {e_outer}")
            except RuntimeError as e_emit_failed_outer:
                self.logger.log(f"レンダリング失敗の発行中にエラーが発生しました: {e_emit_failed_outer}", level="ERROR")
