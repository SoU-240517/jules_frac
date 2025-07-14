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
        kmeans = KMeans(n_clusters=num_colors, n_init='auto', random_state=None).fit(pixels[:, :3])
        centers = kmeans.cluster_centers_.astype(int)
        
        # 色をランダムにシャッフル
        random.shuffle(centers)

        # ノードの位置をランダムに割り振り、ソートする
        positions = sorted([random.random() for _ in range(num_colors)])

        points = [{'pos': positions[i], 'color': list(c) + [255]} for i, c in enumerate(centers)]
        
        # 念のためposでソート
        points.sort(key=lambda x: x['pos'])
        
        return points

    @staticmethod
    def get_random_generate_params(parent, max_value=30, max_nodes=20):
        """ランダム生成のパラメータを取得"""
        num, ok = QInputDialog.getInt(parent, "ランダム生成", f"生成数 (1〜{max_value}):", 1, 1, max_value)
        if not ok:
            return None, None, None, None

        map_type, ok = QInputDialog.getItem(parent, "マップタイプ選択", "マップタイプを選択してください:", ["gradient", "indexed"], 0, False)
        if not ok:
            return None, None, None, None

        min_nodes, max_nodes_val = 2, max_nodes
        if map_type == "gradient":
            text, ok = QInputDialog.getText(parent, "ノード数指定", f"ノード数の範囲 (例: 2-{max_nodes})", text=f"2-{max_nodes}")
            if not ok:
                return None, None, None, None
            try:
                parts = [p.strip() for p in text.split('-')]
                if len(parts) == 2:
                    min_nodes = int(parts[0]) if parts[0] else 2
                    max_nodes_val = int(parts[1]) if parts[1] else max_nodes
                elif len(parts) == 1:
                    min_nodes = max_nodes_val = int(parts[0])
                min_nodes = max(2, min_nodes)
                max_nodes_val = min(max_nodes, max_nodes_val)
            except ValueError:
                ColormapUtils.show_error_message(parent, "入力エラー", "ノード数の形式が正しくありません。")
                return None, None, None, None

        return num, map_type, min_nodes, max_nodes_val

    @staticmethod
    def get_extract_image_params(parent, max_maps=30):
        """画像抽出のパラメータを取得"""
        file_path, _ = QFileDialog.getOpenFileName(parent, "画像ファイルを選択", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if not file_path:
            return None, None, None

        num_colors, ok = QInputDialog.getInt(parent, "色数指定", "抽出する色数 (2〜30):", 5, 2, 30)
        if not ok:
            return file_path, None, None

        num_maps, ok = QInputDialog.getInt(parent, "生成マップ数", f"生成するマップ数 (1〜{max_maps}):", 1, 1, max_maps)
        if not ok:
            return file_path, num_colors, None

        return file_path, num_colors, num_maps

    @staticmethod
    def show_error_message(parent, title, message):
        """エラーメッセージを表示"""
        QMessageBox.warning(parent, title, message)

    @staticmethod
    def show_success_message(parent, title, message):
        """成功メッセージを表示"""
        QMessageBox.information(parent, title, message)
