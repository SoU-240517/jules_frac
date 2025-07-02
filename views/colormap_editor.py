import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QGraphicsView, QGraphicsScene, QLabel, QLineEdit, QFileDialog, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsItem
)
from PyQt6.QtGui import QAction, QLinearGradient, QColor, QBrush, QPainter, QPen
from PyQt6.QtCore import Qt, QTimer, QPointF


class GradientPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cmap_data = None
        self.setMinimumHeight(100)

    def set_colormap(self, cmap_data):
        self.cmap_data = cmap_data
        self.update()  # Schedule a repaint

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if not self.cmap_data:
            return

        gradient = QLinearGradient(0, 0, self.width(), 0)

        if self.cmap_data.get('type') == 'gradient' and 'gradient_points' in self.cmap_data:
            points = self.cmap_data['gradient_points']
            for point in points:
                pos = point.get('pos', 0.0)
                color_rgba = point.get('color', [0, 0, 0, 255])
                gradient.setColorAt(pos, QColor(*color_rgba))
        elif 'colors' in self.cmap_data:
            colors = self.cmap_data['colors']
            num_colors = len(colors)
            if num_colors > 0:
                if num_colors == 1:
                    gradient.setColorAt(0, QColor(*colors[0]))
                    gradient.setColorAt(1, QColor(*colors[0]))
                else:
                    for i, color_rgba in enumerate(colors):
                        pos = i / (num_colors - 1)
                        gradient.setColorAt(pos, QColor(*color_rgba))

        painter.fillRect(self.rect(), QBrush(gradient))

import json

class ColormapEditor(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colormap Editor")
        self.setGeometry(100, 100, 1200, 700)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        self._create_actions()
        self._create_menu_bar()

        # Left Panel (Color Pack Management)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(250)

        self.pack_name_label = QLabel("Pack: (None)")
        self.colormap_list = QListWidget()
        self.colormap_list.currentItemChanged.connect(self._on_colormap_selected)

        self.color_pack_data = None
        self.current_file_path = None
        add_button = QPushButton("Add")
        remove_button = QPushButton("Remove")
        rename_button = QPushButton("Rename")

        button_layout = QHBoxLayout()
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(rename_button)

        left_layout.addWidget(self.pack_name_label)
        left_layout.addWidget(self.colormap_list)
        left_layout.addLayout(button_layout)
        
        # Center Panel (Colormap Editor)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)

        self.gradient_preview = GradientPreviewWidget()
        self.node_editor = QGraphicsView() # Placeholder for node editor
        self.gradient_preview.setFixedHeight(150)
        self.node_editor.setFixedHeight(100)

        center_layout.addWidget(QLabel("Gradient Preview"))
        center_layout.addWidget(self.gradient_preview)
        center_layout.addWidget(QLabel("Node Editor"))
        center_layout.addWidget(self.node_editor)

        # Right Panel (Tools & Settings)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setFixedWidth(300)

        # Placeholder for Color Picker
        color_picker_placeholder = QLabel("Color Picker Area")
        color_picker_placeholder.setMinimumHeight(200)
        color_picker_placeholder.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")

        # Placeholder for Node Info
        node_info_layout = QVBoxLayout()
        node_info_layout.addWidget(QLabel("Node Info"))
        node_info_layout.addWidget(QLineEdit("Color: #RRGGBB"))
        node_info_layout.addWidget(QLineEdit("Position: 0.0"))

        # Placeholder for Utilities
        utilities_layout = QVBoxLayout()
        utilities_layout.addWidget(QLabel("Utilities"))
        utilities_layout.addWidget(QPushButton("Random Generate"))
        utilities_layout.addWidget(QPushButton("Extract from Image"))

        right_layout.addWidget(color_picker_placeholder)
        right_layout.addLayout(node_info_layout)
        right_layout.addStretch()
        right_layout.addLayout(utilities_layout)

        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(center_panel, 1) # Center panel takes available space
        main_layout.addWidget(right_panel)

    def _create_actions(self):
        self.open_action = QAction("開く...", self)
        self.open_action.triggered.connect(self.open_file)
        self.save_action = QAction("上書き保存", self)
        # self.save_action.triggered.connect(self.save_file)
        self.save_as_action = QAction("名前を付けて保存...", self)
        # self.save_as_action.triggered.connect(self.save_file_as)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ファイル")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "カラーパックを開く", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.load_color_pack(data, file_path)
            except Exception as e:
                print(f"Error loading file: {e}") # Replace with proper logging/error dialog

    def load_color_pack(self, data, file_path):
        self.color_pack_data = data
        self.pack_name_label.setText(f"Pack: {data.get('pack_name', 'N/A')}")
        self.colormap_list.clear()
        for cmap in data.get('maps', []):
            self.colormap_list.addItem(cmap.get('map_name', 'Unnamed'))
        self.current_file_path = file_path

    def _on_colormap_selected(self, current, previous):
        if current is None:
            self.gradient_preview.set_colormap(None)
            return

        map_name = current.text()
        if self.color_pack_data and 'maps' in self.color_pack_data:
            selected_map = next((m for m in self.color_pack_data['maps'] if m.get('map_name') == map_name), None)
            if selected_map:
                self.gradient_preview.set_colormap(selected_map)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = ColormapEditor()
    editor.show()
    sys.exit(app.exec())
