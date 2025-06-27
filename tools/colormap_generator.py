import sys
import os
import json
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QFileDialog, QLabel, QSlider, QColorDialog, QSpinBox,
                            QListWidget, QMessageBox, QTabWidget, QGridLayout, QLineEdit,
                            QComboBox, QScrollArea, QFrame)
from PyQt5.QtGui import QColor, QPainter, QPixmap, QImage, QPen
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QRect
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

SKLEARN_AVAILABLE = False
try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    KMeans = None # Placeholder

LANCZOS_RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

class ColorMapPreview(FigureCanvas):
    """カラーマップのプレビューを表示するウィジェット"""
    def __init__(self, parent=None, width=5, height=1, dpi=100):
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.colors = []

    def update_preview(self, colors):
        """カラーマップのプレビューを更新する"""
        self.colors = colors
        self.ax.clear()
        if len(colors) > 1:
            colormap = LinearSegmentedColormap.from_list('custom', colors, N=256)
            gradient = np.linspace(0, 1, 256)
            gradient = np.vstack((gradient, gradient))
            self.ax.imshow(gradient, aspect='auto', cmap=colormap)
        self.ax.set_axis_off()
        self.fig.tight_layout()
        self.draw()

    def get_matplotlib_colormap(self):
        """Matplotlibのカラーマップオブジェクトを返す"""
        if len(self.colors) > 1:
            return LinearSegmentedColormap.from_list('custom', self.colors, N=256)
        return None

class ColorButton(QPushButton):
    """色を選択するためのボタン"""
    color_changed = pyqtSignal()  # 色が変更されたことを通知するシグナル

    def __init__(self, color=QColor(255, 255, 255), parent=None):
        super().__init__(parent)
        self.is_selected = False  # 選択状態を初期化
        self.setColor(color)
        self.setMouseTracking(True)  # マウスイベントを有効化
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setMinimumSize(10, 30)
        self.setMaximumSize(30, 30)

    def setColor(self, color):
        """ボタンの色を設定する"""
        self.color = color
        self._update_style()
        self.color_changed.emit() # 色が変更されたことを通知

    def set_selected(self, selected):
        """選択状態を設定する"""
        self.is_selected = selected
        self._update_style()

    def _update_style(self):
        """選択状態に応じてスタイルを更新"""
        border = "3px solid yellow" if self.is_selected else "1px solid gray"
        self.setStyleSheet(f"""
            background-color: {self.color.name()};
            border: {border};
        """)

    def mouseDoubleClickEvent(self, event):
        """ダブルクリック時の処理"""
        if event.button() == Qt.LeftButton:
            self.choose_color()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """右クリックで選択解除"""
        if event.button() == Qt.RightButton:
            self.set_selected(False)
        super().mousePressEvent(event)

    def choose_color(self):
        """カラーダイアログを表示して色を選択する"""
        color = QColorDialog.getColor(self.color, self.parent(), "色を選択")
        if color.isValid():
            self.setColor(color)  # setColor内で_update_styleが呼ばれる

