import sys
import json
import os
import random
from PyQt6.QtWidgets import QApplication, QMainWindow, QInputDialog, QColorDialog
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QTimer

from utils.settings_manager import SettingsManager
from logger.custom_logger import CustomLogger
from models.colormap import ColorPack, Colormap, ColorStop
from .widgets import NodeItem
from .utils import ColormapUtils
from .state_manager import ColormapStateManager
from .ui_manager import UIManager
from .file_handler import ColormapFileHandler

logger = CustomLogger()

class ColormapEditor(QMainWindow):
    """カラーマップエディタメインウィンドウ"""

    def __init__(self, parent=None, pack_name=None, map_name=None):
        super().__init__(parent)
        self.setWindowTitle("Colormap Editor")
        self.setGeometry(100, 100, 1200, 700)

        self._selected_node = None
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._delayed_update_preview)

        self.settings_manager = SettingsManager()
        self.load_settings()

        self.state_manager = ColormapStateManager()
        self.ui_manager = UIManager(self)
        self.file_handler = ColormapFileHandler(self)

        self._setup_connections()

        if pack_name:
            self.load_initial_pack(pack_name, map_name)

    def load_settings(self):
        """アプリケーション設定を読み込む"""
        self.random_generate_max_count = self.settings_manager.get_setting("colormap_editor_settings.random_generate_max_count", 30)
        self.random_generate_max_nodes = self.settings_manager.get_setting("colormap_editor_settings.random_generate_max_nodes", 20)
        self.extract_image_max_maps = self.settings_manager.get_setting("colormap_editor_settings.extract_image_max_maps", 30)

    def _setup_connections(self):
        """UI要素のシグナルを対応するスロットに接続する"""
        # アクション
        self.new_action.triggered.connect(self.new_file)
        self.open_action.triggered.connect(self.open_file)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action.triggered.connect(self.redo)

        # ボタン
        self.add_button.clicked.connect(self.add_colormap)
        self.copy_button.clicked.connect(self.copy_colormap)
        self.rename_button.clicked.connect(self.rename_colormap)
        self.remove_button.clicked.connect(self.remove_colormap)
        self.flip_button.clicked.connect(self.on_flip_horizontal)
        self.random_generate_button.clicked.connect(self.on_random_generate)
        self.extract_image_button.clicked.connect(self.on_extract_from_image)
        self.color_picker_button.clicked.connect(self.open_color_picker)

        # ウィジェット
        self.colormap_list.currentItemChanged.connect(self.on_colormap_selected)
        self.gradient_preview.color_changed_at.connect(self.on_direct_edit_color_changed)
        self.node_editor.scene().selectionChanged.connect(self.on_node_selected)
        self.node_color_edit.editingFinished.connect(self.on_node_color_edit)
        self.node_pos_edit.editingFinished.connect(self.on_node_pos_edit)

    def load_initial_pack(self, pack_name, map_name):
        """起動時に指定されたカラーパックとマップを読み込む"""
        colorpacks_dir = os.path.join(os.getcwd(), 'plugins', 'colorpacks')
        if not os.path.isdir(colorpacks_dir):
            return

        for fname in os.listdir(colorpacks_dir):
            if fname.lower().endswith('.json'):
                file_path = os.path.join(colorpacks_dir, fname)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data.get("pack_name") == pack_name:
                        color_pack = ColorPack.from_dict(data)
                        color_pack.file_path = file_path
                        self.state_manager.set_current_state(color_pack)
                        self.ui_manager.update_ui_from_state(self.state_manager)
                        self.select_initial_map(map_name)
                        break
                except (json.JSONDecodeError, KeyError) as e:
                    logger.log(f"Skipping invalid color pack file: {fname}, Error: {e}", level="DEBUG")

    def select_initial_map(self, map_name):
        """指定された名前のカラーマップを選択する"""
        if not map_name or self.colormap_list.count() == 0:
            return

        for i in range(self.colormap_list.count()):
            if self.colormap_list.item(i).text() == map_name:
                self.colormap_list.setCurrentRow(i)
                return
        
        # 完全一致がない場合は部分一致で探す
        for i in range(self.colormap_list.count()):
            if map_name.lower() in self.colormap_list.item(i).text().lower():
                self.colormap_list.setCurrentRow(i)
                return

    # --- ファイル操作 ---
    def new_file(self):
        self.state_manager.set_current_state(None)
        self.ui_manager.update_ui_from_state(self.state_manager)
        self.on_colormap_selected(None, None)

    def open_file(self):
        color_pack = self.file_handler.open_file()
        if color_pack:
            self.state_manager.set_current_state(color_pack)
            self.ui_manager.update_ui_from_state(self.state_manager)
            if self.colormap_list.count() > 0:
                self.colormap_list.setCurrentRow(0)

    def save_file(self):
        color_pack = self.state_manager.get_current_state()
        if not color_pack:
            return
        
        file_path = getattr(color_pack, 'file_path', None)
        if file_path:
            self.file_handler.save_to_file(file_path, color_pack)
        else:
            self.save_file_as()

    def save_file_as(self):
        color_pack = self.state_manager.get_current_state()
        if color_pack:
            updated_pack = self.file_handler.save_file_as(color_pack)
            if updated_pack:
                self.state_manager.set_current_state(updated_pack)
                self.ui_manager.update_ui_from_state(self.state_manager)

    # --- アンドゥ・リドゥ ---
    def undo(self):
        if self.state_manager.can_undo():
            self.state_manager.undo()
            self.ui_manager.update_ui_from_state(self.state_manager)
            self.on_colormap_selected(self.colormap_list.currentItem(), None)

    def redo(self):
        if self.state_manager.can_redo():
            self.state_manager.redo()
            self.ui_manager.update_ui_from_state(self.state_manager)
            self.on_colormap_selected(self.colormap_list.currentItem(), None)

    # --- カラーマップ操作 ---
    def get_selected_colormap(self) -> Colormap | None:
        color_pack = self.state_manager.get_current_state()
        if not color_pack:
            return None
        row = self.colormap_list.currentRow()
        if 0 <= row < len(color_pack.maps):
            return color_pack.maps[row]
        return None
    
    def get_selected_colormap_name(self) -> str | None:
        item = self.colormap_list.currentItem()
        return item.text() if item else None

    def on_colormap_selected(self, current, previous):
        selected_map = self.get_selected_colormap()
        if selected_map:
            self.gradient_preview.set_colormap(selected_map)
            
            # ノード数に応じてエディタ表示を切り替え
            num_nodes = len(selected_map.gradient_points) if selected_map.map_type == 'gradient' else len(selected_map.colors)
            use_direct_edit = num_nodes > 30

            self.node_editor.setVisible(not use_direct_edit)
            self.direct_edit_label.setVisible(use_direct_edit)
            self.gradient_preview.set_direct_edit_mode(use_direct_edit)

            if not use_direct_edit:
                if selected_map.map_type == 'gradient':
                    points = [{'pos': p.pos, 'color': p.color} for p in selected_map.gradient_points]
                    self.node_editor.set_nodes(points)
                elif selected_map.map_type == 'indexed':
                    n = len(selected_map.colors)
                    points = [{'pos': i / (n - 1) if n > 1 else 0.0, 'color': c} for i, c in enumerate(selected_map.colors)]
                    self.node_editor.set_nodes(points)
            else:
                self.node_editor.set_nodes([])
        else:
            self.gradient_preview.set_colormap(None)
            self.node_editor.set_nodes([])
            self.node_editor.setVisible(True)
            self.direct_edit_label.setVisible(False)
            self.gradient_preview.set_direct_edit_mode(False)

    def add_colormap(self):
        self.state_manager.save_state_for_undo()
        color_pack = self.state_manager.get_current_state()
        if color_pack is None:
            color_pack = ColorPack(pack_name="New Pack")
            self.state_manager.set_current_state(color_pack)

        new_map = Colormap(
            map_name=f"New Map {len(color_pack.maps) + 1}",
            map_type="gradient",
            gradient_points=[
                ColorStop(pos=0.0, color=[255, 0, 0, 255]),
                ColorStop(pos=1.0, color=[0, 0, 255, 255])
            ]
        )
        color_pack.maps.append(new_map)
        self.ui_manager.update_ui_from_state(self.state_manager)
        self.colormap_list.setCurrentRow(len(color_pack.maps) - 1)

    def remove_colormap(self):
        color_pack = self.state_manager.get_current_state()
        row = self.colormap_list.currentRow()
        if color_pack and 0 <= row < len(color_pack.maps):
            self.state_manager.save_state_for_undo()
            del color_pack.maps[row]
            self.ui_manager.update_ui_from_state(self.state_manager)

    def rename_colormap(self):
        selected_map = self.get_selected_colormap()
        if selected_map:
            new_name, ok = QInputDialog.getText(self, "名前変更", "新しいカラーマップ名:", text=selected_map.map_name)
            if ok and new_name:
                self.state_manager.save_state_for_undo()
                selected_map.map_name = new_name
                self.ui_manager.update_ui_from_state(self.state_manager)

    def copy_colormap(self):
        color_pack = self.state_manager.get_current_state()
        row = self.colormap_list.currentRow()
        if color_pack and 0 <= row < len(color_pack.maps):
            original_map = color_pack.maps[row]
            new_name, ok = QInputDialog.getText(self, "コピー", "新しいカラーマップ名:", text=f"{original_map.map_name} Copy")
            if ok and new_name:
                self.state_manager.save_state_for_undo()
                new_map = Colormap.from_dict(original_map.to_dict()) # Deep copy
                new_map.map_name = new_name
                color_pack.maps.insert(row + 1, new_map)
                self.ui_manager.update_ui_from_state(self.state_manager)
                self.colormap_list.setCurrentRow(row + 1)

    # --- ノード編集 ---
    def on_node_editor_changed(self, final_change=False):
        if final_change == 'start_drag':
            self._update_colormap_from_nodes()
            self.state_manager.save_state_for_undo()
            return
        
        if final_change:
            self._update_timer.stop()
            self.state_manager.save_state_for_undo()
            self._update_colormap_from_nodes()
        else:
            self._update_timer.start(50)

    def _delayed_update_preview(self):
        self._update_colormap_from_nodes()

    def _update_colormap_from_nodes(self):
        selected_map = self.get_selected_colormap()
        if not selected_map:
            return

        nodes = self.node_editor.get_nodes()
        
        # 常にgradient形式として更新
        selected_map.map_type = 'gradient'
        selected_map.gradient_points = [ColorStop(pos=n['pos'], color=n['color']) for n in nodes]
        selected_map.colors.clear() # indexedデータはクリア
        
        self.gradient_preview.set_colormap(selected_map)

    def on_direct_edit_color_changed(self, pos, color):
        selected_map = self.get_selected_colormap()
        if not selected_map:
            return
        
        self.state_manager.save_state_for_undo()
        rgba = [color.red(), color.green(), color.blue(), color.alpha()]
        
        # indexedからgradientへの変換
        if selected_map.map_type == 'indexed':
            n = len(selected_map.colors)
            selected_map.gradient_points = [
                ColorStop(pos=i / (n - 1) if n > 1 else 0.0, color=c) for i, c in enumerate(selected_map.colors)
            ]
            selected_map.colors.clear()
            selected_map.map_type = 'gradient'

        selected_map.gradient_points.append(ColorStop(pos=pos, color=rgba))
        selected_map.gradient_points.sort(key=lambda p: p.pos)
        
        self.gradient_preview.set_colormap(selected_map)

    def on_node_selected(self):
        selected_items = self.node_editor.scene().selectedItems()
        if selected_items and isinstance(selected_items[0], NodeItem):
            self._selected_node = selected_items[0]
            rgba = self._selected_node.color_value
            self.node_color_edit.setText(f'#{rgba[0]:02X}{rgba[1]:02X}{rgba[2]:02X}{rgba[3]:02X}')
            self.node_pos_edit.setText(f'{self._selected_node.pos_value:.4f}')
        else:
            self._selected_node = None
            self.node_color_edit.clear()
            self.node_pos_edit.clear()
        self._update_color_picker_button()

    def on_node_color_edit(self):
        if not self._selected_node: return
        text = self.node_color_edit.text().lstrip('#')
        if len(text) == 6: text += 'FF'
        if len(text) == 8:
            try:
                rgba = [int(text[i:i+2], 16) for i in range(0, 8, 2)]
                self._selected_node.set_color(rgba)
                self.on_node_editor_changed(final_change=True)
                self._update_color_picker_button()
            except ValueError:
                pass # 不正な形式は無視

    def on_node_pos_edit(self):
        if not self._selected_node: return
        try:
            pos = max(0.0, min(1.0, float(self.node_pos_edit.text())))
            self._selected_node.set_pos_from_value(pos)
            self.on_node_editor_changed(final_change=True)
        except ValueError:
            pass # 不正な形式は無視

    def open_color_picker(self):
        if not self._selected_node: return
        initial_color = QColor(*self._selected_node.color_value)
        color = QColorDialog.getColor(initial_color, self, "色を選択")
        if color.isValid():
            rgba = [color.red(), color.green(), color.blue(), color.alpha()]
            self._selected_node.set_color(rgba)
            self.node_color_edit.setText(f'#{rgba[0]:02X}{rgba[1]:02X}{rgba[2]:02X}{rgba[3]:02X}')
            self.on_node_editor_changed(final_change=True)
            self._update_color_picker_button()

    def on_flip_horizontal(self):
        selected_map = self.get_selected_colormap()
        if not selected_map:
            ColormapUtils.show_error_message(self, "エラー", "カラーマップが選択されていません")
            return

        self.state_manager.save_state_for_undo()
        if selected_map.map_type == "gradient":
            for point in selected_map.gradient_points:
                point.pos = 1.0 - point.pos
            selected_map.gradient_points.sort(key=lambda p: p.pos)
        elif selected_map.map_type == "indexed":
            selected_map.colors.reverse()
        
        self.on_colormap_selected(self.colormap_list.currentItem(), None)

    # --- ユーティリティ ---
    def on_random_generate(self):
        params = ColormapUtils.get_random_generate_params(
            self, self.random_generate_max_count, self.random_generate_max_nodes
        )
        if not all(p is not None for p in params): return
        num_to_generate, map_type, min_nodes, max_nodes = params

        self.state_manager.save_state_for_undo()
        color_pack = self.state_manager.get_current_state()
        if color_pack is None:
            color_pack = ColorPack(pack_name="New Pack")
            self.state_manager.set_current_state(color_pack)

        for _ in range(num_to_generate):
            map_name = f"RandomMap{len(color_pack.maps) + 1}"
            if map_type == "gradient":
                num_nodes = random.randint(min_nodes, max_nodes)
                points = ColormapUtils.random_generate_colormap(num_nodes)
                new_map = Colormap(map_name=map_name, map_type='gradient', gradient_points=points)
            else: # indexed
                num_colors = random.randint(2, 256)
                colors = [[random.randint(0, 255) for _ in range(3)] + [255] for _ in range(num_colors)]
                new_map = Colormap(map_name=map_name, map_type='indexed', colors=colors)
            color_pack.maps.append(new_map)

        if num_to_generate > 0:
            self.ui_manager.update_ui_from_state(self.state_manager)
            self.colormap_list.setCurrentRow(len(color_pack.maps) - 1)

    def on_extract_from_image(self):
        params = ColormapUtils.get_extract_image_params(self, self.extract_image_max_maps)
        if not all(p is not None for p in params): return
        file_path, num_colors, num_maps = params

        self.state_manager.save_state_for_undo()
        color_pack = self.state_manager.get_current_state()
        if color_pack is None:
            color_pack = ColorPack(pack_name="New Pack")
            self.state_manager.set_current_state(color_pack)
            
        try:
            for _ in range(num_maps):
                points = ColormapUtils.extract_colors_from_image(file_path, num_colors)
                map_name = f"ImageMap{len(color_pack.maps) + 1}"
                new_map = Colormap(map_name=map_name, map_type='gradient', gradient_points=points)
                color_pack.maps.append(new_map)

            if num_maps > 0:
                self.ui_manager.update_ui_from_state(self.state_manager)
                self.colormap_list.setCurrentRow(len(color_pack.maps) - 1)
        except ImportError:
            ColormapUtils.show_error_message(self, "依存ライブラリ未インストール",
                                           "Pillow, scikit-learn, numpyが必要です。\n`pip install pillow scikit-learn numpy`")
        except Exception as e:
            ColormapUtils.show_error_message(self, "抽出失敗", f"画像から色抽出に失敗しました:\n{e}")

    def _update_color_picker_button(self):
        if self._selected_node:
            rgba = self._selected_node.color_value
            style = f"background-color: rgba({rgba[0]}, {rgba[1]}, {rgba[2]}, {rgba[3]/255}); border: 1px solid #ccc;"
        else:
            style = "background-color: #f0f0f0; border: 1px solid #ccc;"
        self.color_picker_button.setStyleSheet(style)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # pack_name, map_name はテスト用に渡すことができます
    # editor = ColormapEditor(pack_name="classic", map_name="Classic")
    editor = ColormapEditor()
    editor.show()
    sys.exit(app.exec())
