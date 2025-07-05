import sys
import json
from pathlib import Path

# PyQt6の必要なモジュールをインポート
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLineEdit, QLabel, QListWidget,
    QCheckBox, QSpinBox, QTextEdit, QMessageBox, QFrame, QSplitter
)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QLinearGradient

# --- 変換処理のコアロジック (変更なし) ---
def hex_to_rgba(hex_color: str) -> list[int] | None:
    """16進数カラーコードをRGBAリストに変換します。"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        try:
            rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
            return rgb + [255]  # Alpha値を255で追加
        except ValueError:
            return None
    return None

# --- 色プレビューウィジェット ---
class ColorPreviewWidget(QWidget):
    """色のリストやグラデーションを視覚的に表示するウィジェット"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(40)
        self.setMaximumHeight(80)
        self.colors_data = None # {"type": "colors" or "gradient", "data": ...}

    def set_data(self, colors_data):
        """プレビューデータを設定して再描画をトリガーします。"""
        self.colors_data = colors_data
        self.update()

    def clear(self):
        """プレビューをクリアします。"""
        self.colors_data = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        if not self.colors_data or not self.colors_data.get("data"):
            painter.fillRect(rect, self.palette().color(self.backgroundRole()).lighter(120))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Data")
            return

        data_type = self.colors_data.get("type")
        data = self.colors_data.get("data")

        if data_type == "colors":
            num_colors = len(data)
            if num_colors == 0: return
            rect_width = rect.width() / num_colors
            for i, color_rgba in enumerate(data):
                color = QColor(*color_rgba)
                painter.fillRect(int(i * rect_width), 0, int(rect_width + 1), rect.height(), color)

        elif data_type == "gradient":
            gradient = QLinearGradient(0, 0, rect.width(), 0)
            for point in data:
                pos = point.get("pos", 0.0)
                color_rgba = point.get("color", [0,0,0,255])
                gradient.setColorAt(pos, QColor(*color_rgba))
            painter.fillRect(rect, gradient)

