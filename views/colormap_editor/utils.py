import random
from PyQt6.QtWidgets import QInputDialog, QFileDialog, QMessageBox
from models.colormap import ColorStop
from pathlib import Path
import sys
from functools import wraps

class ColormapUtils:
    """カラーマップユーティリティクラス"""

    @staticmethod
    def random_generate_colormap(num_nodes: int) -> list[ColorStop]:
        """ランダムなカラーマップ（ColorStopのリスト）を生成"""
        points = []
        for i in range(num_nodes):
            pos = i / (num_nodes - 1) if num_nodes > 1 else 0.0
            if i != 0 and i != num_nodes - 1:
                pos += random.uniform(-0.05, 0.05)
                pos = min(max(pos, 0.0), 1.0)
            color = [random.randint(0, 255) for _ in range(3)] + [255]
            points.append(ColorStop(pos=pos, color=color))
        points.sort(key=lambda x: x.pos)
        # 最初と最後のノードを黒と白に設定（オプション）
        # if num_nodes > 1:
        #     points[0].color = [0, 0, 0, 255]
        #     points[-1].color = [255, 255, 255, 255]
        return points

    @staticmethod
    def extract_colors_from_image(file_path: str, num_colors: int) -> list[ColorStop]:
        """画像から色を抽出し、ColorStopのリストとして返す"""
        try:
            from PIL import Image
            from sklearn.cluster import KMeans
            import numpy as np
        except ImportError:
            raise ImportError("Pillow, scikit-learn, numpyが必要です")

        img = Image.open(file_path).convert('RGBA')
        img = img.resize((128, 128))
        pixels = np.array(img).reshape(-1, 4)
        # Alphaが0でないピクセルのみを対象
        pixels = pixels[pixels[:, 3] > 0]

        # ピクセル数がクラスタ数より少ない場合は、クラスタ数をピクセル数に合わせる
        actual_num_colors = min(num_colors, len(pixels))
        if actual_num_colors < 2:
            # 色が1色しかない、または抽出できない場合はデフォルトのグラデーションを返す
            return [ColorStop(pos=0.0, color=[0,0,0,255]), ColorStop(pos=1.0, color=[255,255,255,255])]

        kmeans = KMeans(n_clusters=actual_num_colors, n_init='auto', random_state=None).fit(pixels[:, :3])
        centers = kmeans.cluster_centers_.astype(int)

        random.shuffle(centers)
        positions = sorted([random.random() for _ in range(actual_num_colors)])

        points = [ColorStop(pos=positions[i], color=list(c) + [255]) for i, c in enumerate(centers)]
        points.sort(key=lambda x: x.pos)
        return points

    @staticmethod
    def get_random_generate_params(parent, max_value=30, max_nodes=20):
        num, ok = QInputDialog.getInt(parent, "ランダム生成", f"生成数 (1〜{max_value}):", 1, 1, max_value)
        if not ok: return None, None, None, None

        map_type, ok = QInputDialog.getItem(parent, "マップタイプ選択", "マップタイプを選択してください:", ["gradient", "indexed"], 0, False)
        if not ok: return None, None, None, None

        min_n, max_n = 2, max_nodes
        if map_type == "gradient":
            text, ok = QInputDialog.getText(parent, "ノード数指定", f"ノード数の範囲 (例: 2-{max_nodes})", text=f"2-{max_nodes}")
            if not ok: return None, None, None, None
            try:
                parts = [p.strip() for p in text.split('-')]
                if len(parts) == 2:
                    min_n = int(parts[0]) if parts[0] else 2
                    max_n = int(parts[1]) if parts[1] else max_nodes
                elif len(parts) == 1:
                    min_n = max_n = int(parts[0])
                min_n = max(2, min_n)
                max_n = min(max_nodes, max_n)
            except ValueError:
                QMessageBox.warning(parent, "入力エラー", "ノード数の形式が正しくありません。")
                return None, None, None, None

        return num, map_type, min_n, max_n

    @staticmethod
    def get_extract_image_params(parent, max_maps=30):
        file_path, _ = QFileDialog.getOpenFileName(parent, "画像ファイルを選択", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if not file_path: return None, None, None

        num_colors, ok = QInputDialog.getInt(parent, "色数指定", "抽出する色数 (2〜30):", 5, 2, 30)
        if not ok: return file_path, None, None

        num_maps, ok = QInputDialog.getInt(parent, "生成マップ数", f"生成するマップ数 (1〜{max_maps}):", 1, 1, max_maps)
        if not ok: return file_path, num_colors, None

        return file_path, num_colors, num_maps

    @staticmethod
    def show_error_message(parent, title, message):
        QMessageBox.warning(parent, title, message)

    @staticmethod
    def show_success_message(parent, title, message):
        QMessageBox.information(parent, title, message)


def log_exceptions(logger):
    """例外をロギングし、再スローするデコレータ。"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(f"例外発生: {func.__name__}: {e}", level="ERROR")
                raise
        return wrapper
    return decorator


def get_project_root() -> Path:
    """プロジェクトのルートディレクトリを返す。"""
    return Path(__file__).resolve().parent.parent.parent


def to_relpath(p) -> str:
    """パスをプロジェクトルートからの相対パスに変換。"""
    prj = get_project_root()
    try:
        if prj and Path(p).is_absolute():
            return str(Path(p).relative_to(prj))
    except Exception:
        pass
    return str(p)
