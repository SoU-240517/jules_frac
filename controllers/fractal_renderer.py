# coding: utf-8
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from models.fractal_engine import FractalEngine  # 型ヒント用
import time
import numpy as np # NumPy をインポート
from logger.custom_logger import CustomLogger


class FractalRendererSignals(QObject):
    """FractalRendererからのシグナルを定義するクラスです。"""
    rendering_started = pyqtSignal()
    rendering_finished = pyqtSignal(object, float, float)  # レンダリングされた画像データ、計算時間、カラーリング時間
    rendering_failed = pyqtSignal(str)  # エラーメッセージ

    def __init__(self, parent=None):
        """FractalRendererSignals を初期化します。"""
        super().__init__(parent)


class FractalRenderer(QRunnable):
    """フラクタル画像のレンダリング処理を別スレッドで実行するクラスです。QRunnableを継承しています。"""
    def __init__(self, fractal_engine: FractalEngine, image_width_px: int, image_height_px: int, full_recompute: bool, active_coloring_target_type: str):
        """FractalRenderer を初期化します。

        Args:
            fractal_engine (FractalEngine): フラクタル計算エンジン。
            image_width_px (int): レンダリングする画像の幅 (ピクセル単位)。
            image_height_px (int): レンダリングする画像の高さ (ピクセル単位)。
            full_recompute (bool): フラクタルデータを完全に再計算するかどうか。
            active_coloring_target_type (str): 現在アクティブなカラーリングターゲットタイプ ('divergent' または 'non_divergent')。
        """
        super().__init__()
        self.fractal_engine = fractal_engine
        self.image_width_px = image_width_px
        self.image_height_px = image_height_px
        self.full_recompute = full_recompute
        self.active_coloring_target_type = active_coloring_target_type # これを保存
        self.signals = FractalRendererSignals()
        self.logger = CustomLogger()

    def run(self):
        """メインのレンダリング処理を実行します。フラクタル計算、カラーリングを行い、結果のシグナルを発行します。"""
        self.signals.rendering_started.emit()
        self.logger.log("レンダリング開始", level="DEBUG")

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
                self.logger.log("FractalRenderer: 計算に失敗したか、Noneが返されました。", level="ERROR")
                self.signals.rendering_failed.emit("計算失敗 (データなし)")
                return

            is_diverged_mask = fractal_data.get('is_diverged')
            if is_diverged_mask is None:
                self.logger.log("FractalRenderer: 'is_diverged' マスクがfractal_data内で見つかりません。", level="ERROR")
                # エラー処理: 例えば、全域を発散していない（またはしている）として扱うか、エラー画像を出す
                # ここでは、全域を非発散として扱い、単一のカラーリングを試みる（またはエラーにする）
                # より堅牢なのはエラー画像を返すことかもしれない
                self.signals.rendering_failed.emit("計算データエラー (is_divergedマスクなし)")
                return

            if not isinstance(is_diverged_mask, np.ndarray):
                self.logger.log(f"FractalRenderer: 'is_diverged' マスクがNumPy配列ではありません。型: {type(is_diverged_mask)}", level="ERROR")
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
                self.logger.log("FractalRenderer: 一方または両方のカラーリング結果がNoneです。", level="ERROR")
                # エラー処理: 片方だけでもあればそれを使うか、エラー画像を出す
                # ここではエラーとする
                self.signals.rendering_failed.emit("カラーリング失敗 (片方または両方の結果がNone)")
                return

            # 結合前に画像がRGBAであることを確認します（まだの場合）
            # apply_coloring が HxWx4 (RGBA) を返すと仮定
            if colored_image_divergent.shape[-1] != 4 or colored_image_non_divergent.shape[-1] != 4:
                self.logger.log("FractalRenderer: カラーリング結果がRGBAではありません。", level="ERROR")
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
