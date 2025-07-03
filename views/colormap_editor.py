import sys
import json
import copy
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QGraphicsView, QGraphicsScene, QLabel, QLineEdit, QFileDialog,
    QGraphicsEllipseItem, QGraphicsItem, QInputDialog, QMenu, QColorDialog, QMessageBox
)
from PyQt6.QtGui import (
    QAction, QLinearGradient, QColor, QBrush, QPainter, QPen, QKeySequence, QImage
)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal


class GradientPreviewWidget(QWidget):
    color_changed_at = pyqtSignal(float, QColor)
    direct_edit_mode = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cmap_data = None
        self.setMinimumHeight(100)

    def set_colormap(self, cmap_data):
        self.cmap_data = cmap_data
        self.repaint()

    def set_direct_edit_mode(self, enabled):
        self.direct_edit_mode = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def get_color_at(self, pos: float) -> QColor:
        if not self.cmap_data:
            return QColor()

        gradient = QLinearGradient(0, 0, 1, 0)
        if self.cmap_data.get('type') == 'gradient' and 'gradient_points' in self.cmap_data:
            points = self.cmap_data['gradient_points']
            for point in points:
                gradient.setColorAt(point.get('pos', 0.0), QColor(*point.get('color', [0, 0, 0, 255])))
        elif 'colors' in self.cmap_data:
            colors = self.cmap_data['colors']
            num_colors = len(colors)
            if num_colors > 0:
                if num_colors == 1:
                    gradient.setColorAt(0, QColor(*colors[0]))
                    gradient.setColorAt(1, QColor(*colors[0]))
                else:
                    for i, color_rgba in enumerate(colors):
                        gradient.setColorAt(i / (num_colors - 1), QColor(*color_rgba))

        img = QImage(256, 1, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.fillRect(img.rect(), gradient)
        painter.end()

        x = min(max(int(pos * 255), 0), 255)
        return img.pixelColor(x, 0)

    def mousePressEvent(self, event):
        if self.direct_edit_mode and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos().x() / self.width()
            initial_color = self.get_color_at(pos)
            color = QColorDialog.getColor(initial_color, self, "色を選択")
            if color.isValid():
                self.color_changed_at.emit(pos, color)
        else:
            super().mousePressEvent(event)

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


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, pos, color, radius=8):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.setBrush(QBrush(QColor(*color)))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.pos_value = pos
        self.color_value = color

    def set_color(self, color):
        self.color_value = color
        self.setBrush(QBrush(QColor(*color)))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene:
                width = scene.width()
                new_x = min(max(value.x(), 0), width)
                self.pos_value = new_x / width if width > 0 else 0.0
                if scene.parent():
                    scene.parent().on_nodes_changed(final_change=False)
                return QPointF(new_x, self.pos().y())
        return super().itemChange(change, value)


class NodeEditorScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 600, 100)
        self.nodes = []

    def clear_nodes(self):
        for node in self.nodes:
            self.removeItem(node)
        self.nodes.clear()

    def add_node(self, pos, color):
        node = NodeItem(pos, color)
        node.setPos(pos * self.width(), self.height() / 2)
        self.addItem(node)
        self.nodes.append(node)
        return node

    def contextMenuEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        if isinstance(item, NodeItem):
            menu = QMenu()
            remove_action = menu.addAction("ノード削除")
            action = menu.exec(event.screenPos())
            if action == remove_action:
                self.removeItem(item)
                self.nodes.remove(item)
                self.parent().on_nodes_changed(final_change=True)

    def mouseDoubleClickEvent(self, event):
        x = event.scenePos().x()
        pos = min(max(x / self.width(), 0.0), 1.0)
        color = [255, 255, 255, 255]
        self.add_node(pos, color)
        self.parent().on_nodes_changed(final_change=True)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.parent().on_nodes_changed(final_change=True)