class ColorMapEditor(QWidget):
    """カラーマップを編集するためのウィジェット"""
    colormap_changed = pyqtSignal(list)
    deletion_failed = pyqtSignal(str)  # 色削除失敗を通知するシグナル

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color_buttons = []
        self.init_ui()

    def init_ui(self):
        """UIを初期化する"""
        layout = QVBoxLayout()

        # カラーマッププレビュー
        # Figureの高さ0.5インチ * DPI 100 = 50ピクセル
        self.preview = ColorMapPreview(self, height=0.5, dpi=100)
        self.preview.setFixedHeight(50)  # ウィジェットの高さを50ピクセルに固定
        layout.addWidget(self.preview)

        # 色ボタンのレイアウト
        self.color_layout = QHBoxLayout()
        self.scroll_area = QScrollArea()
        self.selected_button = None  # 現在選択中のボタン
        self.scroll_widget = QWidget()
        self.scroll_widget.setLayout(self.color_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(60)
        self.scroll_area.setMaximumHeight(60)
        layout.addWidget(self.scroll_area)

        # ボタンのレイアウト
        button_layout = QHBoxLayout()
        add_button = QPushButton("色を追加")
        add_button.clicked.connect(lambda: self.add_color())
        remove_button = QPushButton("色を削除")
        remove_button.clicked.connect(self.remove_color)
        generate_gradient_button = QPushButton("グラデーションを生成")
        generate_gradient_button.clicked.connect(self.generate_gradient)
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(generate_gradient_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 初期色を追加
        self.add_color(QColor(0, 0, 255))
        self.add_color(QColor(255, 0, 0))  # 右側の初期色を赤に

    def _get_interpolated_color(self, color1, color2):
        """2色の中間色を計算する"""
        r = (color1.red() + color2.red()) / 2
        g = (color1.green() + color2.green()) / 2
        b = (color1.blue() + color2.blue()) / 2
        return QColor(int(r), int(g), int(b))

    def add_color(self, color=None):
        """色を追加する"""
        if self.selected_button is None:
            # 非選択時: 右端に色を追加
            if color is not None: # 引数で色が指定されている場合はそれを使う
                new_color = color
            elif self.color_buttons: # 指定されていない場合は右端の同色を追加
                last_color = self.color_buttons[-1].color
                new_color = last_color
            else: # 最初の色で、指定もされていない場合はデフォルト色（赤）
                new_color = QColor(255, 0, 0)
            insert_pos = len(self.color_buttons)
        else:
            # 選択時: 選択位置の右に中間色追加
            selected_index = self.color_buttons.index(self.selected_button)
            if selected_index < len(self.color_buttons) - 1:
                next_color = self.color_buttons[selected_index + 1].color
                new_color = self._get_interpolated_color(self.selected_button.color, next_color)
            else:
                new_color = self.selected_button.color
            insert_pos = selected_index + 1

        color_button = ColorButton(new_color, self)
        self.color_buttons.insert(insert_pos, color_button)
        self.color_layout.insertWidget(insert_pos, color_button)
        color_button.clicked.connect(self._on_color_button_clicked)
        color_button.color_changed.connect(self.update_preview) # 色変更シグナルを接続
        self.update_preview()
        return color_button

    def remove_color(self):
        """色を削除する"""
        if not self.selected_button or not self.selected_button.is_selected:
            self.deletion_failed.emit("色が選択されていないので削除できません")
            return

        if len(self.color_buttons) <= 2:
            # 2色以下の場合は削除できないが、ここでは特にメッセージは出さず、操作を無効にする
            return

        button_to_remove = self.selected_button # 削除するボタンへの参照を保持
        index = self.color_buttons.index(button_to_remove) # リスト内のインデックスを取得
        self.color_buttons.pop(index) # リストから削除
        button_to_remove.deleteLater() # UIから削除
        self.selected_button = None # エディタの選択参照をクリア
        self.update_preview()
    def _on_color_button_clicked(self):
        """カラーボタンがクリックされた時の処理"""
        clicked_button = self.sender()

        # 選択状態を切り替え
        if self.selected_button == clicked_button:
            clicked_button.set_selected(False)
            self.selected_button = None
        else:
            if self.selected_button:
                self.selected_button.set_selected(False)
            clicked_button.set_selected(True)
            self.selected_button = clicked_button

    def generate_gradient(self):
        """開始色と終了色からグラデーションを生成する"""
        if len(self.color_buttons) >= 2:
            num_colors = 20  # 固定で20色のグラデーションを生成

            start_color = self.color_buttons[0].color
            end_color = self.color_buttons[-1].color

            # 既存の色ボタンをすべて削除
            for button in self.color_buttons:
                button.deleteLater()
            self.color_buttons = []
            self.selected_button = None # 選択中のボタンをクリア

            # グラデーションの色を生成して追加
            for i in range(num_colors):
                r = start_color.red() + (end_color.red() - start_color.red()) * i / (num_colors - 1)
                g = start_color.green() + (end_color.green() - start_color.green()) * i / (num_colors - 1)
                b = start_color.blue() + (end_color.blue() - start_color.blue()) * i / (num_colors - 1)
                color = QColor(int(r), int(g), int(b))

                color_button = ColorButton(color, self)
                self.color_buttons.append(color_button)
                self.color_layout.addWidget(color_button)
                color_button.clicked.connect(self._on_color_button_clicked)

            self.update_preview()

    def update_preview(self):
        """プレビューを更新する"""
        colors = [button.color.getRgbF()[0:3] for button in self.color_buttons]
        self.preview.update_preview(colors)
        self.colormap_changed.emit(colors)

    def get_colors(self):
        """現在の色のリストを返す"""
        return [button.color.getRgbF()[0:3] for button in self.color_buttons]

    def set_colors(self, colors):
        """色のリストを設定する"""
        # 既存の色ボタンをすべて削除
        for button in self.color_buttons:
            button.deleteLater()
        self.color_buttons = []
        self.selected_button = None # 選択中のボタンをクリア

        # 新しい色を追加
        for color in colors:
            r, g, b = [int(c * 255) for c in color]
            color_button = ColorButton(QColor(r, g, b), self)
            self.color_buttons.append(color_button)
            self.color_layout.addWidget(color_button)
            color_button.clicked.connect(self._on_color_button_clicked)

        self.update_preview()

class ImageColorExtractor(QWidget):
    """画像から色を抽出するためのウィジェット"""
    colors_extracted = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.init_ui()

    def init_ui(self):
        """UIを初期化する"""
        layout = QVBoxLayout()

        # 画像表示エリア
        self.image_label = QLabel("画像をロードしてください")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setFrameStyle(QFrame.StyledPanel)
        layout.addWidget(self.image_label)

        # コントロールレイアウト (読み込みボタン、色数選択、抽出ボタン)
        controls_layout = QHBoxLayout()

        load_button = QPushButton("画像を読み込む")
        load_button.clicked.connect(self.load_image)
        controls_layout.addWidget(load_button)

        # 抽出色数の選択ウィジェット
        num_colors_widget = QWidget()
        num_colors_sub_layout = QHBoxLayout(num_colors_widget)
        num_colors_sub_layout.setContentsMargins(0, 0, 0, 0)
        num_colors_sub_layout.addWidget(QLabel("抽出色数:"))
        self.num_colors_spinbox = QSpinBox()
        self.num_colors_spinbox.setMinimum(2)
        self.num_colors_spinbox.setMaximum(50) # 最大30色まで抽出可能
        self.num_colors_spinbox.setValue(10)
        num_colors_sub_layout.addWidget(self.num_colors_spinbox)
        controls_layout.addWidget(num_colors_widget)

        extract_button = QPushButton("色を自動抽出")
        extract_button.clicked.connect(self.extract_colors)
        if not SKLEARN_AVAILABLE:
            extract_button.setEnabled(False)
            extract_button.setToolTip("scikit-learn がインストールされていません。この機能は利用できません。\n`pip install scikit-learn` でインストールしてください。")
        controls_layout.addWidget(extract_button)

        layout.addLayout(controls_layout)

        # 抽出色のプレビュー
        self.color_preview = QWidget()
        self.color_preview.setMinimumHeight(50)
        self.color_preview_layout = QHBoxLayout()
        self.color_preview.setLayout(self.color_preview_layout)
        layout.addWidget(self.color_preview)

        self.setLayout(layout)

    def load_image(self):
        """画像を読み込む"""
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "画像を開く", "", "画像ファイル (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
            options=options)

        if file_name:
            self.image = Image.open(file_name)
            pixmap = QPixmap(file_name)

            # 画像を表示エリアのサイズに合わせてリサイズ
            scaled_pixmap = pixmap.scaled(
                self.image_label.width(), self.image_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)

            self.image_label.setPixmap(scaled_pixmap)

    def extract_colors(self):
        """画像から色を抽出する"""
        if not SKLEARN_AVAILABLE:
            QMessageBox.critical(self, "エラー", "scikit-learnがインストールされていません。\nこの機能を使用するには `pip install scikit-learn` を実行してください。")
            return

        if self.image is None:
            QMessageBox.warning(self, "警告", "画像を読み込んでください。")
            return

        num_extract_colors = self.num_colors_spinbox.value()

        # 画像をNumPy配列に変換
        img_array = np.array(self.image.convert('RGB'))

        # 画像のサイズを縮小して処理を高速化
        height, width, _ = img_array.shape
        # K-meansの処理負荷を考慮し、大きすぎる画像はリサイズ
        # (閾値は必要に応じて調整してください)
        if width > 400 or height > 400: # 以前の300pxから少し緩和
            scale = min(400.0 / width, 400.0 / height)
            new_width = max(1, int(width * scale))
            new_height = max(1, int(height * scale))
            img_small = self.image.resize((new_width, new_height), LANCZOS_RESAMPLE)
            img_array = np.array(img_small.convert('RGB'))

        # 画像の色をフラット化
        pixels = img_array.reshape(-1, 3)

        if pixels.shape[0] == 0:
            QMessageBox.warning(self, "警告", "画像から有効なピクセルを抽出できませんでした。")
            return

        n_samples = pixels.shape[0]
        effective_n_clusters = num_extract_colors

        if n_samples < num_extract_colors:
            QMessageBox.information(self, "情報", f"画像のピクセル数 ({n_samples}) が指定された抽出色数 ({num_extract_colors}) より少ないため、抽出色数を {n_samples} に調整します。")
            effective_n_clusters = n_samples
            if effective_n_clusters < 1: # 念のため
                 QMessageBox.warning(self, "警告", "有効なピクセルがありません。")
                 return

        kmeans = KMeans(n_clusters=effective_n_clusters, random_state=0, n_init=10)
        kmeans.fit(pixels)

        extracted_rgb_colors = kmeans.cluster_centers_.astype(int)
        top_colors = []
        for r, g, b in extracted_rgb_colors:
            top_colors.append((r / 255.0, g / 255.0, b / 255.0))

        # 色のプレビューを更新
        self._update_color_preview(top_colors)

        # 抽出した色を通知
        self.colors_extracted.emit(top_colors)

    def _update_color_preview(self, colors):
        """抽出した色のプレビューを更新する"""
        # 既存のウィジェットをクリア
        for i in reversed(range(self.color_preview_layout.count())):
            self.color_preview_layout.itemAt(i).widget().deleteLater()

        # 色のプレビューを追加
        for color in colors:
            r, g, b = [int(c * 255) for c in color]
            color_label = QLabel()
            color_label.setStyleSheet(f"background-color: rgb({r}, {g}, {b})")
            color_label.setMinimumSize(20, 40)
            self.color_preview_layout.addWidget(color_label)

class AutoColorMapGenerator(QWidget):
    """カラーマップを自動生成するためのウィジェット"""
    colormap_generated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """UIを初期化する"""
        layout = QVBoxLayout()

        # カラーマップの種類を選択
        # Matplotlibの標準カラーマップも追加
        self.colormap_options = ["グラデーション", "虹色", "地形図", "温度", "赤青", "グレースケール", "パステル調", "viridis", "plasma", "inferno", "magma", "cividis", "coolwarm", "seismic"]
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("カラーマップの種類:"))
        self.colormap_type = QComboBox()
        self.colormap_type.addItems(self.colormap_options)
        type_layout.addWidget(self.colormap_type)
        layout.addLayout(type_layout)
        # 色数の選択
        num_colors_layout = QHBoxLayout()
        num_colors_layout.addWidget(QLabel("色数:"))
        self.num_colors_slider = QSlider(Qt.Horizontal)
        self.num_colors_slider.setMinimum(2)
        self.num_colors_slider.setMaximum(20)
        self.num_colors_slider.setValue(10)
        self.num_colors_slider.setTickPosition(QSlider.TicksBelow)
        self.num_colors_slider.setTickInterval(1)
        self.num_colors_label = QLabel("10")
        self.num_colors_slider.valueChanged.connect(lambda x: self.num_colors_label.setText(str(x)))
        num_colors_layout.addWidget(self.num_colors_slider)
        num_colors_layout.addWidget(self.num_colors_label)
        layout.addLayout(num_colors_layout)

        # 生成ボタン
        generate_button = QPushButton("カラーマップを生成")
        generate_button.clicked.connect(self.generate_colormap)
        layout.addWidget(generate_button)

        # プレビュー
        self.preview = ColorMapPreview(self)
        layout.addWidget(self.preview)

        self.setLayout(layout)
        self.preview.update_preview([]) # 初期状態で軸を非表示にする

    def generate_colormap(self):
        """選択したタイプに基づいてカラーマップを生成する"""
        colormap_type = self.colormap_type.currentText()
        num_colors = self.num_colors_slider.value()

        colors = []

        if colormap_type == "グラデーション":
            # 青から赤へのグラデーション
            for i in range(num_colors):
                t = i / (num_colors - 1)
                colors.append((t, 0, 1 - t))

        elif colormap_type == "虹色":
            # 虹色のカラーマップ
            import colorsys
            for i in range(num_colors):
                hue = i / (num_colors - 1)
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                colors.append((r, g, b))

        elif colormap_type == "地形図":
            # 地形図のカラーマップ（青、緑、茶色、白）
            base_colors = [(0, 0, 0.5), (0, 0.5, 0), (0.5, 0.25, 0), (1, 1, 1)]
            for i in range(num_colors):
                t = i / (num_colors - 1)
                if t <= 0.33:  # 青から緑
                    s = t / 0.33
                    colors.append(self._interpolate(base_colors[0], base_colors[1], s))
                elif t <= 0.67:  # 緑から茶色
                    s = (t - 0.33) / 0.34
                    colors.append(self._interpolate(base_colors[1], base_colors[2], s))
                else:  # 茶色から白
                    s = (t - 0.67) / 0.33
                    colors.append(self._interpolate(base_colors[2], base_colors[3], s))

        elif colormap_type == "温度":
            # 温度のカラーマップ（青、緑、黄色、赤）
            base_colors = [(0, 0, 1), (0, 1, 0), (1, 1, 0), (1, 0, 0)]
            for i in range(num_colors):
                t = i / (num_colors - 1)
                if t <= 0.33:  # 青から緑
                    s = t / 0.33
                    colors.append(self._interpolate(base_colors[0], base_colors[1], s))
                elif t <= 0.67:  # 緑から黄色
                    s = (t - 0.33) / 0.34
                    colors.append(self._interpolate(base_colors[1], base_colors[2], s))
                else:  # 黄色から赤
                    s = (t - 0.67) / 0.33
                    colors.append(self._interpolate(base_colors[2], base_colors[3], s))

        elif colormap_type == "赤青":
            # 赤青のカラーマップ（赤、白、青）
            base_colors = [(1, 0, 0), (1, 1, 1), (0, 0, 1)]
            middle = num_colors // 2
            for i in range(num_colors):
                if i < middle:
                    s = i / middle
                    colors.append(self._interpolate(base_colors[0], base_colors[1], s))
                else:
                    s = (i - middle) / (num_colors - middle - 1) if num_colors > middle + 1 else 1
                    colors.append(self._interpolate(base_colors[1], base_colors[2], s))

        elif colormap_type == "グレースケール":
            # 黒から白へのグラデーション
            for i in range(num_colors):
                t = i / (num_colors - 1)
                colors.append((t, t, t))

        elif colormap_type == "パステル調":
            # ランダムなパステルカラー
            import colorsys
            import random
            for _ in range(num_colors):
                hue = random.random()
                r, g, b = colorsys.hsv_to_rgb(hue, random.uniform(0.3, 0.5), random.uniform(0.8, 1.0))
                colors.append((r, g, b))

        # Matplotlib標準カラーマップの生成
        elif colormap_type in ["viridis", "plasma", "inferno", "magma", "cividis", "coolwarm", "seismic"]:
            try:
                cmap = plt.get_cmap(colormap_type)
                # 0から1の範囲で均等にサンプリング
                sampled_colors = cmap(np.linspace(0, 1, num_colors))
                # RGBAからRGBに変換 (アルファチャンネルを捨てる)
                colors = [(r, g, b) for r, g, b, a in sampled_colors]
            except ValueError:
                # 指定された名前のカラーマップが見つからない場合（通常は発生しないはず）
                print(f"Warning: Unknown colormap type '{colormap_type}'.")
                colors = [] # またはデフォルトのカラーマップを生成

        # プレビューを更新
        self.preview.update_preview(colors)

        # 生成したカラーマップを通知
        self.colormap_generated.emit(colors)

    def _interpolate(self, color1, color2, t):
        """二つの色の間を補間する"""
        r = color1[0] + (color2[0] - color1[0]) * t
        g = color1[1] + (color2[1] - color1[1]) * t
        b = color1[2] + (color2[2] - color1[2]) * t
        return (r, g, b)

