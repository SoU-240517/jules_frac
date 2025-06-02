from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

class RenderArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Render Area")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #333333; color: #FFFFFF;") # Dark gray background, white text
        # Further customization for border, etc., can be added here if needed.

if __name__ == '__main__':
    # This part is for testing the RenderArea independently.
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    render_area = RenderArea()
    render_area.setMinimumSize(600, 400) # Set a minimum size for standalone testing
    render_area.show()
    sys.exit(app.exec())
