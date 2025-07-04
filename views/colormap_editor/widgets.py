import sys
from PyQt6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsItem,
    QMenu, QColorDialog
)
from PyQt6.QtGui import (
    QLinearGradient, QColor, QBrush, QPainter, QPen, QImage
)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal


class GradientPreviewWidget(QWidget):
    """グラディエントプレビューウィジェット"""
    color_changed_at = pyqtSignal(float, QColor)
    direct_edit_mode = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cmap_data = None
        self.setMinimumHeight(100)

    def set_colormap(self, cmap_data):
        """カラーマップデータを設定してプレビューを更新"""
        self.cmap_data = cmap_data
        # デバッグ情報を出力
        if cmap_data:
            print(f"GradientPreviewWidget: カラーマップデータを設定 - type: {cmap_data.get('type')}, points: {len(cmap_data.get('gradient_points', []))}")
        # 強制的に再描画を実行
        self.update()
        self.repaint()

    def set_direct_edit_mode(self, enabled):
        """ダイレクト編集モードを設定"""
        self.direct_edit_mode = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def get_color_at(self, pos: float) -> QColor:
        """指定位置の色を取得"""
        if not self.cmap_data:
            return QColor()

        gradient = QLinearGradient(0, 0, 1, 0)
        if self.cmap_data.get('type') == 'gradient' and 'gradient_points' in self.cmap_data:
            points = self.cmap_data['gradient_points']
            for point in points:
                gradient.setColorAt(point.get('pos', 0.0), QColor(*point.get('color', [0, 0, 0, 255])))
        elif 'colors' in self.cmap_data:
            colors = self.cmap_data['colors']
            num_colors = len(colors)
            if num_colors > 0:
                if num_colors == 1:
                    gradient.setColorAt(0, QColor(*colors[0]))
                    gradient.setColorAt(1, QColor(*colors[0]))
                else:
                    for i, color_rgba in enumerate(colors):
                        gradient.setColorAt(i / (num_colors - 1), QColor(*color_rgba))

        img = QImage(256, 1, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.fillRect(img.rect(), gradient)
        painter.end()

        x = min(max(int(pos * 255), 0), 255)
        return img.pixelColor(x, 0)

    def mousePressEvent(self, event):
        """マウスプレスイベント処理"""
        if self.direct_edit_mode and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos().x() / self.width()
            initial_color = self.get_color_at(pos)
            color = QColorDialog.getColor(initial_color, self, "色を選択")
            if color.isValid():
                self.color_changed_at.emit(pos, color)
        else:
            # ノードドラッグ開始時に親へ通知
            scene = self.scene()
            if scene and scene.parent():
                scene.parent().on_nodes_changed(final_change='start_drag')
            # ドラッグ開始時にフラグをリセット
            self._dragging = False
            super().mousePressEvent(event)

    def paintEvent(self, event):
        """描画イベント処理"""
        super().paintEvent(event)
        painter = QPainter(self)
        if not self.cmap_data:
            return

        gradient = QLinearGradient(0, 0, self.width(), 0)

        if self.cmap_data.get('type') == 'gradient' and 'gradient_points' in self.cmap_data:
            points = self.cmap_data['gradient_points']
            for point in points:
                pos = point.get('pos', 0.0)
                color_rgba = point.get('color', [0, 0, 0, 255])
                gradient.setColorAt(pos, QColor(*color_rgba))
        elif 'colors' in self.cmap_data:
            colors = self.cmap_data['colors']
            num_colors = len(colors)
            if num_colors > 0:
                if num_colors == 1:
                    gradient.setColorAt(0, QColor(*colors[0]))
                    gradient.setColorAt(1, QColor(*colors[0]))
                else:
                    for i, color_rgba in enumerate(colors):
                        pos = i / (num_colors - 1)
                        gradient.setColorAt(pos, QColor(*color_rgba))

        painter.fillRect(self.rect(), QBrush(gradient))


class NodeItem(QGraphicsEllipseItem):
    """ノードアイテム"""

    def __init__(self, pos, color, radius=8):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.setBrush(QBrush(QColor(*color)))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.pos_value = pos
        self.color_value = color
        self._dragging = False  # ドラッグ中フラグ
        self._last_pos = None   # 前回の座標

    def set_color(self, color):
        """色を設定"""
        self.color_value = color
        self.setBrush(QBrush(QColor(*color)))

    def itemChange(self, change, value):
        """アイテム変更イベント処理"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            print(f"NodeItem: ItemPositionChange - pos: {value.x():.4f}, _dragging={self._dragging}, _last_pos={self._last_pos}")
            if not self._dragging and self._last_pos is not None and value != self._last_pos:
                scene = self.scene()
                if scene and scene.parent():
                    print("NodeItem: start_drag 通知")
                    scene.parent().on_nodes_changed(final_change='start_drag')
                self._dragging = True
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            print(f"NodeItem: ItemPositionHasChanged - pos: {self.pos().x():.4f}")
            self._dragging = False
            self._last_pos = self.pos()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        print("NodeItem: mousePressEvent（マウス押下）")
        self._last_pos = self.pos()  # ドラッグ開始前の座標を記録
        self._dragging = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        print("NodeItem: mouseReleaseEvent（マウス離し）")
        self._dragging = False
        super().mouseReleaseEvent(event)


class NodeEditorScene(QGraphicsScene):
    """ノードエディタシーン"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 600, 100)
        self.nodes = []

    def clear_nodes(self):
        """すべてのノードをクリア"""
        for node in self.nodes:
            self.removeItem(node)
        self.nodes.clear()

    def add_node(self, pos, color):
        """ノードを追加"""
        node = NodeItem(pos, color)
        node.setPos(pos * self.width(), self.height() / 2)
        self.addItem(node)
        self.nodes.append(node)
        return node

    def contextMenuEvent(self, event):
        """コンテキストメニューイベント処理"""
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        if isinstance(item, NodeItem):
            menu = QMenu()
            remove_action = menu.addAction("ノード削除")
            action = menu.exec(event.screenPos())
            if action == remove_action:
                self.removeItem(item)
                self.nodes.remove(item)
                # 正しい親ウィジェット（ColormapEditor）を取得
                parent_widget = self.parent()
                while parent_widget and not hasattr(parent_widget, 'on_node_editor_changed'):
                    parent_widget = parent_widget.parent()
                if parent_widget:
                    parent_widget.on_node_editor_changed(final_change=True)

    def mouseDoubleClickEvent(self, event):
        """マウスダブルクリックイベント処理"""
        x = event.scenePos().x()
        pos = min(max(x / self.width(), 0.0), 1.0)
        color = [255, 255, 255, 255]
        self.add_node(pos, color)
        # 正しい親ウィジェット（ColormapEditor）を取得
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, 'on_node_editor_changed'):
            parent_widget = parent_widget.parent()
        if parent_widget:
            parent_widget.on_node_editor_changed(final_change=True)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        """マウスリリースイベント処理"""
        super().mouseReleaseEvent(event)
        # マウスリリース時に最終更新を実行
        # 正しい親ウィジェット（ColormapEditor）を取得
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, 'on_node_editor_changed'):
            parent_widget = parent_widget.parent()
        if parent_widget:
            parent_widget.on_node_editor_changed(final_change=True)


class NodeEditorView(QGraphicsView):
    """ノードエディタビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(NodeEditorScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(100)

    def set_nodes(self, points):
        """ノードを設定"""
        scene = self.scene()
        scene.clear_nodes()
        for pt in points:
            scene.add_node(pt.get('pos', 0.0), pt.get('color', [255, 255, 255, 255]))

    def get_nodes(self):
        """ノードリストを取得"""
        scene = self.scene()
        return sorted([
            {'pos': node.pos_value, 'color': node.color_value}
            for node in scene.nodes
        ], key=lambda x: x['pos'])

    def on_nodes_changed(self, final_change=False):
        """ノード変更イベント処理"""
        print(f"NodeEditorView: on_nodes_changed 呼び出し - final_change: {final_change}")
        # 正しい親ウィジェット（ColormapEditor）を取得
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, 'on_node_editor_changed'):
            parent_widget = parent_widget.parent()

        if parent_widget and hasattr(parent_widget, 'on_node_editor_changed'):
            parent_widget.on_node_editor_changed(final_change=final_change)
        else:
            print("NodeEditorView: ColormapEditorが見つかりません")