class ColorMapLibrary(QWidget):
    """カラーマップのライブラリを管理するウィジェット"""
    colormap_selected = pyqtSignal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colormaps = {}
        self.init_ui()

    def init_ui(self):
        """UIを初期化する"""
        layout = QVBoxLayout()

        # 名前入力
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("カラーマップ名:"))
        self.name_input = QLineEdit()
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # 保存と読み込みのボタン
        button_layout = QHBoxLayout()
        save_button = QPushButton("現在のカラーマップを保存")
        save_button.clicked.connect(self.save_current_colormap)
        load_button = QPushButton("選択したカラーマップを読み込む")
        load_button.clicked.connect(self.load_selected_colormap)
        button_layout.addWidget(save_button)
        button_layout.addWidget(load_button)
        layout.addLayout(button_layout)

        # カラーマップリスト
        self.colormap_list = QListWidget()
        self.colormap_list.itemDoubleClicked.connect(self.load_selected_colormap)
        layout.addWidget(self.colormap_list)

        # ファイル操作ボタン
        file_button_layout = QHBoxLayout()
        export_button = QPushButton("JSONファイルにエクスポート")
        export_button.clicked.connect(self.export_to_json)
        import_button = QPushButton("JSONファイルからインポート")
        import_button.clicked.connect(self.import_from_json)
        delete_button = QPushButton("選択したカラーマップを削除")
        delete_button.clicked.connect(self.delete_selected_colormap)
        file_button_layout.addWidget(export_button)
        file_button_layout.addWidget(import_button)
        file_button_layout.addWidget(delete_button)
        layout.addLayout(file_button_layout)

        self.setLayout(layout)

    def set_current_colors(self, colors):
        """現在の色を設定する"""
        self.current_colors = colors

    def save_current_colormap(self):
        """現在のカラーマップを保存する"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "カラーマップ名を入力してください。")
            return

        self.colormaps[name] = self.current_colors

        # リストに追加（まだ存在しない場合）
        items = [self.colormap_list.item(i).text() for i in range(self.colormap_list.count())]
        if name not in items:
            self.colormap_list.addItem(name)

        QMessageBox.information(self, "保存完了", f"カラーマップ '{name}' を保存しました。")

    def load_selected_colormap(self):
        """選択したカラーマップを読み込む"""
        items = self.colormap_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "警告", "カラーマップを選択してください。")
            return

        name = items[0].text()
        if name in self.colormaps:
            colors = self.colormaps[name]
            self.colormap_selected.emit(colors, name)

    def delete_selected_colormap(self):
        """選択したカラーマップを削除する"""
        items = self.colormap_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "警告", "カラーマップを選択してください。")
            return

        name = items[0].text()
        if name in self.colormaps:
            del self.colormaps[name]
            self.colormap_list.takeItem(self.colormap_list.row(items[0]))
            QMessageBox.information(self, "削除完了", f"カラーマップ '{name}' を削除しました。")

    def export_to_json(self):
        """カラーマップをJSONファイルにエクスポートする"""
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(
            self, "JSONファイルに保存", "", "JSON Files (*.json);;All Files (*)",
            options=options)

        if file_name:
            # 拡張子が指定されていない場合は.jsonを追加
            if not file_name.endswith('.json'):
                file_name += '.json'

            try:
                # カラーマップデータをJSON形式に変換
                data = {}
                for name, colors in self.colormaps.items():
                    data[name] = colors

                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                QMessageBox.information(self, "エクスポート完了", f"カラーマップを '{file_name}' にエクスポートしました。")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"エクスポート中にエラーが発生しました: {str(e)}")

    def import_from_json(self):
        """JSONファイルからカラーマップをインポートする"""
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "JSONファイルを開く", "", "JSON Files (*.json);;All Files (*)",
            options=options)

        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # データをカラーマップに変換
                for name, colors in data.items():
                    self.colormaps[name] = colors

                    # リストに追加（まだ存在しない場合）
                    items = [self.colormap_list.item(i).text() for i in range(self.colormap_list.count())]
                    if name not in items:
                        self.colormap_list.addItem(name)

                QMessageBox.information(self, "インポート完了", f"カラーマップを '{file_name}' からインポートしました。")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"インポート中にエラーが発生しました: {str(e)}")

class ColorMapGenerator(QMainWindow):
    """カラーマップジェネレータのメインウィンドウ"""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """UIを初期化する"""
        self.setWindowTitle("Matplotlibカラーマップジェネレータ")
        self.setGeometry(100, 100, 800, 400)

        # メインウィジェット
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # タブウィジェット
        tab_widget = QTabWidget()

        # カラーマップエディタタブ
        self.editor = ColorMapEditor()
        tab_widget.addTab(self.editor, "カラーマップエディタ")

        # 画像からの色抽出タブ
        self.extractor = ImageColorExtractor()
        tab_widget.addTab(self.extractor, "画像から色を抽出")

        # 自動生成タブ
        self.generator = AutoColorMapGenerator()
        tab_widget.addTab(self.generator, "カラーマップを自動生成")

        # ライブラリタブ
        self.library = ColorMapLibrary()
        tab_widget.addTab(self.library, "カラーマップライブラリ")

        main_layout.addWidget(tab_widget)

        # ステータスバーとプレビュー
        status_layout = QHBoxLayout()
        self.status_label = QLabel("準備完了")
        status_layout.addWidget(self.status_label)
        main_layout.addLayout(status_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # シグナル接続
        self.editor.colormap_changed.connect(self.update_library_colors)
        self.extractor.colors_extracted.connect(self.set_editor_colors)
        self.generator.colormap_generated.connect(self.set_editor_colors)
        self.library.colormap_selected.connect(self.load_colormap)
        self.editor.deletion_failed.connect(self.update_status_message)

    def update_library_colors(self, colors):
        """ライブラリに現在の色を設定する"""
        self.library.set_current_colors(colors)

    def set_editor_colors(self, colors):
        """エディタの色を設定する"""
        self.editor.set_colors(colors)
        self.status_label.setText(f"{len(colors)}色のカラーマップをロードしました")

    def load_colormap(self, colors, name):
        """カラーマップをロードする"""
        self.editor.set_colors(colors)
        self.status_label.setText(f"カラーマップ '{name}' をロードしました")

    def update_status_message(self, message):
        """ステータスバーのメッセージを更新する"""
        self.status_label.setText(message)

def main():
    app = QApplication(sys.argv)
    window = ColorMapGenerator()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