class ConversionWorker(QObject):
    """変換処理をバックグラウンドで実行するためのワーカクラス"""
    log_message = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, input_files, output_file, pack_name, use_gradient, num_points):
        super().__init__()
        self.input_files = input_files
        self.output_file = output_file
        self.pack_name = pack_name
        self.use_gradient = use_gradient
        self.num_points = num_points
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        """変換処理の本体"""
        output_data = {"pack_name": self.pack_name, "maps": []}
        self.log_message.emit(f"合計 {len(self.input_files)} 個のファイルを処理します...")

        for file_path_str in self.input_files:
            if not self.is_running:
                self.log_message.emit("処理が中断されました。")
                break

            file_path = Path(file_path_str)
            self.log_message.emit(f"  - 処理中: {file_path.name}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                map_name, hex_colors = data.get("name"), data.get("colors")
                if not map_name or not isinstance(hex_colors, list):
                    self.log_message.emit(f"    -> 警告: '{file_path.name}' は期待される形式ではありません。スキップします。")
                    continue

                valid_rgb_colors = [rgb for rgb in (hex_to_rgba(hc) for hc in hex_colors) if rgb is not None]
                if not valid_rgb_colors:
                    self.log_message.emit(f"    -> 警告: '{file_path.name}' から有効な色を読み込めませんでした。スキップします。")
                    continue

                num_colors = len(valid_rgb_colors)

                if self.use_gradient and num_colors > self.num_points and self.num_points >= 2:
                    self.log_message.emit(f"    -> グラデーション形式に変換します ({self.num_points} ポイント)。")
                    gradient_points = []
                    for i in range(self.num_points):
                        raw_idx = i * (num_colors - 1) / (self.num_points - 1)
                        index = min(int(round(raw_idx)), num_colors - 1)
                        if i > 0 and index == gradient_points[-1]['_index']: continue
                        pos = index / (num_colors - 1)
                        point = {"pos": round(pos, 5), "color": valid_rgb_colors[index], "_index": index}
                        gradient_points.append(point)
                    for p in gradient_points: del p['_index']
                    new_map = {
                        "map_name": map_name, "type": "gradient",
                        "gradient_points": gradient_points, "num_colors": num_colors
                    }
                else:
                    if self.use_gradient:
                        self.log_message.emit(f"    -> 色数が少ないため、通常形式で出力します。")
                    new_map = {"map_name": map_name, "colors": valid_rgb_colors}
                output_data["maps"].append(new_map)

            except Exception as e:
                self.log_message.emit(f"    -> エラー: '{file_path.name}' の処理中にエラー発生: {e}。スキップします。")

        if not self.is_running:
            self.finished.emit()
            return

        if not output_data["maps"]:
            self.log_message.emit("\n有効なカラーマップが一つも作成されませんでした。")
            self.finished.emit()
            return

        try:
            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('{\n')
                f.write(f'    "pack_name": {json.dumps(output_data["pack_name"], ensure_ascii=False)},\n')
                f.write('    "maps": [\n')
                num_maps = len(output_data["maps"])
                for map_index, map_data in enumerate(output_data["maps"]):
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
                                f.write(' ' * 16 + json.dumps(point))
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
            self.log_message.emit(f"\n✅ 成功: カラーパックを '{output_path.name}' に保存しました。")
        except Exception as e:
            self.log_message.emit(f"\n❌ エラー: 出力ファイル '{self.output_file}' の書き込みに失敗しました: {e}")
        finally:
            self.finished.emit()

# --- GUIのメインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Color Pack Converter")
        self.setGeometry(100, 100, 800, 700)
        self.thread = None
        self.worker = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- スプリッターでUIを分割 ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # --- 左側: コントロールパネル ---
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        main_splitter.addWidget(control_panel)

        # 1. 入力ファイルセクション
        control_layout.addWidget(QLabel("1. Input JSON Files:"))
        input_buttons_layout = QVBoxLayout()
        select_files_button = QPushButton("Select Files...")
        select_folder_button = QPushButton("Select Folder...")
        clear_list_button = QPushButton("Clear List")
        input_buttons_layout.addWidget(select_files_button)
        input_buttons_layout.addWidget(select_folder_button)
        input_buttons_layout.addWidget(clear_list_button)
        input_buttons_layout.addStretch()

        input_layout = QHBoxLayout()
        self.file_list_widget = QListWidget()
        input_layout.addWidget(self.file_list_widget, 1)
        input_layout.addLayout(input_buttons_layout)
        control_layout.addLayout(input_layout)

        # 2. 出力ファイルセクション
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        save_as_button = QPushButton("Save As...")
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(save_as_button)
        control_layout.addWidget(QLabel("2. Output Color Pack File:"))
        control_layout.addLayout(output_layout)

        # 3. 設定セクション
        control_layout.addWidget(QLabel("3. Settings:"))
        self.pack_name_edit = QLineEdit()
        self.pack_name_edit.setPlaceholderText("Enter a name for the color pack")
        control_layout.addWidget(self.pack_name_edit)

        gradient_layout = QHBoxLayout()
        self.gradient_checkbox = QCheckBox("Convert to Gradient")
        self.gradient_points_label = QLabel("Points:")
        self.gradient_points_spinbox = QSpinBox()
        self.gradient_points_spinbox.setRange(2, 256)
        self.gradient_points_spinbox.setValue(8)
        gradient_layout.addWidget(self.gradient_checkbox)
        gradient_layout.addWidget(self.gradient_points_label)
        gradient_layout.addWidget(self.gradient_points_spinbox)
        gradient_layout.addStretch()
        control_layout.addLayout(gradient_layout)

        self.gradient_points_label.setEnabled(False)
        self.gradient_points_spinbox.setEnabled(False)

        # 4. 実行ボタン
        action_layout = QHBoxLayout()
        self.preview_button = QPushButton("Update Preview")
        self.convert_button = QPushButton("Convert")
        self.convert_button.setStyleSheet("font-size: 16px; padding: 10px;")
        action_layout.addStretch()
        action_layout.addWidget(self.preview_button)
        action_layout.addWidget(self.convert_button)
        control_layout.addLayout(action_layout)

        # 5. ログ表示セクション
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        control_layout.addWidget(line)
        control_layout.addWidget(QLabel("Log:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        control_layout.addWidget(self.log_area)

        # --- 右側: プレビューパネル ---
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        main_splitter.addWidget(preview_panel)

        preview_layout.addWidget(QLabel("<b>Preview (Before)</b>"))
        self.before_preview = ColorPreviewWidget()
        preview_layout.addWidget(self.before_preview)

        preview_layout.addWidget(QLabel("<b>Preview (After)</b>"))
        self.after_preview = ColorPreviewWidget()
        preview_layout.addWidget(self.after_preview)
        preview_layout.addStretch()

        # --- スプリッターの初期サイズを設定 ---
        main_splitter.setSizes([450, 350])

        # --- イベント（シグナルとスロット）の接続 ---
        select_files_button.clicked.connect(self.select_input_files)
        select_folder_button.clicked.connect(self.select_input_folder)
        clear_list_button.clicked.connect(self.clear_input_list)
        save_as_button.clicked.connect(self.select_output_file)
        self.gradient_checkbox.stateChanged.connect(self.toggle_gradient_controls)
        self.gradient_points_spinbox.valueChanged.connect(self.update_previews)
        self.convert_button.clicked.connect(self.start_conversion)
        self.preview_button.clicked.connect(self.update_previews)
        self.file_list_widget.currentItemChanged.connect(self.update_previews)

    def update_previews(self):
        """変換前後のプレビューを更新します。"""
        current_item = self.file_list_widget.currentItem()
        if not current_item:
            self.before_preview.clear()
            self.after_preview.clear()
            return

        file_path_str = current_item.text()
        file_path = Path(file_path_str)
        rgba_colors = []

        # --- 変換前プレビューの更新 ---
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            hex_colors = data.get("colors", [])
            if not isinstance(hex_colors, list):
                raise ValueError("`colors` field is not a list.")

            rgba_colors = [rgb for rgb in (hex_to_rgba(hc) for hc in hex_colors) if rgb is not None]
            if not rgba_colors:
                raise ValueError("No valid colors found in file.")

            self.before_preview.set_data({"type": "colors", "data": rgba_colors})
            self.add_log(f"プレビュー (変換前): {file_path.name}")

        except Exception as e:
            self.add_log(f"プレビュー(前)エラー: {e}")
            self.before_preview.clear()
            self.after_preview.clear()
            return

        # --- 変換後プレビューの更新 ---
        use_gradient = self.gradient_checkbox.isChecked()
        num_points = self.gradient_points_spinbox.value()
        num_colors = len(rgba_colors)

        after_data = None
        if use_gradient and num_colors >= 2 and num_colors > num_points:
            gradient_points = []
            for i in range(num_points):
                raw_idx = i * (num_colors - 1) / (num_points - 1)
                index = min(int(round(raw_idx)), num_colors - 1)
                # 変換処理と同じロジックで重複をチェック
                if i > 0 and index == gradient_points[-1]['_index']:
                    continue
                pos = index / (num_colors - 1)
                point = {"pos": round(pos, 5), "color": rgba_colors[index], "_index": index}
                gradient_points.append(point)

            # プレビューに渡す前に一時的な '_index' キーを削除
            final_gradient_points = [{k: v for k, v in p.items() if k != '_index'} for p in gradient_points]

            after_data = {"type": "gradient", "data": final_gradient_points}
            self.add_log(f"プレビュー (変換後): グラデーション ({len(final_gradient_points)}ポイント)")
        else:
            after_data = {"type": "colors", "data": rgba_colors}
            if use_gradient:
                self.add_log(f"プレビュー (変換後): 通常形式 (色数が少ないため)")
            else:
                self.add_log(f"プレビュー (変換後): 通常形式")

        self.after_preview.set_data(after_data)


    def add_files_to_list(self, files_to_add):
        existing_files = {self.file_list_widget.item(i).text() for i in range(self.file_list_widget.count())}
        new_files = [str(f) for f in files_to_add if str(f) not in existing_files]
        if new_files:
            self.file_list_widget.addItems(new_files)
            self.add_log(f"{len(new_files)} 個のファイルを追加しました。")
            if self.file_list_widget.count() > 0 and self.file_list_widget.currentRow() == -1:
                self.file_list_widget.setCurrentRow(0)
        else:
            self.add_log("新しいファイルは追加されませんでした（重複または選択なし）。")

    def clear_input_list(self):
        self.file_list_widget.clear()
        self.before_preview.clear()
        self.after_preview.clear()
        self.add_log("入力リストをクリアしました。")

    def select_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Color Definition Files", "", "JSON Files (*.json);;All Files (*)"
        )
        if files:
            self.add_files_to_list(files)

    def select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Color Files")
        if folder:
            self.add_log(f"フォルダ '{folder}' を検索中...")
            folder_path = Path(folder)
            json_files = list(folder_path.glob('*.json'))
            if json_files:
                self.add_files_to_list(json_files)
            else:
                self.add_log(f"-> フォルダ内に .json ファイルが見つかりませんでした。")

    def select_output_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Color Pack As", "", "JSON Files (*.json)")
        if file:
            self.output_path_edit.setText(file)

    def toggle_gradient_controls(self, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        self.gradient_points_label.setEnabled(is_checked)
        self.gradient_points_spinbox.setEnabled(is_checked)
        self.update_previews()

    def add_log(self, message):
        self.log_area.append(message)

    def on_conversion_finished(self):
        self.convert_button.setEnabled(True)
        self.preview_button.setEnabled(True)
        self.add_log("--- 処理完了 ---")
        QMessageBox.information(self, "Finished", "Conversion process has finished.")
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None

    def start_conversion(self):
        input_files = [self.file_list_widget.item(i).text() for i in range(self.file_list_widget.count())]
        output_file = self.output_path_edit.text()
        pack_name = self.pack_name_edit.text()

        if not input_files:
            QMessageBox.warning(self, "Input Error", "Please select at least one input file.")
            return
        if not output_file:
            QMessageBox.warning(self, "Input Error", "Please specify an output file path.")
            return
        if not pack_name:
            QMessageBox.warning(self, "Input Error", "Please enter a pack name.")
            return

        self.log_area.clear()
        self.add_log("--- 処理開始 ---")
        self.convert_button.setEnabled(False)
        self.preview_button.setEnabled(False)

        self.thread = QThread()
        self.worker = ConversionWorker(
            input_files=input_files, output_file=output_file, pack_name=pack_name,
            use_gradient=self.gradient_checkbox.isChecked(), num_points=self.gradient_points_spinbox.value()
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_conversion_finished)
        self.worker.log_message.connect(self.add_log)
        self.thread.start()

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
