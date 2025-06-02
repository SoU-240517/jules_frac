from PyQt6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class ParameterPanel(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)

        self.content_widget = QWidget()
        self.setWidget(self.content_widget)

        self.layout = QVBoxLayout(self.content_widget)
        self.content_widget.setLayout(self.layout)

        # Add placeholder labels
        title_label = QLabel("パラメータパネル")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        self.layout.addWidget(title_label)

        fractal_selection_label = QLabel("フラクタル選択:")
        self.layout.addWidget(fractal_selection_label)
        # Placeholder for fractal selection dropdown/radio buttons

        common_params_label = QLabel("共通パラメータ:")
        self.layout.addWidget(common_params_label)
        # Placeholder for common parameters like iterations, zoom, etc.

        self.layout.addStretch() # Add stretch at the bottom to push content to the top

if __name__ == '__main__':
    # This part is for testing the ParameterPanel independently.
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    param_panel = ParameterPanel()
    param_panel.setMinimumSize(300, 600) # Set a minimum size for standalone testing
    param_panel.show()
    sys.exit(app.exec())
