# coding: utf-8
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QStatusBar  # For type hinting
from logger.custom_logger import CustomLogger


class StatusBarAnimator(QObject):
    animation_stopped = pyqtSignal()

    def __init__(self, status_bar: QStatusBar, parent=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.logger = CustomLogger()
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_interval_ms = 300  # Dot update interval
        self.base_message = "描画処理中"
        self.num_dots = 0
        self.max_dots = 10
        self.is_running = False

    def _update_animation(self):
        self.num_dots = (self.num_dots + 1) % (self.max_dots + 1)
        dots = "." * self.num_dots
        self.status_bar.showMessage(f"{self.base_message}{dots}")

    def start_animation(self):
        if self.is_running:
            return
        self.logger.log("StatusBarAnimator: Starting animation.", level="DEBUG")
        self.num_dots = 0
        self.status_bar.showMessage(self.base_message)  # Initial message
        self.animation_timer.start(self.animation_interval_ms)
        self.is_running = True

    def stop_animation(self, final_message: str = None):
        if not self.is_running:
            return
        self.logger.log(f"StatusBarAnimator: Stopping animation. Final message: '{final_message}'", level="DEBUG")
        self.animation_timer.stop()
        if final_message is not None:
            self.status_bar.showMessage(final_message)
        else:
            # Optional: Clear message on animation stop or restore previous message
            # For this requirement, the rendering finished message will be displayed,
            # so do nothing here or use self.status_bar.clearMessage(). Adjust as needed.
            pass # MainWindow will set the final message
        self.is_running = False
        self.animation_stopped.emit()
