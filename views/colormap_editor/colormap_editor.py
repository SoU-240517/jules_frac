import sys
import json
import copy
import re
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QLineEdit, QFileDialog,
    QInputDialog, QColorDialog
)
from PyQt6.QtGui import QAction, QKeySequence, QColor
from PyQt6.QtCore import Qt, QTimer
import os

from utils.settings_manager import SettingsManager

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

        # ノード移動中の遅延更新用タイマー
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._delayed_update_preview)

        # 設定読み込み
        self.settings_manager = SettingsManager()
        self.random_generate_max_count = self.settings_manager.get_setting("colormap_editor_settings.random_generate_max_count", 30)

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

        self.file_name_label = QLabel("File: (None)")
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

        layout.addWidget(self.file_name_label)
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
        # 現在の作業ディレクトリ（main.pyから起動していればjules_frac）
        project_root = os.getcwd()
        colorpacks_dir = os.path.join(project_root, 'plugins', 'colorpacks')
        if not os.path.exists(colorpacks_dir):
            colorpacks_dir = project_root
        file_path, _ = QFileDialog.getOpenFileName(self, "カラーパックを開く", colorpacks_dir, "JSON Files (*.json)")
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
        if not self.color_pack_data:
            return

        current_pack_name = self.color_pack_data.get("pack_name", "New Pack")
        new_pack_name, ok = QInputDialog.getText(self, "カラーパック名の設定", "新しいカラーパック名:", text=current_pack_name)

        if ok and new_pack_name:
            # 新しいファイル名を提案
            # 安全なファイル名に変換
            safe_new_pack_name = re.sub(r'[\\/:"*?<>|]+', '_', new_pack_name)
            # 現在のディレクトリを取得
            if self.current_file_path:
                dir_path = os.path.dirname(self.current_file_path)
            else:
                project_root = os.getcwd()
                dir_path = os.path.join(project_root, 'plugins', 'colorpacks')
            
            suggested_filename = os.path.join(dir_path, f"{safe_new_pack_name}.json")

            file_path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", suggested_filename, "JSON Files (*.json)")
            
            if file_path:
                self._save_state_for_undo()
                self.color_pack_data["pack_name"] = new_pack_name
                self.current_file_path = file_path
                self._save_to_file(file_path)

    def _save_to_file(self, file_path):
        """ファイルに保存"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('{\n')
                f.write(f'    "pack_name": {json.dumps(self.color_pack_data["pack_name"], ensure_ascii=False)},\n')
                f.write('    "maps": [\n')
                num_maps = len(self.color_pack_data["maps"])
                for map_index, map_data in enumerate(self.color_pack_data["maps"]):
                    f.write('        {\n')
                    keys = list(map_data.keys())
                    for i, key in enumerate(keys):
                        f.write(f'            "{key}": ')
                        if key == "colors":
                            f.write('[\n')
                            colors, num_colors_inner = map_data[key], len(map_data[key])
                            for j, color in enumerate(colors):
                                if j % 5 == 0: f.write(' ' * 16)
                                f.write(f'[{color[0]},{color[1]},{color[2]},{color[3]}]')
                                if j < num_colors_inner - 1: f.write(',')
                                if (j + 1) % 5 == 0 and j < num_colors_inner - 1: f.write('\n')
                            f.write('\n' + ' ' * 12 + ']')
                        elif key == "gradient_points":
                            f.write('[\n')
                            points, num_points_ = map_data[key], len(map_data[key])
                            for j, point in enumerate(points):
                                f.write(' ' * 16 + json.dumps(point, ensure_ascii=False))
                                if j < num_points_ - 1: f.write(',')
                                f.write('\n')
                            f.write(' ' * 12 + ']')
                        else:
                            f.write(json.dumps(map_data[key], ensure_ascii=False))
                        if i < len(keys) - 1: f.write(',')
                        f.write('\n')
                    f.write('        }')
                    if map_index < num_maps - 1: f.write(',\n')
                    else: f.write('\n')
                f.write('    ]\n')
                f.write('}\n')

            self.file_name_label.setText(f"File: {os.path.basename(file_path)}")
            self.pack_name_label.setText(f"Pack: {self.color_pack_data.get('pack_name', 'N/A')}")
            ColormapUtils.show_success_message(self, "保存完了", f"ファイルを保存しました.\n{file_path}")
        except Exception as e:
            ColormapUtils.show_error_message(self, "保存失敗", f"ファイル保存に失敗しました:\n{e}")

    def load_color_pack(self, data, file_path):
        """カラーパックを読み込み"""
        self.color_pack_data = data
        self.file_name_label.setText(f"File: {os.path.basename(file_path)}")
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
        print("ColormapEditor: _save_state_for_undo 呼び出し（undo保存）")

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
        print(f"ColormapEditor: on_node_editor_changed 呼び出し - final_change: {final_change}")
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get('maps'):
            print(f"ColormapEditor: 条件チェック失敗 - row: {row}, color_pack_data: {self.color_pack_data is not None}")
            return

        if final_change == 'start_drag':
            print("ColormapEditor: ドラッグ開始時 - 状態保存（UI同期→保存）")
            self._update_gradient_preview()  # まずUIの状態でcolor_pack_dataを最新化
            self._save_state_for_undo()     # その直後にundo保存
            return
        if final_change:
            # 最終変更の場合は即座に更新
            print("ColormapEditor: 最終変更 - 即座に更新")
            self._update_timer.stop()  # 遅延更新をキャンセル
            self._save_state_for_undo()
            self._update_gradient_preview()
        else:
            # 移動中の場合は遅延更新を使用
            print("ColormapEditor: 移動中 - 遅延更新開始")
            self._update_timer.start(50)  # 50ms後に更新

    def _delayed_update_preview(self):
        """遅延更新処理"""
        print("ColormapEditor: 遅延更新実行")
        self._update_gradient_preview()

    def _update_gradient_preview(self):
        """グラディエントプレビューを更新"""
        print("ColormapEditor: _update_gradient_preview 開始")
        row = self.colormap_list.currentRow()
        if row < 0 or not self.color_pack_data or not self.color_pack_data.get('maps'):
            print(f"ColormapEditor: _update_gradient_preview 条件チェック失敗 - row: {row}, color_pack_data: {self.color_pack_data is not None}")
            return

        cmap = self.color_pack_data['maps'][row]
        points = self.node_editor.get_nodes()

        # デバッグ情報を出力
        print(f"ColormapEditor: プレビュー更新 - 元のtype: {cmap.get('type')}, colors: {len(cmap.get('colors', []))}, points: {len(points)}")

        # 常にgradient_points形式に変換
        cmap['type'] = 'gradient'
        cmap['gradient_points'] = points
        cmap['num_colors'] = 256

        # colorsフィールドが存在する場合は削除（gradient_pointsに変換済み）
        if 'colors' in cmap:
            del cmap['colors']

        print(f"ColormapEditor: 変換後 - type: {cmap.get('type')}, gradient_points: {len(cmap.get('gradient_points', []))}")

        self.gradient_preview.set_colormap(cmap)
        print("ColormapEditor: _update_gradient_preview 完了")

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
        self._update_color_picker_button()

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
                self._update_color_picker_button()
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
            self._update_color_picker_button()

    # ユーティリティ機能
    def on_random_generate(self):
        """ランダム生成"""
        num_to_generate = ColormapUtils.get_random_generate_params(self, max_value=self.random_generate_max_count)
        if num_to_generate is None:
            return

        self._save_state_for_undo()
        if self.color_pack_data is None:
            self.color_pack_data = {"pack_name": "New Pack", "maps": []}
            self.pack_name_label.setText(f"Pack: {self.color_pack_data['pack_name']}")

        for i in range(num_to_generate):
            # ノード数は2から10の間でランダムに決める（例）
            num_nodes = random.randint(2, 10)
            points = ColormapUtils.random_generate_colormap(num_nodes)
            new_map = {
                "map_name": f"RandomMap{self.colormap_list.count() + 1}",
                "type": "gradient",
                "gradient_points": points,
                "num_colors": 256
            }
            self.color_pack_data["maps"].append(new_map)
            self.colormap_list.addItem(new_map["map_name"])
        
        if num_to_generate > 0:
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

    def _update_color_picker_button(self):
        """色選択ボタンの背景色を選択中ノードの色に合わせて更新"""
        if self._selected_node:
            rgba = self._selected_node.color_value
            self.color_picker_button.setStyleSheet(
                f"background-color: rgba({rgba[0]}, {rgba[1]}, {rgba[2]}, {rgba[3]/255}); border: 1px solid #ccc;"
            )
        else:
            self.color_picker_button.setStyleSheet(
                "background-color: #f0f0f0; border: 1px solid #ccc;"
            )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = ColormapEditor()
    editor.show()
    sys.exit(app.exec())
