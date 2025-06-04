# coding: utf-8
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QStatusBar
from logger.custom_logger import CustomLogger


class StatusBarAnimator(QObject):
    """
    QStatusBar にシンプルなテキストベースのアニメーション（例: "処理中..."）を表示するクラス。

    アニメーションの開始、停止、およびアニメーションが停止したことを通知するシグナルを提供します。
    """
    animation_stopped = pyqtSignal()
    """アニメーションが stop_animation() によって停止されたときに発行されるシグナル。"""

    def __init__(self, status_bar: QStatusBar, parent=None):
        """
        StatusBarAnimator を初期化します。

        Args:
            status_bar (QStatusBar): アニメーションを表示する対象のステータスバー。
            parent (QObject, optional): 親オブジェクト。 Defaults to None.
        """
        super().__init__(parent)
        self.status_bar = status_bar
        self.logger = CustomLogger()
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_interval_ms = 300  # ドット更新間隔
        self.base_message = "描画処理中"
        self.num_dots = 0
        self.max_dots = 10
        self.is_running = False

    def _update_animation(self):
        """
        アニメーションの各フレームを更新します。
        ベースメッセージに続くドットの数を増やし、ステータスバーに表示します。
        """
        self.num_dots = (self.num_dots + 1) % (self.max_dots + 1)
        dots = "." * self.num_dots
        self.status_bar.showMessage(f"{self.base_message}{dots}")

    def start_animation(self):
        """ステータスバーでのアニメーションを開始します。既に実行中の場合は何もしません。"""
        if self.is_running:
            return
        self.logger.log("StatusBarAnimator: アニメーションを開始します。", level="DEBUG")
        self.num_dots = 0
        self.status_bar.showMessage(self.base_message)  # 初期メッセージ
        self.animation_timer.start(self.animation_interval_ms)
        self.is_running = True

    def stop_animation(self, final_message: str = None):
        """
        ステータスバーでのアニメーションを停止します。

        Args:
            final_message (str, optional): アニメーション停止後に表示する最終メッセージ。
                                           None の場合、メッセージは変更されません（またはクリアされます）。
        """
        if not self.is_running:
            return
        self.logger.log(f"StatusBarAnimator: アニメーションを停止します。最終メッセージ: '{final_message}'", level="DEBUG")
        self.animation_timer.stop()
        if final_message is not None:
            self.status_bar.showMessage(final_message)
        else:
            # オプション: アニメーション停止時にメッセージをクリアするか、以前のメッセージを復元します。
            # この要件では、レンダリング完了メッセージが表示されるため、
            # ここでは何もしないか、self.status_bar.clearMessage() を使用します。必要に応じて調整してください。
            pass # MainWindow が最終メッセージを設定します
        self.is_running = False
        self.animation_stopped.emit()
