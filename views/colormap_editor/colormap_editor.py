import sys
import json
import copy
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QLineEdit, QFileDialog,
    QInputDialog, QColorDialog
)
from PyQt6.QtGui import QAction, QKeySequence, QColor
from PyQt6.QtCore import Qt

from .widgets import GradientPreviewWidget, NodeEditorView, NodeItem
from .utils import ColormapUtils


class ColormapEditor(QMainWindow):
    """カラーマップエディタメインウィンドウ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colormap Editor")
        self.setGeometry(100, 100, 1200, 700)

        # データ管理
        self.undo_stack = []
        self.redo_stack = []
        self.color_pack_data = None
        self.current_file_path = None
        self._selected_node = None

        # UI初期化
        self._init_ui()
        self._create_actions()
        self._create_menu_bar()
        self._setup_connections()

    def _init_ui(self):
        """UI初期化"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_panel = self._create_left_panel()
        center_panel = self._create_center_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(center_panel, 1)
        main_layout.addWidget(right_panel)

    def _create_actions(self):
        """アクション作成"""
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
        """メニューバー作成"""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("ファイル")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        edit_menu = menu_bar.addMenu("編集")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

    def _create_left_panel(self):
        """左パネル作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setFixedWidth(250)

        self.pack_name_label = QLabel("Pack: (None)")
        self.colormap_list = QListWidget()

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
        """中央パネル作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.gradient_preview = GradientPreviewWidget()
        self.gradient_preview.setFixedHeight(150)

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
        """右パネル作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setFixedWidth(300)

        # 色選択ボタン
        self.color_picker_button = QPushButton("色を選択")
        self.color_picker_button.setMinimumHeight(40)
        self.color_picker_button.clicked.connect(self.open_color_picker)
        self.color_picker_button.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")

        # ノード情報
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

        # ユーティリティ
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

    def _setup_connections(self):
        """シグナル接続設定"""
        self.colormap_list.currentItemChanged.connect(self._on_colormap_selected)
        self.gradient_preview.color_changed_at.connect(self.on_direct_edit_color_changed)
        self.node_editor.scene().selectionChanged.connect(self.on_node_selected)

    # ファイル操作
    def open_file(self):
        """ファイルを開く"""
        file_path, _ = QFileDialog.getOpenFileName(self, "カラーパックを開く", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.load_color_pack(data, file_path)
            except Exception as e:
                ColormapUtils.show_error_message(self, "読み込み失敗", f"ファイル読み込みに失敗しました:\n{e}")

    def save_file(self):
        """ファイルを保存"""
        if not self.current_file_path:
            self.save_file_as()
            return
        self._save_to_file(self.current_file_path)

    def save_file_as(self):
        """名前を付けて保存"""
        file_path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", "", "JSON Files (*.json)")
        if file_path:
            self.current_file_path = file_path
            self._save_to_file(file_path)

    def _save_to_file(self, file_path):
        """ファイルに保存"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.color_pack_data, f, ensure_ascii=False, indent=2)
            self.pack_name_label.setText(f"Pack: {self.color_pack_data.get('pack_name', 'N/A')}")
            ColormapUtils.show_success_message(self, "保存完了", f"ファイルを保存しました.\n{file_path}")
        except Exception as e:
            ColormapUtils.show_error_message(self, "保存失敗", f"ファイル保存に失敗しました:\n{e}")

    def load_color_pack(self, data, file_path):
        """カラーパックを読み込み"""
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

    # アンドゥ・リドゥ
    def _update_undo_redo_actions(self):
        """アンドゥ・リドゥアクションの状態を更新"""
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.redo_action.setEnabled(bool(self.redo_stack))

    def _save_state_for_undo(self):
        """アンドゥ用の状態を保存"""
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
        """元に戻す"""
        if not self.undo_stack:
            return
        self.redo_stack.append(copy.deepcopy(self.color_pack_data))
        self.color_pack_data = self.undo_stack.pop()
        self._reload_ui_from_data()
        self._update_undo_redo_actions()

    def redo(self):
        """やり直し"""
        if not self.redo_stack:
            return
        self.undo_stack.append(copy.deepcopy(self.color_pack_data))
        self.color_pack_data = self.redo_stack.pop()
        self._reload_ui_from_data()
        self._update_undo_redo_actions()

    def _reload_ui_from_data(self):
        """データからUIを再読み込み"""
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

    # カラーマップ操作
    def _on_colormap_selected(self, current, previous):
        """カラーマップ選択時の処理"""
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
        """カラーマップを追加"""
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
        """カラーマップを削除"""
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get("maps"):
            return
        self._save_state_for_undo()
        del self.color_pack_data["maps"][row]
        self.colormap_list.takeItem(row)

    def rename_colormap(self):
        """カラーマップ名を変更"""
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get("maps"):
            return
        current_name = self.color_pack_data["maps"][row].get("map_name", "")
        new_name, ok = QInputDialog.getText(self, "名前変更", "新しいカラーマップ名:", text=current_name)
        if ok and new_name:
            self._save_state_for_undo()
            self.color_pack_data["maps"][row]["map_name"] = new_name
            self.colormap_list.item(row).setText(new_name)

    # ノード編集
    def on_node_editor_changed(self, final_change=False):
        """ノードエディタ変更時の処理"""
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
        """ダイレクト編集時の色変更処理"""
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
        """ノード選択時の処理"""
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
        """ノード色編集時の処理"""
        if not self._selected_node:
            return
        text = self.node_color_edit.text().lstrip('#')
        if len(text) == 6:
            text += 'FF'
        if len(text) == 8:
            try:
                rgba = [int(text[i:i + 2], 16) for i in range(0, 8, 2)]
                self._selected_node.set_color(rgba)
                self.on_node_editor_changed(final_change=True)
            except ValueError:
                pass

    def on_node_pos_edit(self):
        """ノード位置編集時の処理"""
        if not self._selected_node:
            return
        try:
            pos = float(self.node_pos_edit.text())
            pos = min(max(pos, 0.0), 1.0)
            self._selected_node.setPos(pos * self.node_editor.scene().width(), self._selected_node.pos().y())
            self._selected_node.pos_value = pos
            self.on_node_editor_changed(final_change=True)
        except ValueError:
            pass

    def open_color_picker(self):
        """色選択ダイアログを開く"""
        if not self._selected_node:
            return
        initial = QColor(*self._selected_node.color_value)
        color = QColorDialog.getColor(initial, self, "色を選択")
        if color.isValid():
            rgba = [color.red(), color.green(), color.blue(), color.alpha()]
            self._selected_node.set_color(rgba)
            self.node_color_edit.setText('#{:02X}{:02X}{:02X}{:02X}'.format(*rgba))
            self.on_node_editor_changed(final_change=True)

    # ユーティリティ機能
    def on_random_generate(self):
        """ランダム生成"""
        num = ColormapUtils.get_random_generate_params(self)
        if num is None:
            return

        self._save_state_for_undo()
        points = ColormapUtils.random_generate_colormap(num)
        new_map = {
            "map_name": f"RandomMap{self.colormap_list.count() + 1}",
            "type": "gradient",
            "gradient_points": points,
            "num_colors": 256
        }
        if self.color_pack_data is None:
            self.color_pack_data = {"pack_name": "New Pack", "maps": []}
            self.pack_name_label.setText(f"Pack: {self.color_pack_data['pack_name']}")
        self.color_pack_data["maps"].append(new_map)
        self.colormap_list.addItem(new_map["map_name"])
        self.colormap_list.setCurrentRow(self.colormap_list.count() - 1)

    def on_extract_from_image(self):
        """画像から色を抽出"""
        file_path, num = ColormapUtils.get_extract_image_params(self)
        if file_path is None or num is None:
            return

        self._save_state_for_undo()
        try:
            points = ColormapUtils.extract_colors_from_image(file_path, num)
            new_map = {
                "map_name": f"ImageMap{self.colormap_list.count() + 1}",
                "type": "gradient",
                "gradient_points": points,
                "num_colors": 256
            }
            if self.color_pack_data is None:
                self.color_pack_data = {"pack_name": "New Pack", "maps": []}
                self.pack_name_label.setText(f"Pack: {self.color_pack_data['pack_name']}")
            self.color_pack_data["maps"].append(new_map)
            self.colormap_list.addItem(new_map["map_name"])
            self.colormap_list.setCurrentRow(self.colormap_list.count() - 1)
        except ImportError:
            ColormapUtils.show_error_message(self, "依存ライブラリ未インストール",
                                           "Pillow, scikit-learn, numpyが必要です.\n`pip install pillow scikit-learn numpy`")
        except Exception as e:
            ColormapUtils.show_error_message(self, "抽出失敗", f"画像から色抽出に失敗しました:\n{e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = ColormapEditor()
    editor.show()
    sys.exit(app.exec())
