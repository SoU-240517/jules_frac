import sys
from PyQt6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsItem,
    QMenu, QColorDialog
)
from PyQt6.QtGui import (
    QLinearGradient, QColor, QBrush, QPainter, QPen, QImage
)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal

from models.colormap import Colormap, ColorStop

class GradientPreviewWidget(QWidget):
    """グラディエントプレビューウィジェット"""
    color_changed_at = pyqtSignal(float, QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cmap: Colormap | None = None
        self.direct_edit_mode = False
        self.setMinimumHeight(100)

    def set_colormap(self, cmap: Colormap | None):
        self.cmap = cmap
        self.update()

    def set_direct_edit_mode(self, enabled: bool):
        self.direct_edit_mode = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def get_color_at(self, pos: float) -> QColor:
        if not self.cmap:
            return QColor()

        # QImageを使って特定の位置の色を正確に取得
        img = QImage(256, 1, QImage.Format.Format_ARGB32)
        painter = QPainter(img)
        gradient = self._create_q_linear_gradient(256, 0)
        painter.fillRect(img.rect(), gradient)
        painter.end()

        x = min(max(int(pos * 255), 0), 255)
        return img.pixelColor(x, 0)

    def mousePressEvent(self, event):
        if self.direct_edit_mode and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos().x() / self.width()
            initial_color = self.get_color_at(pos)
            color = QColorDialog.getColor(initial_color, self, "色を選択")
            if color.isValid():
                self.color_changed_at.emit(pos, color)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if not self.cmap:
            painter.fillRect(self.rect(), Qt.GlobalColor.gray)
            return

        gradient = self._create_q_linear_gradient(self.width(), 0)
        painter.fillRect(self.rect(), QBrush(gradient))

    def _create_q_linear_gradient(self, width: int, height: int) -> QLinearGradient:
        gradient = QLinearGradient(0, 0, width, height)
        if self.cmap.map_type == 'gradient':
            for stop in self.cmap.gradient_points:
                gradient.setColorAt(stop.pos, QColor(*stop.color))
        elif self.cmap.map_type == 'indexed':
            num_colors = len(self.cmap.colors)
            if num_colors > 0:
                for i, color_rgba in enumerate(self.cmap.colors):
                    pos = i / (num_colors - 1) if num_colors > 1 else 0.0
                    gradient.setColorAt(pos, QColor(*color_rgba))
        return gradient

class NodeItem(QGraphicsEllipseItem):
    """ノードアイテム"""

    def __init__(self, pos_value: float, color: list, radius: int = 8):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.pos_value = pos_value
        self.color_value = color
        self.setBrush(QBrush(QColor(*color)))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_color(self, color: list):
        self.color_value = color
        self.setBrush(QBrush(QColor(*color)))

    def set_pos_from_value(self, pos: float):
        """0-1の論理的位置から実際の描画位置を設定"""
        self.pos_value = pos
        if self.scene():
            y_pos = self.scene().height() / 2
            x_pos = pos * self.scene().width()
            self.setPos(x_pos, y_pos)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # X軸方向の移動に制限し、Y軸は中央に固定
            new_x = max(0, min(value.x(), self.scene().width()))
            new_pos = QPointF(new_x, self.scene().height() / 2)
            # 新しい論理的位置を更新
            self.pos_value = new_x / self.scene().width() if self.scene().width() > 0 else 0.0
            self.scene().parent().on_nodes_changed(final_change=False) # 継続的な変更を通知
            return new_pos
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.scene().parent().on_nodes_changed(final_change='start_drag')
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.scene().parent().on_nodes_changed(final_change=True)
        super().mouseReleaseEvent(event)

class NodeEditorScene(QGraphicsScene):
    """ノードエディタシーン"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 600, 100)

    def add_node(self, pos: float, color: list) -> NodeItem:
        node = NodeItem(pos, color)
        self.addItem(node)
        node.set_pos_from_value(pos) # 初期位置を設定
        return node

    def contextMenuEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        if isinstance(item, NodeItem):
            menu = QMenu()
            remove_action = menu.addAction("ノード削除")
            action = menu.exec(event.screenPos())
            if action == remove_action:
                self.removeItem(item)
                self.parent().on_nodes_changed(final_change=True)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos().x() / self.width()
            self.add_node(pos, [255, 255, 255, 255])
            self.parent().on_nodes_changed(final_change=True)
        super().mouseDoubleClickEvent(event)

class NodeEditorView(QGraphicsView):
    """ノードエディタビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(NodeEditorScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(100)

    def set_nodes(self, points: list[dict]):
        self.scene().clear()
        for pt in points:
            self.scene().add_node(pt.get('pos', 0.0), pt.get('color', [255, 255, 255, 255]))

    def get_nodes(self) -> list[dict]:
        nodes = [item for item in self.scene().items() if isinstance(item, NodeItem)]
        return sorted(
            [{'pos': node.pos_value, 'color': node.color_value} for node in nodes],
            key=lambda x: x['pos']
        )

    def on_nodes_changed(self, final_change=False):
        # イベントをColormapEditorに中継
        if hasattr(self.parent(), 'on_node_editor_changed'):
            self.parent().on_node_editor_changed(final_change=final_change)