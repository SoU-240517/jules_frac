
import copy
from typing import List, Optional
from models.colormap import ColorPack, Colormap

class ColormapStateManager:
    """カラーマップエディタの状態（アンドゥ/リドゥ履歴を含む）を管理する"""

    def __init__(self, max_history_size: int = 50):
        self.undo_stack: List[ColorPack] = []
        self.redo_stack: List[ColorPack] = []
        self.current_color_pack: Optional[ColorPack] = None
        self.max_history_size = max_history_size

    def get_current_state(self) -> Optional[ColorPack]:
        """現在のカラーパックの状態を取得"""
        return self.current_color_pack

    def set_current_state(self, color_pack: Optional[ColorPack]):
        """新しいカラーパックの状態でエディタを初期化"""
        self.current_color_pack = color_pack
        self.undo_stack.clear()
        self.redo_stack.clear()

    def save_state_for_undo(self):
        """現在の状態をアンドゥスタックに保存"""
        if not self.current_color_pack:
            return
        
        # スタックの最後の状態と現在の状態が同じ場合は保存しない
        if self.undo_stack and self.undo_stack[-1] == self.current_color_pack:
            return

        self.undo_stack.append(copy.deepcopy(self.current_color_pack))
        self.redo_stack.clear() # やり直し履歴はクリア

        # 履歴が最大サイズを超えたら古いものから削除
        if len(self.undo_stack) > self.max_history_size:
            self.undo_stack.pop(0)

    def undo(self) -> Optional[ColorPack]:
        """状態を一つ前に戻す"""
        if not self.can_undo():
            return None
        
        self.redo_stack.append(copy.deepcopy(self.current_color_pack))
        self.current_color_pack = self.undo_stack.pop()
        return self.current_color_pack

    def redo(self) -> Optional[ColorPack]:
        """元に戻した状態をやり直す"""
        if not self.can_redo():
            return None

        self.undo_stack.append(copy.deepcopy(self.current_color_pack))
        self.current_color_pack = self.redo_stack.pop()
        return self.current_color_pack

    def can_undo(self) -> bool:
        """元に戻す操作が可能か"""
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        """やり直し操作が可能か"""
        return bool(self.redo_stack)
