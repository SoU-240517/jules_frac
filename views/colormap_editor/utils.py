import random
from PyQt6.QtWidgets import QInputDialog, QFileDialog, QMessageBox


class ColormapUtils:
    """カラーマップユーティリティクラス"""

    @staticmethod
    def random_generate_colormap(num_nodes):
        """ランダムカラーマップを生成"""
        points = []
        for i in range(num_nodes):
            pos = i / (num_nodes - 1) if num_nodes > 1 else 0.0
            if i != 0 and i != num_nodes - 1:
                pos += random.uniform(-0.1, 0.1)
                pos = min(max(pos, 0.0), 1.0)
            color = [random.randint(0, 255) for _ in range(3)] + [255]
            points.append({'pos': pos, 'color': color})
        points.sort(key=lambda x: x['pos'])
        return points

    @staticmethod
    def extract_colors_from_image(file_path, num_colors):
        """画像から色を抽出"""
        try:
            from PIL import Image
            from sklearn.cluster import KMeans
            import numpy as np
        except ImportError:
            raise ImportError("Pillow, scikit-learn, numpyが必要です")

        img = Image.open(file_path).convert('RGBA')
        img = img.resize((128, 128))
        pixels = np.array(img).reshape(-1, 4)
        pixels = pixels[pixels[:, 3] > 0]
        kmeans = KMeans(n_clusters=num_colors, n_init='auto', random_state=0).fit(pixels[:, :3])
        centers = kmeans.cluster_centers_.astype(int)
        points = [{'pos': i / (num_colors - 1) if num_colors > 1 else 0.0, 'color': list(c) + [255]} for i, c in enumerate(centers)]
        return points

    @staticmethod
    def get_random_generate_params(parent):
        """ランダム生成のパラメータを取得"""
        num, ok = QInputDialog.getInt(parent, "ランダム生成", "ノード数 (2〜30):", 5, 2, 30)
        return num if ok else None

    @staticmethod
    def get_extract_image_params(parent):
        """画像抽出のパラメータを取得"""
        file_path, _ = QFileDialog.getOpenFileName(parent, "画像ファイルを選択", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if not file_path:
            return None, None

        num, ok = QInputDialog.getInt(parent, "色数指定", "抽出する色数 (2〜30):", 5, 2, 30)
        return file_path, num if ok else None

    @staticmethod
    def show_error_message(parent, title, message):
        """エラーメッセージを表示"""
        QMessageBox.warning(parent, title, message)

    @staticmethod
    def show_success_message(parent, title, message):
        """成功メッセージを表示"""
        QMessageBox.information(parent, title, message)
