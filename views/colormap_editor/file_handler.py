import json
import os
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
import re

from models.colormap import ColorPack
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class ColormapFileHandler:
    """カラーマップファイルの読み書きを処理するクラス"""

    def __init__(self, parent):
        self.parent = parent

    def open_file(self) -> ColorPack | None:
        """ファイルダイアログを開き、カラーパックファイルを読み込む"""
        project_root = os.getcwd()
        colorpacks_dir = os.path.join(project_root, 'plugins', 'colorpacks')
        if not os.path.exists(colorpacks_dir):
            colorpacks_dir = project_root
        
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent, "カラーパックを開く", colorpacks_dir, "JSON Files (*.json)"
        )

        if not file_path:
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            color_pack = ColorPack.from_dict(data)
            color_pack.file_path = file_path  # 動的にファイルパス属性を追加
            return color_pack
        except Exception as e:
            self.show_error_message(f"ファイル読み込みに失敗しました:\n{e}")
            return None

    def save_file_as(self, color_pack: ColorPack) -> ColorPack | None:
        """名前を付けて保存ダイアログを開き、カラーパックを保存する"""
        if not color_pack:
            return None

        current_pack_name = color_pack.pack_name
        new_pack_name, ok = QInputDialog.getText(
            self.parent, "カラーパック名の設定", "新しいカラーパック名:", text=current_pack_name
        )

        if not (ok and new_pack_name):
            return None

        safe_new_pack_name = re.sub(r'[\\/:"*?<>|]+', '_', new_pack_name)
        
        if hasattr(color_pack, 'file_path') and color_pack.file_path:
            dir_path = os.path.dirname(color_pack.file_path)
        else:
            project_root = os.getcwd()
            dir_path = os.path.join(project_root, 'plugins', 'colorpacks')

        suggested_filename = os.path.join(dir_path, f"{safe_new_pack_name}.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self.parent, "名前を付けて保存", suggested_filename, "JSON Files (*.json)"
        )

        if file_path:
            color_pack.pack_name = new_pack_name
            if self.save_to_file(file_path, color_pack):
                color_pack.file_path = file_path
                return color_pack
        return None

    def save_to_file(self, file_path: str, color_pack: ColorPack) -> bool:
        """指定されたパスにColorPackデータをカスタムフォーマットで書き込む"""
        try:
            data_dict = color_pack.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('{\n')
                f.write(f'    "pack_name": {json.dumps(data_dict["pack_name"], ensure_ascii=False)},\n')
                f.write('    "maps": [\n')
                num_maps = len(data_dict["maps"])
                for map_index, map_data in enumerate(data_dict["maps"]):
                    f.write('        {\n')
                    keys = list(map_data.keys())
                    for i, key in enumerate(keys):
                        f.write(f'            \"{key}\": ')
                        if key == "colors":
                            colors = map_data[key]
                            num_colors_inner = len(colors)
                            f.write('[\n')
                            for j, color in enumerate(colors):
                                if j % 5 == 0: f.write(' ' * 16)
                                f.write(f'[{color[0]},{color[1]},{color[2]},{color[3]}]')
                                if j < num_colors_inner - 1: f.write(',')
                                if (j + 1) % 5 == 0 and j < num_colors_inner - 1: f.write('\n')
                            f.write('\n' + ' ' * 12 + ']')
                        elif key == "gradient_points":
                            points = map_data[key]
                            num_points_ = len(points)
                            f.write('[\n')
                            for j, point in enumerate(points):
                                # JSON準拠のフォーマットで出力
                                point_str = json.dumps(point, ensure_ascii=False)
                                f.write(' ' * 16 + point_str)
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
            
            self.show_success_message(f"ファイルを保存しました。\n{file_path}")
            return True
        except Exception as e:
            self.show_error_message(f"ファイル保存に失敗しました:\n{e}")
            logger.log(f"[ColormapFileHandler._save_to_file] Error: {e}", level="ERROR")
            return False

    def show_error_message(self, message: str):
        QMessageBox.warning(self.parent, "エラー", message)

    def show_success_message(self, message: str):
        QMessageBox.information(self.parent, "保存完了", message)