class NodeEditorView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(NodeEditorScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(100)

    def set_nodes(self, points):
        scene = self.scene()
        scene.clear_nodes()
        for pt in points:
            scene.add_node(pt.get('pos', 0.0), pt.get('color', [255, 255, 255, 255]))

    def get_nodes(self):
        scene = self.scene()
        return sorted([
            {'pos': node.pos_value, 'color': node.color_value}
            for node in scene.nodes
        ], key=lambda x: x['pos'])

    def on_nodes_changed(self, final_change=False):
        if hasattr(self.parent(), 'on_node_editor_changed'):
            self.parent().on_node_editor_changed(final_change=final_change)


class ColormapEditor(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colormap Editor")
        self.setGeometry(100, 100, 1200, 700)

        self.undo_stack = []
        self.redo_stack = []
        self.color_pack_data = None
        self.current_file_path = None
        self._selected_node = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        self._create_actions()
        self._create_menu_bar()

        left_panel = self._create_left_panel()
        center_panel = self._create_center_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(center_panel, 1)
        main_layout.addWidget(right_panel)

        self.node_editor.scene().selectionChanged.connect(self.on_node_selected)

    def _create_actions(self):
        self.open_action = QAction("開く...", self)
        self.open_action.triggered.connect(self.open_file)
        self.save_action = QAction("上書き保存", self)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action = QAction("名前を付けて保存...", self)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.undo_action = QAction("元に戻す", self)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setEnabled(False)
        self.redo_action = QAction("やり直し", self)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setEnabled(False)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ファイル")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        edit_menu = menu_bar.addMenu("編集")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setFixedWidth(250)
        self.pack_name_label = QLabel("Pack: (None)")
        self.colormap_list = QListWidget()
        self.colormap_list.currentItemChanged.connect(self._on_colormap_selected)
        add_button = QPushButton("Add")
        add_button.clicked.connect(self.add_colormap)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_colormap)
        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(self.rename_colormap)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(add_button)
        btn_layout.addWidget(remove_button)
        btn_layout.addWidget(rename_button)
        layout.addWidget(self.pack_name_label)
        layout.addWidget(self.colormap_list)
        layout.addLayout(btn_layout)
        return panel

    def _create_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.gradient_preview = GradientPreviewWidget()
        self.gradient_preview.setFixedHeight(150)
        self.gradient_preview.color_changed_at.connect(self.on_direct_edit_color_changed)
        self.node_editor = NodeEditorView(self)
        self.direct_edit_label = QLabel("ダイレクト編集モード: グラデーションをクリックして色を編集")
        self.direct_edit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.direct_edit_label.setVisible(False)
        layout.addWidget(QLabel("Gradient Preview"))
        layout.addWidget(self.gradient_preview)
        layout.addWidget(QLabel("Node Editor"))
        layout.addWidget(self.node_editor)
        layout.addWidget(self.direct_edit_label)
        return panel

    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setFixedWidth(300)
        self.color_picker_button = QPushButton("色を選択")
        self.color_picker_button.setMinimumHeight(40)
        self.color_picker_button.clicked.connect(self.open_color_picker)
        self.color_picker_button.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        node_info_layout = QVBoxLayout()
        node_info_layout.addWidget(QLabel("Node Info"))
        self.node_color_edit = QLineEdit()
        self.node_color_edit.setPlaceholderText("Color: #RRGGBBAA")
        self.node_color_edit.editingFinished.connect(self.on_node_color_edit)
        node_info_layout.addWidget(self.node_color_edit)
        self.node_pos_edit = QLineEdit()
        self.node_pos_edit.setPlaceholderText("Position: 0.0")
        self.node_pos_edit.editingFinished.connect(self.on_node_pos_edit)
        node_info_layout.addWidget(self.node_pos_edit)
        utilities_layout = QVBoxLayout()
        utilities_layout.addWidget(QLabel("Utilities"))
        self.random_generate_button = QPushButton("Random Generate")
        self.random_generate_button.clicked.connect(self.on_random_generate)
        self.extract_image_button = QPushButton("Extract from Image")
        self.extract_image_button.clicked.connect(self.on_extract_from_image)
        utilities_layout.addWidget(self.random_generate_button)
        utilities_layout.addWidget(self.extract_image_button)
        layout.addWidget(self.color_picker_button)
        layout.addLayout(node_info_layout)
        layout.addStretch()
        layout.addLayout(utilities_layout)
        return panel

    def _update_undo_redo_actions(self):
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.redo_action.setEnabled(bool(self.redo_stack))

    def _save_state_for_undo(self):
        if not self.color_pack_data:
            return
        if self.undo_stack and self.undo_stack[-1] == self.color_pack_data:
            return
        self.undo_stack.append(copy.deepcopy(self.color_pack_data))
        self.redo_stack.clear()
        self._update_undo_redo_actions()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(copy.deepcopy(self.color_pack_data))
        self.color_pack_data = self.undo_stack.pop()
        self._reload_ui_from_data()
        self._update_undo_redo_actions()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(copy.deepcopy(self.color_pack_data))
        self.color_pack_data = self.redo_stack.pop()
        self._reload_ui_from_data()
        self._update_undo_redo_actions()

    def _reload_ui_from_data(self):
        current_item = self.colormap_list.currentItem()
        current_item_text = current_item.text() if current_item else None
        self.pack_name_label.setText(f"Pack: {self.color_pack_data.get('pack_name', 'N/A')}")
        self.colormap_list.clear()
        new_selection_row = -1
        for i, cmap in enumerate(self.color_pack_data.get('maps', [])):
            map_name = cmap.get('map_name', 'Unnamed')
            self.colormap_list.addItem(map_name)
            if map_name == current_item_text:
                new_selection_row = i
        if new_selection_row != -1:
            self.colormap_list.setCurrentRow(new_selection_row)
        elif self.colormap_list.count() > 0:
            self.colormap_list.setCurrentRow(0)
        else:
            self._on_colormap_selected(None, None)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "カラーパックを開く", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.load_color_pack(data, file_path)
            except Exception as e:
                QMessageBox.warning(self, "読み込み失敗", f"ファイル読み込みに失敗しました:\n{e}")

    def load_color_pack(self, data, file_path):
        self.color_pack_data = data
        self.pack_name_label.setText(f"Pack: {data.get('pack_name', 'N/A')}")
        self.colormap_list.clear()
        for cmap in data.get('maps', []):
            self.colormap_list.addItem(cmap.get('map_name', 'Unnamed'))
        self.current_file_path = file_path
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._update_undo_redo_actions()
        if self.colormap_list.count() > 0:
            self.colormap_list.setCurrentRow(0)

    def _on_colormap_selected(self, current, previous):
        if current is None:
            self.gradient_preview.set_colormap(None)
            self.node_editor.set_nodes([])
            self.node_editor.setVisible(True)
            self.direct_edit_label.setVisible(False)
            self.gradient_preview.set_direct_edit_mode(False)
            return

        map_name = current.text()
        if self.color_pack_data and 'maps' in self.color_pack_data:
            selected_map = next((m for m in self.color_pack_data['maps'] if m.get('map_name') == map_name), None)
            if selected_map:
                self.gradient_preview.set_colormap(selected_map)
                is_gradient = selected_map.get('type') == 'gradient'
                is_discrete = 'colors' in selected_map
                points = selected_map.get('gradient_points', [])
                colors = selected_map.get('colors', [])
                num_nodes = len(points) if is_gradient else len(colors)

                if num_nodes <= 30:
                    self.node_editor.setVisible(True)
                    self.direct_edit_label.setVisible(False)
                    self.gradient_preview.set_direct_edit_mode(False)
                    if is_gradient:
                        self.node_editor.set_nodes(points)
                    elif is_discrete:
                        n = len(colors)
                        points_from_colors = [{'pos': i / (n - 1) if n > 1 else 0.0, 'color': c} for i, c in enumerate(colors)]
                        self.node_editor.set_nodes(points_from_colors)
                else:
                    self.node_editor.setVisible(False)
                    self.direct_edit_label.setVisible(True)
                    self.gradient_preview.set_direct_edit_mode(True)
                    self.node_editor.set_nodes([])

    def add_colormap(self):
        self._save_state_for_undo()
        if self.color_pack_data is None:
            self.color_pack_data = {"pack_name": "New Pack", "maps": []}
            self.pack_name_label.setText(f"Pack: {self.color_pack_data['pack_name']}")
        new_map = {
            "map_name": f"New Map {self.colormap_list.count() + 1}",
            "type": "gradient",
            "gradient_points": [
                {"pos": 0.0, "color": [255, 0, 0, 255]},
                {"pos": 1.0, "color": [0, 0, 255, 255]}
            ],
            "num_colors": 256
        }
        self.color_pack_data["maps"].append(new_map)
        self.colormap_list.addItem(new_map["map_name"])
        self.colormap_list.setCurrentRow(self.colormap_list.count() - 1)

    def remove_colormap(self):
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get("maps"):
            return
        self._save_state_for_undo()
        del self.color_pack_data["maps"][row]
        self.colormap_list.takeItem(row)

    def rename_colormap(self):
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get("maps"):
            return
        current_name = self.color_pack_data["maps"][row].get("map_name", "")
        new_name, ok = QInputDialog.getText(self, "名前変更", "新しいカラーマップ名:", text=current_name)
        if ok and new_name:
            self._save_state_for_undo()
            self.color_pack_data["maps"][row]["map_name"] = new_name
            self.colormap_list.item(row).setText(new_name)

    def on_node_editor_changed(self, final_change=False):
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get('maps'):
            return
        if final_change:
            self._save_state_for_undo()
        cmap = self.color_pack_data['maps'][row]
        points = self.node_editor.get_nodes()
        cmap['type'] = 'gradient'
        cmap['gradient_points'] = points
        cmap['num_colors'] = 256
        if 'colors' in cmap:
            del cmap['colors']
        self.gradient_preview.set_colormap(cmap)

    def on_direct_edit_color_changed(self, pos, color):
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data:
            return
        self._save_state_for_undo()
        cmap = self.color_pack_data['maps'][row]
        rgba = [color.red(), color.green(), color.blue(), color.alpha()]
        if 'colors' in cmap:
            n = len(cmap['colors'])
            points = [{'pos': i / (n - 1) if n > 1 else 0.0, 'color': c} for i, c in enumerate(cmap['colors'])]
            cmap['gradient_points'] = points
            del cmap['colors']
            cmap['type'] = 'gradient'
            cmap['num_colors'] = 256
        cmap.setdefault('gradient_points', []).append({'pos': pos, 'color': rgba})
        cmap['gradient_points'] = sorted(cmap['gradient_points'], key=lambda x: x['pos'])
        self.gradient_preview.set_colormap(cmap)

    def on_node_selected(self):
        selected = [item for item in self.node_editor.scene().selectedItems() if isinstance(item, NodeItem)]
        if selected:
            node = selected[0]
            self._selected_node = node
            rgba = node.color_value
            self.node_color_edit.setText('#{:02X}{:02X}{:02X}{:02X}'.format(*rgba))
            self.node_pos_edit.setText(f'{node.pos_value:.4f}')
        else:
            self._selected_node = None
            self.node_color_edit.setText("")
            self.node_pos_edit.setText("")

    def on_node_color_edit(self):
        if not self._selected_node: return
        text = self.node_color_edit.text().lstrip('#')
        if len(text) == 6: text += 'FF'
        if len(text) == 8:
            try:
                rgba = [int(text[i:i + 2], 16) for i in range(0, 8, 2)]
                self._selected_node.set_color(rgba)
                self.on_node_editor_changed(final_change=True)
            except ValueError: pass

    def on_node_pos_edit(self):
        if not self._selected_node: return
        try:
            pos = float(self.node_pos_edit.text())
            pos = min(max(pos, 0.0), 1.0)
            self._selected_node.setPos(pos * self.node_editor.scene().width(), self._selected_node.pos().y())
            self._selected_node.pos_value = pos
            self.on_node_editor_changed(final_change=True)
        except ValueError: pass

    def open_color_picker(self):
        if not self._selected_node: return
        initial = QColor(*self._selected_node.color_value)
        color = QColorDialog.getColor(initial, self, "色を選択")
        if color.isValid():
            rgba = [color.red(), color.green(), color.blue(), color.alpha()]
            self._selected_node.set_color(rgba)
            self.node_color_edit.setText('#{:02X}{:02X}{:02X}{:02X}'.format(*rgba))
            self.on_node_editor_changed(final_change=True)

    def on_random_generate(self):
        num, ok = QInputDialog.getInt(self, "ランダム生成", "ノード数 (2〜30):", 5, 2, 30)
        if not ok: return
        self._save_state_for_undo()
        points = []
        for i in range(num):
            pos = i / (num - 1) if num > 1 else 0.0
            if i != 0 and i != num - 1:
                pos += random.uniform(-0.1, 0.1)
                pos = min(max(pos, 0.0), 1.0)
            color = [random.randint(0, 255) for _ in range(3)] + [255]
            points.append({'pos': pos, 'color': color})
        points.sort(key=lambda x: x['pos'])
        new_map = {
            "map_name": f"RandomMap{self.colormap_list.count() + 1}",
            "type": "gradient", "gradient_points": points, "num_colors": 256
        }
        if self.color_pack_data is None:
            self.color_pack_data = {"pack_name": "New Pack", "maps": []}
            self.pack_name_label.setText(f"Pack: {self.color_pack_data['pack_name']}")
        self.color_pack_data["maps"].append(new_map)
        self.colormap_list.addItem(new_map["map_name"])
        self.colormap_list.setCurrentRow(self.colormap_list.count() - 1)

    def on_extract_from_image(self):
        try:
            from PIL import Image
            from sklearn.cluster import KMeans
            import numpy as np
        except ImportError:
            QMessageBox.warning(self, "依存ライブラリ未インストール", "Pillow, scikit-learn, numpyが必要です.\n`pip install pillow scikit-learn numpy`")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "画像ファイルを選択", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if not file_path: return
        num, ok = QInputDialog.getInt(self, "色数指定", "抽出する色数 (2〜30):", 5, 2, 30)
        if not ok: return
        self._save_state_for_undo()
        try:
            img = Image.open(file_path).convert('RGBA')
            img = img.resize((128, 128))
            pixels = np.array(img).reshape(-1, 4)
            pixels = pixels[pixels[:, 3] > 0]
            kmeans = KMeans(n_clusters=num, n_init='auto', random_state=0).fit(pixels[:, :3])
            centers = kmeans.cluster_centers_.astype(int)
            points = [{'pos': i / (num - 1) if num > 1 else 0.0, 'color': list(c) + [255]} for i, c in enumerate(centers)]
            new_map = {
                "map_name": f"ImageMap{self.colormap_list.count() + 1}",
                "type": "gradient", "gradient_points": points, "num_colors": 256
            }
            if self.color_pack_data is None:
                self.color_pack_data = {"pack_name": "New Pack", "maps": []}
                self.pack_name_label.setText(f"Pack: {self.color_pack_data['pack_name']}")
            self.color_pack_data["maps"].append(new_map)
            self.colormap_list.addItem(new_map["map_name"])
            self.colormap_list.setCurrentRow(self.colormap_list.count() - 1)
        except Exception as e:
            QMessageBox.warning(self, "抽出失敗", f"画像から色抽出に失敗しました:\n{e}")

    def save_file(self):
        if not self.current_file_path:
            self.save_file_as()
            return
        try:
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.color_pack_data, f, ensure_ascii=False, indent=2)
            self.pack_name_label.setText(f"Pack: {self.color_pack_data.get('pack_name', 'N/A')}")
            QMessageBox.information(self, "保存完了", f"ファイルを保存しました.\n{self.current_file_path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失敗", f"ファイル保存に失敗しました:\n{e}")

    def save_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.color_pack_data, f, ensure_ascii=False, indent=2)
            self.current_file_path = file_path
            self.pack_name_label.setText(f"Pack: {self.color_pack_data.get('pack_name', 'N/A')}")
            QMessageBox.information(self, "保存完了", f"新しいファイルに保存しました.\n{self.current_file_path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失敗", f"ファイル保存に失敗しました:\n{e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = ColormapEditor()
    editor.show()
    sys.exit(app.exec())