import os
import sys
from pathlib import Path
from functools import partial
from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSlider, QSpinBox, QLabel, QFormLayout, QVBoxLayout,
    QHBoxLayout, QGroupBox, QFileDialog, QDialogButtonBox,
    QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize
from PyQt6.QtWidgets import QMessageBox # accept時のエラー表示用

from settings_manager import SettingsManager # SettingsManager をインポート
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class HighResOutputDialog(QDialog):
    """高解像度画像出力の設定を行うダイアログクラスです。

    ファイル形式、解像度、反復回数、アンチエイリアスなどの設定をユーザーに提供し、
    設定値を取得する機能も持ちます。SettingsManagerと連携して設定の読み書きを行います。
    """
    SETTINGS_SECTION_NAME = "high_res_export_defaults" # 設定セクションキー

    def __init__(self, settings_manager: SettingsManager,
                 current_dialog_defaults: dict | None = None, # 以前の current_export_settings
                 current_view_params: dict | None = None,
                 parent=None):
        """HighResOutputDialogを初期化します。

        Args:
            settings_manager (SettingsManager): 設定の読み書きを行うためのSettingsManagerインスタンス。
            current_dialog_defaults (dict | None, optional): ダイアログの初期値として使用する設定の辞書。
                                                              保存された設定や前回使用された設定を反映します。
            current_view_params (dict | None, optional): 現在のビュー（例: メインウィンドウの描画エリア）の
                                                         パラメータ。プリセットの「現在の表示」などに使用されます。
            parent (QWidget, optional): 親ウィジェット。
        """
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("高解像度出力設定")
        self.setMinimumWidth(550)
        # current_dialog_defaults は、保存された設定が見つからない場合に設定する値、
        # または保存された設定を適用する前のベースとして使用する値です。
        # これらはアプリの一般的なデフォルト値、または最後に *使用された* (必ずしも保存されていない) 設定である可能性があります。
        self.dialog_defaults = current_dialog_defaults if current_dialog_defaults else {}
        self.current_view_params = current_view_params if current_view_params else {}

        initial_width_px = self.current_view_params.get('image_width_px', 800)
        initial_height_px = self.current_view_params.get('image_height_px', 600)
        self.source_aspect_ratio = initial_width_px / initial_height_px if initial_height_px > 0 else 16.0/9.0
        self.keep_aspect_ratio_enabled = True
        self.updates_enabled = True # 寸法変更時の再帰的更新を管理するため

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._create_file_group())
        main_layout.addWidget(self._create_resolution_group())
        main_layout.addWidget(self._create_options_group())
        main_layout.addWidget(self._create_buttons())

        self._connect_signals()
        self._load_settings() # 保存された設定を読み込み、適用する
        self._update_memory_usage_label()

    def _create_file_group(self) -> QGroupBox: # 変更なし、コンテキスト用
        group = QGroupBox("ファイル設定")
        layout = QFormLayout()

        self.filepath_edit = QLineEdit()
        self.filepath_edit.setReadOnly(True)
        browse_button = QPushButton("参照...")
        browse_button.clicked.connect(self._browse_filepath) # 早期アクセスのためにここで接続
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.filepath_edit)
        path_layout.addWidget(browse_button)
        layout.addRow(QLabel("保存場所:"), path_layout)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "TIFF", "BMP"])
        layout.addRow(QLabel("ファイル形式:"), self.format_combo)

        self.png_transparent_check = QCheckBox("背景を透過する (PNGのみ)")
        layout.addRow(self.png_transparent_check)

        jpeg_quality_layout = QHBoxLayout()
        self.jpeg_quality_label = QLabel("JPEG品質:")
        self.jpeg_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.jpeg_quality_slider.setRange(1, 100)
        self.jpeg_quality_slider.setValue(90)
        self.jpeg_quality_value_label = QLabel(f"{self.jpeg_quality_slider.value()}%")
        self.jpeg_quality_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        jpeg_quality_layout.addWidget(self.jpeg_quality_slider)
        jpeg_quality_layout.addWidget(self.jpeg_quality_value_label)
        self.jpeg_quality_widgets = [self.jpeg_quality_label, self.jpeg_quality_slider, self.jpeg_quality_value_label] # このリストを保持
        layout.addRow(self.jpeg_quality_label, jpeg_quality_layout)

        group.setLayout(layout)
        return group

    def _create_resolution_group(self) -> QGroupBox: # 変更なし、コンテキスト用
        group = QGroupBox("解像度設定")
        layout = QFormLayout()
        self.preset_combo = QComboBox()
        # self.presets は _load_settings で初期化されるか、current_view_params に基づいて初期化されます。
        # self.presets が完全に定義された後にアイテムを設定する方が良いです。
        layout.addRow(QLabel("プリセット:"), self.preset_combo)

        self.width_spinbox = QSpinBox(); self.width_spinbox.setRange(1, 32768); self.width_spinbox.setSuffix(" px")
        self.height_spinbox = QSpinBox(); self.height_spinbox.setRange(1, 32768); self.height_spinbox.setSuffix(" px")
        res_size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.width_spinbox.setSizePolicy(res_size_policy); self.height_spinbox.setSizePolicy(res_size_policy)

        dims_layout = QHBoxLayout()
        dims_layout.addWidget(self.width_spinbox); dims_layout.addWidget(QLabel("x")); dims_layout.addWidget(self.height_spinbox)
        layout.addRow(QLabel("サイズ (幅x高):"), dims_layout)

        self.aspect_ratio_check = QCheckBox("現在のアスペクト比を維持")
        # self.aspect_ratio_check.setChecked(True) # _load_settings で設定
        layout.addRow(self.aspect_ratio_check)

        self.memory_usage_label = QLabel("予測メモリ使用量: N/A MB")
        layout.addRow(self.memory_usage_label)

        group.setLayout(layout)
        return group

    def _create_options_group(self) -> QGroupBox: # 変更なし、コンテキスト用
        group = QGroupBox("出力オプション")
        layout = QFormLayout()
        self.iterations_spinbox = QSpinBox(); self.iterations_spinbox.setRange(10, 1000000)
        layout.addRow(QLabel("最大反復回数:"), self.iterations_spinbox)
        self.antialiasing_combo = QComboBox()
        self.antialiasing_combo.addItems(["なし", "2x2 SSAA", "3x3 SSAA", "4x4 SSAA"]) # SSAA = スーパーサンプリングアンチエイリアス
        layout.addRow(QLabel("アンチエイリアス:"), self.antialiasing_combo)
        group.setLayout(layout)
        return group

    def _create_buttons(self) -> QDialogButtonBox:
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("出力開始")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        return button_box

    def _connect_signals(self):
        """ダイアログ内のウィジェットのシグナルを対応するスロットに接続します。"""
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.jpeg_quality_slider.valueChanged.connect(self._on_jpeg_quality_changed)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        # partial を使用して、どの寸法が変更されたかを渡す
        self.width_spinbox.valueChanged.connect(partial(self._on_dimension_changed, "width"))
        self.height_spinbox.valueChanged.connect(partial(self._on_dimension_changed, "height"))
        self.aspect_ratio_check.stateChanged.connect(self._on_aspect_ratio_toggled)

    def _load_settings(self): # _load_initial_settings から名前変更
        """保存された設定またはデフォルト値をダイアログの各ウィジェットに読み込み、表示します。"""
        self.updates_enabled = False # 読み込み中は更新を無効化

        saved_settings = self.settings_manager.get_setting(self.SETTINGS_SECTION_NAME, {})

        # ファイル設定 - 保存された設定、次に dialog_defaults、次にハードコードされたデフォルトを使用
        default_file_path_base = self.dialog_defaults.get('filepath', Path.home() / "fractal_render")
        file_format = saved_settings.get('format', self.dialog_defaults.get('format', 'PNG'))
        self.filepath_edit.setText(saved_settings.get('filepath', str(default_file_path_base) + f".{file_format.lower()}"))
        self.format_combo.setCurrentText(file_format)
        self.png_transparent_check.setChecked(saved_settings.get('png_transparent', self.dialog_defaults.get('png_transparent', False)))
        self.jpeg_quality_slider.setValue(saved_settings.get('jpeg_quality', self.dialog_defaults.get('jpeg_quality', 90)))
        # 解像度プリセット - self.presets が定義されている必要がある
        self.presets = {
            "現在の表示": (self.current_view_params.get('image_width_px',800), self.current_view_params.get('image_height_px',600)),
            "HD (1280x720)": (1280, 720), "FHD (1920x1080)": (1920, 1080),
            "4K UHD (3840x2160)": (3840, 2160), "8K UHD (7680x4320)": (7680, 4320),
            "カスタム": (-1, -1)
        }
        self.preset_combo.blockSignals(True) # 設定中はブロック
        self.preset_combo.clear()
        self.preset_combo.addItems(self.presets.keys())
        self.preset_combo.blockSignals(False)

        # 解像度設定を読み込み
        # 保存された幅/高さをプリセットに一致させてみてください。それ以外の場合はカスタムに設定します
        saved_w = saved_settings.get('width', self.presets["現在の表示"][0])
        saved_h = saved_settings.get('height', self.presets["現在の表示"][1])
        current_preset_text = "カスタム" # 一致しない場合はカスタムをデフォルトとする
        for name, (pw, ph) in self.presets.items():
            if pw == saved_w and ph == saved_h and name != "カスタム":
                current_preset_text = name
                break

        self.preset_combo.setCurrentText(current_preset_text) # これにより _on_preset_changed がトリガーされる
        # カスタムの場合、_on_preset_changed は幅/高さが既に正しい場合は設定しない可能性がある
        if current_preset_text == "カスタム":
            self.width_spinbox.setValue(saved_w)
            self.height_spinbox.setValue(saved_h) # アスペクト比が維持されている場合、これにより _on_dimension_changed がトリガーされる

        self.aspect_ratio_check.setChecked(saved_settings.get('keep_aspect_ratio', True))

        # 出力オプション
        default_iters = self.current_view_params.get('max_iterations', 100) * 2
        self.iterations_spinbox.setValue(saved_settings.get('iterations', default_iters))
        self.antialiasing_combo.setCurrentText(saved_settings.get('antialiasing', 'なし'))

        self._on_format_changed(self.format_combo.currentText())
        self.updates_enabled = True
        self._update_memory_usage_label() # すべての解像度設定が安定したら一度更新

    @pyqtSlot()
    def _browse_filepath(self):
        """「参照...」ボタンがクリックされたときに呼び出され、ファイル保存ダイアログを開いて保存パスをユーザーに選択させます。"""
        current_path = self.filepath_edit.text()
        if not current_path:
            current_path = os.getcwd()

        format_filter = ""
        selected_format = self.format_combo.currentText()
        if selected_format == "PNG": format_filter = "PNG Files (*.png)"
        elif selected_format == "JPEG": format_filter = "JPEG Files (*.jpg *.jpeg)"
        elif selected_format == "TIFF": format_filter = "TIFF Files (*.tif *.tiff)"
        elif selected_format == "BMP": format_filter = "BMP Files (*.bmp)"
        all_filters = "All Files (*)"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "名前を付けて保存", current_path,
            f"{format_filter};;{all_filters}" if format_filter else all_filters
        )
        if filepath:
            self.filepath_edit.setText(filepath)

    @pyqtSlot(str)
    def _on_format_changed(self, format_str: str):
        is_png = (format_str == "PNG")
        is_jpeg = (format_str == "JPEG")
        self.png_transparent_check.setEnabled(is_png)
        if not is_png: self.png_transparent_check.setChecked(False)
        for widget in self.jpeg_quality_widgets:
            widget.setEnabled(is_jpeg)
        # ユーザーが入力していない場合、パス内のファイル拡張子を更新
        current_path = self.filepath_edit.text()
        if current_path:
            name, ext = os.path.splitext(current_path)
            new_ext = f".{format_str.lower()}"
            if ext.lower() in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'] and ext.lower() != new_ext:
                 self.filepath_edit.setText(name + new_ext)
            elif not ext: # 拡張子がなかった場合
                 self.filepath_edit.setText(current_path + new_ext)

    @pyqtSlot(int)
    def _on_jpeg_quality_changed(self, value: int):
        """JPEG品質スライダーの値が変更されたときに呼び出され、品質表示ラベルを更新します。"""
        self.jpeg_quality_value_label.setText(f"{value}%")

    @pyqtSlot(str)
    def _on_preset_changed(self, preset_text: str):
        """解像度プリセットコンボボックスの選択が変更されたときに呼び出されます。

        選択されたプリセットに応じて幅と高さの入力フィールドを更新し、編集可否を切り替えます。
        """
        if preset_text == "カスタム":
            self.width_spinbox.setEnabled(True)
            self.height_spinbox.setEnabled(True)
        else:
            width, height = self.presets.get(preset_text, (0,0))
            if width > 0 and height > 0 :
                self.width_spinbox.blockSignals(True)
                self.height_spinbox.blockSignals(True)
                self.width_spinbox.setValue(width)
                self.height_spinbox.setValue(height)
                self.width_spinbox.blockSignals(False)
                self.height_spinbox.blockSignals(False)
                self.width_spinbox.setEnabled(False) # または aspect_ratio_check に基づく
                self.height_spinbox.setEnabled(False)
                self._update_memory_usage_label() # 新しいプリセット用に更新

        # アスペクト比が維持されている場合、プリセットを変更すると幅/高さが無効になるか、
        # 比率を維持しながらカスタム編集が許可されている場合はそのいずれかが無効になるようにする必要があります。
        # 簡単にするために、プリセットは直接の幅/高さ編集を無効にします。「カスタム」はそれらを有効にします。
        self._on_aspect_ratio_toggled(self.aspect_ratio_check.isChecked())


    @pyqtSlot(int) # state は QCheckBox.stateChanged の int です
    def _on_aspect_ratio_toggled(self, state_int: int):
        """「アスペクト比を維持」チェックボックスの状態が変更されたときに呼び出されます。

        アスペクト比維持の有効/無効状態を更新します。
        """
        self.keep_aspect_ratio_enabled = (state_int == Qt.CheckState.Checked.value)
        # 「カスタム」プリセットでアスペクト比がチェックされている場合、幅/高さのいずれかを無効にする必要があります。
        # ここでは、ユーザーが一方を変更すると、チェックされていればもう一方が追従すると仮定します。
        # プリセットが「カスタム」でない場合、幅/高さは通常 _on_preset_changed によって無効にされます。
        if self.preset_combo.currentText() == "カスタム":
             self.width_spinbox.setEnabled(True) # カスタムでは両方有効、アスペクトは _on_dimension_changed で処理
             self.height_spinbox.setEnabled(True)


    @pyqtSlot(str) # 引数 'changed_source' は "width" または "height" になります
    def _on_dimension_changed(self, changed_source: str):
        """幅または高さのスピンボックスの値が変更されたときに呼び出されます。

        「アスペクト比を維持」が有効な場合、もう一方の寸法を自動的に更新します。
        また、プリセットを「カスタム」に切り替えます。
        引数 `changed_source` は "width" または "height" を取ります。
        """
        if not self.keep_aspect_ratio_enabled or not self.updates_enabled: return

        self.updates_enabled = False # 再帰的な更新を防ぐ

        w_box = self.width_spinbox
        h_box = self.height_spinbox

        if changed_source == "width":
            new_width = w_box.value()
            new_height = int(round(new_width / self.source_aspect_ratio))
            if h_box.value() != new_height: h_box.setValue(new_height)
        elif changed_source == "height":
            new_height = h_box.value()
            new_width = int(round(new_height * self.source_aspect_ratio))
            if w_box.value() != new_width: w_box.setValue(new_width)

        if self.preset_combo.currentText() != "カスタム":
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText("カスタム") # 寸法が変更されたため、カスタムになりました
            self.preset_combo.blockSignals(False)
            self.width_spinbox.setEnabled(True) # カスタム編集用に有効化
            self.height_spinbox.setEnabled(True)

        self._update_memory_usage_label()
        self.updates_enabled = True


    def _update_memory_usage_label(self):
        """現在の解像度とアンチエイリアス設定に基づいて、予測されるメモリ使用量を計算し、ラベルに表示します。"""
        width = self.width_spinbox.value(); height = self.height_spinbox.value()
        bytes_per_pixel = 4 # RGBA
        ssaa_text = self.antialiasing_combo.currentText(); ssaa_factor = 1
        if "SSAA" in ssaa_text and ssaa_text[0].isdigit(): ssaa_factor = int(ssaa_text[0])**2
        mem_bytes = width * height * bytes_per_pixel * ssaa_factor
        mem_mb = mem_bytes / (1024 * 1024)
        self.memory_usage_label.setText(f"予測メモリ使用量: {mem_mb:.2f} MB")

    def accept(self): # 設定を保存するために accept をオーバーライド
        """「出力開始」ボタンが押されたとき、またはダイアログが承認されたときに呼び出されます。

        現在のUI設定を保存し、ダイアログを閉じます。ファイルパスが未指定の場合は警告を表示します。
        """
        current_settings = self.get_export_settings()
        if not current_settings.get('filepath'):
            QMessageBox.warning(self, "入力エラー", "ファイルパスを指定してください。")
            return # ダイアログが閉じるのを防ぐ

        self.settings_manager.set_setting(self.SETTINGS_SECTION_NAME, current_settings)
        super().accept()


    def get_export_settings(self) -> dict:
        """現在のダイアログのUI設定値を取得し、辞書として返します。

        アンチエイリアス設定は、エンジンが期待する係数 (`antialiasing_factor`) に変換されます。

        Returns:
            dict: エクスポート設定を含む辞書。
        """
        # UIからすべての関連設定が収集されていることを確認する
        s = {
            'filepath': self.filepath_edit.text(),
            'format': self.format_combo.currentText(),
            'png_transparent': self.png_transparent_check.isChecked(), # チェック状態は問題なし
            'jpeg_quality': self.jpeg_quality_slider.value(),
            'width': self.width_spinbox.value(),
            'height': self.height_spinbox.value(),
            'keep_aspect_ratio': self.aspect_ratio_check.isChecked(),
            'iterations': self.iterations_spinbox.value(),
            'antialiasing': self.antialiasing_combo.currentText()
        }
        # アンチエイリアステキストをエンジン用の係数に変換
        aa_text = s['antialiasing']
        if "SSAA" in aa_text and aa_text[0].isdigit(): s['antialiasing_factor'] = int(aa_text[0])
        else: s['antialiasing_factor'] = 1
        return s

    # updates_enabled のカスタム __setattr__ を削除し、明示的な呼び出しまたはシグナルブロッキングを使用。

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # テスト用のダミー設定マネージャーを作成
    # 実際のアプリでは、これは MainWindow/Application から渡されます
    test_settings_file = "dialog_test_settings.json"
    settings_mgr = SettingsManager(settings_filename=test_settings_file)

    # いくつかの保存された設定をシミュレート
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.filepath", str(Path.home() / "my_fractal.png"))
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.format", "PNG")
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.width", 2000)
    settings_mgr.set_setting(f"{HighResOutputDialog.SETTINGS_SECTION_NAME}.iterations", 300)


    dummy_dialog_defaults = {'filepath': str(Path.home()/"default_export.png"), 'format': 'JPEG',
                             'width':1024, 'height':768, 'iterations': 150,
                             'keep_aspect_ratio': False, 'jpeg_quality': 80}
    dummy_view_params = {'max_iterations': 200, 'image_width_px': 800, 'image_height_px': 600}

    dialog = HighResOutputDialog(settings_manager=settings_mgr,
                                 current_dialog_defaults=dummy_dialog_defaults,
                                 current_view_params=dummy_view_params)

    if dialog.exec():
        final_settings = dialog.get_export_settings()
        logger.log(f"ダイアログからのエクスポート設定: {final_settings}", level="INFO")
        # 設定がダイアログの accept() によって保存されたかどうかを確認
        reloaded_saved_settings = settings_mgr.get_setting(HighResOutputDialog.SETTINGS_SECTION_NAME)
        logger.log(f"ダイアログによって保存された設定: {reloaded_saved_settings}", level="INFO")
        assert final_settings == reloaded_saved_settings # 返されたものが保存されたものであることを確認
    else:
        logger.log("ユーザーによってエクスポートがキャンセルされました。", level="INFO")

    # テスト設定ファイルをクリーンアップ
    if Path(test_settings_file).exists(): Path(test_settings_file).unlink(missing_ok=True)
    # SettingsManager によってデフォルトの場所に作成された可能性のある設定ファイルをクリーンアップ
    default_sm_file = Path.home() / ".fractalapp" / "fractal_app_settings.json" # SettingsManager のデフォルトパス
    if default_sm_file.exists(): default_sm_file.unlink(missing_ok=True)
    if (Path.home() / ".fractalapp").exists() and not any((Path.home() / ".fractalapp").iterdir()):
        (Path.home() / ".fractalapp").rmdir()

    # テスト完了。アプリループを管理するより大きなテストスイートの一部として実行される場合、
    # またはモーダルで長時間表示せずにダイアログロジックをテストするだけの場合は、app.exec() は不要です。
    # このタイプの __main__ ブロックの場合、通常は簡単な視覚的確認用なので、app.exec() は問題ありません。
    if not QApplication.instance(): # アプリインスタンスが存在しない場合 (例: スクリプトを直接実行)
        sys.exit(app.exec()) # イベントループを開始
    else: # アプリインスタンスが既に存在する場合 (例: テストランナーにインポート)
        logger.log("ダイアログテストが完了しました (外部イベントループまたはモーダル実行を想定しています)。", level="INFO")
        # dialog.show() # 必要に応じて検査用に非モーダルにし、手動で閉じる
        pass
