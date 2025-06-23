# coding: utf-8
from PyQt6.QtCore import QAbstractListModel, Qt, QModelIndex
from PyQt6.QtGui import QIcon
from typing import Any, List, Dict

class ColorMapModel(QAbstractListModel):
    """
    カラーマップのデータ（名前とサムネイル）を管理するためのカスタムモデル。
    QListViewと連携してグリッド表示を実現します。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        item = self._data[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return item.get('name')
        if role == Qt.ItemDataRole.DecorationRole:
            return item.get('icon')
        return None

    def populate_data(self, data: List[Dict[str, Any]]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()
