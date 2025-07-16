import sys
import json
import os
import random
from PyQt6.QtWidgets import QApplication, QMainWindow, QInputDialog, QColorDialog
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QTimer

from settings_manager import SettingsManager
from logger.custom_logger import CustomLogger
from models.colormap import ColorPack, Colormap, ColorStop
from .widgets import NodeItem
from .utils import ColormapUtils
from .state_manager import ColormapStateManager
from .ui_manager import UIManager
from .file_handler import ColormapFileHandler

# ロガーインスタンスの初期化
logger = CustomLogger()


class ColormapEditor(QMainWindow):
    """
    カラーマップエディタのメインウィンドウクラス。

    フラクタル生成アプリケーション用のカラーマップ（色彩パレット）を作成・編集するための
    専用エディタです。グラデーション形式とインデックス形式の両方のカラーマップに対応し、
    ノードベースの直感的な編集インターフェースを提供します。

    主な機能：
    - カラーパックの新規作成・読み込み・保存
    - カラーマップの追加・削除・複製・名前変更
    - ノードエディタによる色と位置の調整
    - プレビュー機能によるリアルタイム確認
    - アンドゥ・リドゥ機能
    - ランダム生成機能
    - 画像からの色抽出機能
    """

    def __init__(self, parent=None, pack_name=None, map_name=None):
        """
        カラーマップエディタを初期化します。

        Args:
            parent: 親ウィンドウ（オプション）
            pack_name (str, optional): 起動時に読み込むカラーパック名
            map_name (str, optional): 起動時に選択するカラーマップ名
        """
        super().__init__(parent)
        self.setWindowTitle("カラーマップエディター")
        self.setGeometry(100, 100, 1200, 700)

        # 内部状態の初期化
        self._selected_node = None  # 現在選択されているノード

        # プレビュー更新用のタイマー（パフォーマンス最適化のため遅延更新）
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._delayed_update_preview)

        # 各種マネージャーの初期化
        self.settings_manager = SettingsManager()
        self.load_settings()

        self.state_manager = ColormapStateManager()  # 状態管理（アンドゥ・リドゥ）
        self.ui_manager = UIManager(self)            # UI管理
        self.file_handler = ColormapFileHandler(self)  # ファイル操作

        # シグナル・スロット接続の設定
        self._setup_connections()

        # 指定されたカラーパックがある場合は読み込み
        if pack_name:
            self.load_initial_pack(pack_name, map_name)

    def load_settings(self):
        """
        設定ファイルからカラーマップエディタ固有の設定を読み込みます。

        読み込む設定項目：
        - random_generate_max_count: ランダム生成時の最大生成数
        - random_generate_max_nodes: ランダム生成時の最大ノード数
        - extract_image_max_maps: 画像抽出時の最大マップ数
        """
        self.random_generate_max_count = self.settings_manager.get_setting(
            "colormap_editor_settings.random_generate_max_count", 30)
        self.random_generate_max_nodes = self.settings_manager.get_setting(
            "colormap_editor_settings.random_generate_max_nodes", 20)
        self.extract_image_max_maps = self.settings_manager.get_setting(
            "colormap_editor_settings.extract_image_max_maps", 30)

    def _setup_connections(self):
        """
        UI要素のシグナルを対応するスロットに接続します。

        PyQt6のシグナル・スロット機構を使用して、ユーザーの操作に対する
        適切なレスポンスを設定します。接続される要素：
        - メニューアクション（新規・開く・保存・アンドゥ・リドゥ）
        - ツールバーボタン（追加・削除・コピー・名前変更・反転・生成）
        - ウィジェット（リスト選択・プレビュー・ノードエディタ・入力フィールド）
        """
        # メニューアクション
        self.new_action.triggered.connect(self.new_file)
        self.open_action.triggered.connect(self.open_file)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action.triggered.connect(self.redo)

        # ツールバーボタン
        self.add_button.clicked.connect(self.add_colormap)
        self.copy_button.clicked.connect(self.copy_colormap)
        self.rename_button.clicked.connect(self.rename_colormap)
        self.remove_button.clicked.connect(self.remove_colormap)
        self.flip_button.clicked.connect(self.on_flip_horizontal)
        self.random_generate_button.clicked.connect(self.on_random_generate)
        self.extract_image_button.clicked.connect(self.on_extract_from_image)
        self.color_picker_button.clicked.connect(self.open_color_picker)

        # メインウィジェット
        self.colormap_list.currentItemChanged.connect(
            self.on_colormap_selected)
        self.gradient_preview.color_changed_at.connect(
            self.on_direct_edit_color_changed)
        self.node_editor.scene().selectionChanged.connect(self.on_node_selected)
        self.node_color_edit.editingFinished.connect(self.on_node_color_edit)
        self.node_pos_edit.editingFinished.connect(self.on_node_pos_edit)

    def load_initial_pack(self, pack_name, map_name):
        """
        起動時に指定されたカラーパックとマップを読み込みます。

        plugins/colorpacksディレクトリ内のJSONファイルを検索し、
        指定されたpack_nameに一致するカラーパックを読み込みます。
        読み込み成功後、指定されたmap_nameのカラーマップを選択します。

        Args:
            pack_name (str): 読み込むカラーパック名
            map_name (str): 選択するカラーマップ名
        """
        colorpacks_dir = os.path.join(os.getcwd(), 'plugins', 'colorpacks')
        if not os.path.isdir(colorpacks_dir):
            return

        # colorpacksディレクトリ内のJSONファイルを検索
        for fname in os.listdir(colorpacks_dir):
            if fname.lower().endswith('.json'):
                file_path = os.path.join(colorpacks_dir, fname)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 指定されたpack_nameと一致するかチェック
                    if data.get("pack_name") == pack_name:
                        color_pack = ColorPack.from_dict(data)
                        color_pack.file_path = file_path
                        self.state_manager.set_current_state(color_pack)
                        self.ui_manager.update_ui_from_state(
                            self.state_manager)
                        self.select_initial_map(map_name)
                        break
                except (json.JSONDecodeError, KeyError) as e:
                    logger.log(
                        f"無効なカラーパックファイルをスキップ: {fname}, エラー: {e}", level="DEBUG")

    def select_initial_map(self, map_name):
        """
        指定された名前のカラーマップを選択します。

        完全一致を優先し、見つからない場合は部分一致で検索します。
        カラーマップリストが空の場合や、map_nameが指定されていない場合は何もしません。

        Args:
            map_name (str): 選択するカラーマップ名
        """
        if not map_name or self.colormap_list.count() == 0:
            return

        # 完全一致で検索
        for i in range(self.colormap_list.count()):
            if self.colormap_list.item(i).text() == map_name:
                self.colormap_list.setCurrentRow(i)
                return

        # 完全一致がない場合は部分一致で検索
        for i in range(self.colormap_list.count()):
            if map_name.lower() in self.colormap_list.item(i).text().lower():
                self.colormap_list.setCurrentRow(i)
                return

    # --- ファイル操作 ---
    def new_file(self):
        """
        新しいカラーパックを作成します。

        現在の状態をクリアし、空の状態でUIを更新します。
        未保存の変更がある場合の確認は行わないため、必要に応じて
        呼び出し元で確認処理を実装してください。
        """
        self.state_manager.set_current_state(None)
        self.ui_manager.update_ui_from_state(self.state_manager)
        self.on_colormap_selected(None, None)

    def open_file(self):
        """
        既存のカラーパックファイルを開きます。

        ファイルハンドラーを使用してファイル選択ダイアログを表示し、
        選択されたファイルを読み込みます。読み込み成功時は状態を更新し、
        最初のカラーマップを選択状態にします。
        """
        color_pack = self.file_handler.open_file()
        if color_pack:
            self.state_manager.set_current_state(color_pack)
            self.ui_manager.update_ui_from_state(self.state_manager)
            if self.colormap_list.count() > 0:
                self.colormap_list.setCurrentRow(0)

    def save_file(self):
        """
        現在のカラーパックを保存します。

        既存のファイルパスがある場合はそのパスに保存し、
        ない場合は名前を付けて保存ダイアログを表示します。
        カラーパックが存在しない場合は何もしません。
        """
        color_pack = self.state_manager.get_current_state()
        if not color_pack:
            return

        file_path = getattr(color_pack, 'file_path', None)
        if file_path:
            self.file_handler.save_to_file(file_path, color_pack)
        else:
            self.save_file_as()

    def save_file_as(self):
        """
        現在のカラーパックに名前を付けて保存します。

        ファイル選択ダイアログを表示し、指定されたパスに保存します。
        保存成功時は新しいファイルパスで状態を更新します。
        """
        color_pack = self.state_manager.get_current_state()
        if color_pack:
            updated_pack = self.file_handler.save_file_as(color_pack)
            if updated_pack:
                self.state_manager.set_current_state(updated_pack)
                self.ui_manager.update_ui_from_state(self.state_manager)

    # --- アンドゥ・リドゥ ---
    def undo(self):
        """
        直前の操作を取り消します。

        状態管理マネージャーを使用して前の状態に戻し、UIを更新します。
        取り消し可能な操作がない場合は何もしません。
        """
        if self.state_manager.can_undo():
            self.state_manager.undo()
            self.ui_manager.update_ui_from_state(self.state_manager)
            self.on_colormap_selected(self.colormap_list.currentItem(), None)

    def redo(self):
        """
        取り消した操作をやり直します。

        状態管理マネージャーを使用して次の状態に進み、UIを更新します。
        やり直し可能な操作がない場合は何もしません。
        """
        if self.state_manager.can_redo():
            self.state_manager.redo()
            self.ui_manager.update_ui_from_state(self.state_manager)
            self.on_colormap_selected(self.colormap_list.currentItem(), None)

    # --- カラーマップ操作 ---
    def get_selected_colormap(self) -> Colormap | None:
        """
        現在選択されているカラーマップを取得します。

        Returns:
            Colormap | None: 選択されているカラーマップ、または選択されていない場合はNone
        """
        color_pack = self.state_manager.get_current_state()
        if not color_pack:
            return None
        row = self.colormap_list.currentRow()
        if 0 <= row < len(color_pack.maps):
            return color_pack.maps[row]
        return None

    def get_selected_colormap_name(self) -> str | None:
        """
        現在選択されているカラーマップの名前を取得します。

        Returns:
            str | None: カラーマップ名、または選択されていない場合はNone
        """
        item = self.colormap_list.currentItem()
        return item.text() if item else None

    def on_colormap_selected(self, current, previous):
        """
        カラーマップが選択された時の処理を行います。

        選択されたカラーマップに応じて、プレビューとエディタの表示を更新します。
        ノード数が多い場合（30個超）は直接編集モードに切り替えます。

        Args:
            current: 現在選択されているアイテム
            previous: 前に選択されていたアイテム
        """
        selected_map = self.get_selected_colormap()
        if selected_map:
            self.gradient_preview.set_colormap(selected_map)

            # ノード数に応じてエディタ表示を切り替え（パフォーマンス最適化）
            num_nodes = len(selected_map.gradient_points) if selected_map.map_type == 'gradient' else len(
                selected_map.colors)
            use_direct_edit = num_nodes > 30

            self.node_editor.setVisible(not use_direct_edit)
            self.direct_edit_label.setVisible(use_direct_edit)
            self.gradient_preview.set_direct_edit_mode(use_direct_edit)

            if not use_direct_edit:
                # 通常のノードエディタモード
                if selected_map.map_type == 'gradient':
                    points = [{'pos': p.pos, 'color': p.color}
                              for p in selected_map.gradient_points]
                    self.node_editor.set_nodes(points)
                elif selected_map.map_type == 'indexed':
                    # インデックス形式を位置ベースに変換
                    n = len(selected_map.colors)
                    points = [{'pos': i / (n - 1) if n > 1 else 0.0, 'color': c}
                              for i, c in enumerate(selected_map.colors)]
                    self.node_editor.set_nodes(points)
            else:
                # 直接編集モード（ノード数が多い場合）
                self.node_editor.set_nodes([])
        else:
            # 選択解除時の処理
            self.gradient_preview.set_colormap(None)
            self.node_editor.set_nodes([])
            self.node_editor.setVisible(True)
            self.direct_edit_label.setVisible(False)
            self.gradient_preview.set_direct_edit_mode(False)

    def add_colormap(self):
        """
        新しいカラーマップを追加します。

        デフォルトで赤から青へのグラデーションを持つカラーマップを作成し、
        現在のカラーパックに追加します。カラーパックが存在しない場合は
        新しいカラーパックも作成します。
        """
        self.state_manager.save_state_for_undo()
        color_pack = self.state_manager.get_current_state()
        if color_pack is None:
            color_pack = ColorPack(pack_name="New Pack")
            self.state_manager.set_current_state(color_pack)

        # デフォルトの赤→青グラデーションを作成
        new_map = Colormap(
            map_name=f"New Map {len(color_pack.maps) + 1}",
            map_type="gradient",
            gradient_points=[
                ColorStop(pos=0.0, color=[255, 0, 0, 255]),  # 赤
                ColorStop(pos=1.0, color=[0, 0, 255, 255])   # 青
            ]
        )
        color_pack.maps.append(new_map)
        self.ui_manager.update_ui_from_state(self.state_manager)
        self.colormap_list.setCurrentRow(len(color_pack.maps) - 1)

    def remove_colormap(self):
        """
        選択されているカラーマップを削除します。

        現在選択されているカラーマップをカラーパックから削除し、
        UIを更新します。有効な選択がない場合は何もしません。
        """
        color_pack = self.state_manager.get_current_state()
        row = self.colormap_list.currentRow()
        if color_pack and 0 <= row < len(color_pack.maps):
            self.state_manager.save_state_for_undo()
            del color_pack.maps[row]
            self.ui_manager.update_ui_from_state(self.state_manager)

    def rename_colormap(self):
        """
        選択されているカラーマップの名前を変更します。

        入力ダイアログを表示してユーザーに新しい名前を入力してもらい、
        確定された場合はカラーマップの名前を更新します。
        """
        selected_map = self.get_selected_colormap()
        if selected_map:
            new_name, ok = QInputDialog.getText(
                self, "名前変更", "新しいカラーマップ名:", text=selected_map.map_name)
            if ok and new_name:
                self.state_manager.save_state_for_undo()
                selected_map.map_name = new_name
                self.ui_manager.update_ui_from_state(self.state_manager)

    def copy_colormap(self):
        """
        選択されているカラーマップを複製します。

        現在選択されているカラーマップの完全なコピーを作成し、
        新しい名前を付けて元のマップの直後に挿入します。
        """
        color_pack = self.state_manager.get_current_state()
        row = self.colormap_list.currentRow()
        if color_pack and 0 <= row < len(color_pack.maps):
            original_map = color_pack.maps[row]
            new_name, ok = QInputDialog.getText(
                self, "コピー", "新しいカラーマップ名:", text=f"{original_map.map_name} Copy")
            if ok and new_name:
                self.state_manager.save_state_for_undo()
                new_map = Colormap.from_dict(original_map.to_dict())  # ディープコピー
                new_map.map_name = new_name
                color_pack.maps.insert(row + 1, new_map)
                self.ui_manager.update_ui_from_state(self.state_manager)
                self.colormap_list.setCurrentRow(row + 1)

    # --- ノード編集 ---
    def on_node_editor_changed(self, final_change=False):
        """
        ノードエディタでの変更を処理します。

        パフォーマンス最適化のため、ドラッグ中は遅延更新を使用し、
        最終的な変更時のみアンドゥ用の状態を保存します。

        Args:
            final_change: 最終的な変更かどうか（'start_drag'、True、Falseのいずれか）
        """
        if final_change == 'start_drag':
            self._update_colormap_from_nodes()
            self.state_manager.save_state_for_undo()
            return

        if final_change:
            # 最終変更時：タイマーを停止し、状態を保存して即座に更新
            self._update_timer.stop()
            self.state_manager.save_state_for_undo()
            self._update_colormap_from_nodes()
        else:
            # 中間変更時：遅延更新タイマーを開始（50ms後に更新）
            self._update_timer.start(50)

    def _delayed_update_preview(self):
        """
        遅延更新タイマーによって呼び出されるプレビュー更新処理。

        ノード編集中のパフォーマンス最適化のため、連続する変更を
        まとめて処理します。
        """
        self._update_colormap_from_nodes()

    def _update_colormap_from_nodes(self):
        """
        ノードエディタの状態からカラーマップを更新します。

        ノードエディタから取得した位置と色の情報を使用して、
        選択されているカラーマップのグラデーションポイントを更新し、
        プレビューに反映します。
        """
        selected_map = self.get_selected_colormap()
        if not selected_map:
            return

        nodes = self.node_editor.get_nodes()

        # 常にgradient形式として更新（統一性のため）
        selected_map.map_type = 'gradient'
        selected_map.gradient_points = [
            ColorStop(pos=n['pos'], color=n['color']) for n in nodes]
        selected_map.colors.clear()  # indexedデータはクリア

        self.gradient_preview.set_colormap(selected_map)

    def on_direct_edit_color_changed(self, pos, color):
        """
        直接編集モードで色が変更された時の処理を行います。

        プレビューエリアでの直接的な色変更に対応し、指定された位置に
        新しい色ポイントを追加します。インデックス形式のカラーマップは
        自動的にグラデーション形式に変換されます。

        Args:
            pos (float): 色を変更する位置（0.0-1.0）
            color (QColor): 新しい色
        """
        selected_map = self.get_selected_colormap()
        if not selected_map:
            return

        self.state_manager.save_state_for_undo()
        rgba = [color.red(), color.green(), color.blue(), color.alpha()]

        # インデックス形式からグラデーション形式への自動変換
        if selected_map.map_type == 'indexed':
            n = len(selected_map.colors)
            selected_map.gradient_points = [
                ColorStop(pos=i / (n - 1) if n > 1 else 0.0, color=c) for i, c in enumerate(selected_map.colors)
            ]
            selected_map.colors.clear()
            selected_map.map_type = 'gradient'

        # 新しい色ポイントを追加し、位置順にソート
        selected_map.gradient_points.append(ColorStop(pos=pos, color=rgba))
        selected_map.gradient_points.sort(key=lambda p: p.pos)

        self.gradient_preview.set_colormap(selected_map)

    def on_node_selected(self):
        """
        ノードエディタでノードが選択された時の処理を行います。

        選択されたノードの色と位置の情報を取得し、対応する入力フィールドに
        表示します。選択が解除された場合は入力フィールドをクリアします。
        カラーピッカーボタンの表示も更新します。
        """
        selected_items = self.node_editor.scene().selectedItems()
        if selected_items and isinstance(selected_items[0], NodeItem):
            self._selected_node = selected_items[0]
            rgba = self._selected_node.color_value
            # 16進数形式で色を表示（#RRGGBBAA）
            self.node_color_edit.setText(
                f'#{rgba[0]:02X}{rgba[1]:02X}{rgba[2]:02X}{rgba[3]:02X}')
            # 位置を小数点4桁で表示
            self.node_pos_edit.setText(f'{self._selected_node.pos_value:.4f}')
        else:
            # 選択解除時の処理
            self._selected_node = None
            self.node_color_edit.clear()
            self.node_pos_edit.clear()
        self._update_color_picker_button()

    def on_node_color_edit(self):
        """
        ノードの色入力フィールドが編集された時の処理を行います。

        16進数形式（#RRGGBB または #RRGGBBAA）の色文字列を解析し、
        選択されているノードの色を更新します。不正な形式の場合は無視します。
        """
        if not self._selected_node:
            return

        text = self.node_color_edit.text().lstrip('#')
        if len(text) == 6:
            text += 'FF'  # アルファ値が省略された場合は不透明に設定

        if len(text) == 8:
            try:
                # 16進数文字列をRGBA値に変換
                rgba = [int(text[i:i+2], 16) for i in range(0, 8, 2)]
                self._selected_node.set_color(rgba)
                self.on_node_editor_changed(final_change=True)
                self._update_color_picker_button()
            except ValueError:
                pass  # 不正な形式は無視

    def on_node_pos_edit(self):
        """
        ノードの位置入力フィールドが編集された時の処理を行います。

        入力された数値を0.0-1.0の範囲に制限し、選択されているノードの
        位置を更新します。不正な形式の場合は無視します。
        """
        if not self._selected_node:
            return

        try:
            # 0.0-1.0の範囲に制限
            pos = max(0.0, min(1.0, float(self.node_pos_edit.text())))
            self._selected_node.set_pos_from_value(pos)
            self.on_node_editor_changed(final_change=True)
        except ValueError:
            pass  # 不正な形式は無視

    def open_color_picker(self):
        """
        カラーピッカーダイアログを開いてノードの色を変更します。

        現在選択されているノードの色を初期値としてカラーピッカーを表示し、
        ユーザーが選択した色でノードを更新します。選択されたノードがない場合は何もしません。
        """
        if not self._selected_node:
            return

        initial_color = QColor(*self._selected_node.color_value)
        color = QColorDialog.getColor(initial_color, self, "色を選択")
        if color.isValid():
            rgba = [color.red(), color.green(), color.blue(), color.alpha()]
            self._selected_node.set_color(rgba)
            # 入力フィールドも更新
            self.node_color_edit.setText(
                f'#{rgba[0]:02X}{rgba[1]:02X}{rgba[2]:02X}{rgba[3]:02X}')
            self.on_node_editor_changed(final_change=True)
            self._update_color_picker_button()

    def on_flip_horizontal(self):
        """
        選択されているカラーマップを水平方向に反転します。

        グラデーション形式の場合は各ポイントの位置を1.0から引いて反転し、
        インデックス形式の場合は色の配列を逆順にします。
        カラーマップが選択されていない場合はエラーメッセージを表示します。
        """
        selected_map = self.get_selected_colormap()
        if not selected_map:
            ColormapUtils.show_error_message(self, "エラー", "カラーマップが選択されていません")
            return

        self.state_manager.save_state_for_undo()
        if selected_map.map_type == "gradient":
            # グラデーションポイントの位置を反転
            for point in selected_map.gradient_points:
                point.pos = 1.0 - point.pos
            # 位置順に再ソート
            selected_map.gradient_points.sort(key=lambda p: p.pos)
        elif selected_map.map_type == "indexed":
            # インデックス形式の場合は色配列を逆順に
            selected_map.colors.reverse()

        # UIを更新
        self.on_colormap_selected(self.colormap_list.currentItem(), None)

    # --- ユーティリティ ---
    def on_random_generate(self):
        """
        ランダムなカラーマップを生成します。

        ユーザーが指定したパラメータに基づいて、ランダムな色配置を持つ
        カラーマップを複数生成します。グラデーション形式とインデックス形式の
        両方に対応し、設定で指定された最大値の範囲内で生成します。
        """
        # ユーザーからランダム生成パラメータを取得
        params = ColormapUtils.get_random_generate_params(
            self, self.random_generate_max_count, self.random_generate_max_nodes
        )
        if not all(p is not None for p in params):
            return
        num_to_generate, map_type, min_nodes, max_nodes = params

        self.state_manager.save_state_for_undo()
        color_pack = self.state_manager.get_current_state()
        if color_pack is None:
            color_pack = ColorPack(pack_name="New Pack")
            self.state_manager.set_current_state(color_pack)

        # 指定された数だけランダムカラーマップを生成
        for _ in range(num_to_generate):
            map_name = f"RandomMap{len(color_pack.maps) + 1}"
            if map_type == "gradient":
                # グラデーション形式：ランダムな位置と色のポイントを生成
                num_nodes = random.randint(min_nodes, max_nodes)
                points = ColormapUtils.random_generate_colormap(num_nodes)
                new_map = Colormap(map_name=map_name,
                                   map_type='gradient', gradient_points=points)
            else:
                # インデックス形式：ランダムな色配列を生成
                num_colors = random.randint(2, 256)
                colors = [[random.randint(0, 255) for _ in range(
                    3)] + [255] for _ in range(num_colors)]
                new_map = Colormap(map_name=map_name,
                                   map_type='indexed', colors=colors)
            color_pack.maps.append(new_map)

        # 生成されたカラーマップがある場合はUIを更新し、最後のマップを選択
        if num_to_generate > 0:
            self.ui_manager.update_ui_from_state(self.state_manager)
            self.colormap_list.setCurrentRow(len(color_pack.maps) - 1)

    def on_extract_from_image(self):
        """
        画像ファイルから色を抽出してカラーマップを作成します。

        ユーザーが選択した画像ファイルから代表的な色を抽出し、
        それらを使用してカラーマップを生成します。機械学習ライブラリ
        （scikit-learn）を使用してクラスタリングによる色抽出を行います。
        """
        # ユーザーから画像抽出パラメータを取得
        params = ColormapUtils.get_extract_image_params(
            self, self.extract_image_max_maps)
        if not all(p is not None for p in params):
            return
        file_path, num_colors, num_maps = params

        self.state_manager.save_state_for_undo()
        color_pack = self.state_manager.get_current_state()
        if color_pack is None:
            color_pack = ColorPack(pack_name="New Pack")
            self.state_manager.set_current_state(color_pack)

        try:
            # 指定された数だけ画像から色抽出を実行
            for _ in range(num_maps):
                points = ColormapUtils.extract_colors_from_image(
                    file_path, num_colors)
                map_name = f"ImageMap{len(color_pack.maps) + 1}"
                new_map = Colormap(map_name=map_name,
                                   map_type='gradient', gradient_points=points)
                color_pack.maps.append(new_map)

            # 抽出されたカラーマップがある場合はUIを更新し、最後のマップを選択
            if num_maps > 0:
                self.ui_manager.update_ui_from_state(self.state_manager)
                self.colormap_list.setCurrentRow(len(color_pack.maps) - 1)
        except ImportError:
            # 必要なライブラリがインストールされていない場合のエラー処理
            ColormapUtils.show_error_message(self, "依存ライブラリ未インストール",
                                             "Pillow, scikit-learn, numpyが必要です。\n`pip install pillow scikit-learn numpy`")
        except Exception as e:
            # その他のエラー（ファイル読み込み失敗など）の処理
            ColormapUtils.show_error_message(
                self, "抽出失敗", f"画像から色抽出に失敗しました:\n{e}")

    def _update_color_picker_button(self):
        """
        カラーピッカーボタンの表示を更新します。

        選択されているノードがある場合はそのノードの色を背景色として表示し、
        選択されていない場合はデフォルトの灰色を表示します。
        視覚的なフィードバックによりユーザーの操作性を向上させます。
        """
        if self._selected_node:
            # 選択されたノードの色を背景色として設定
            rgba = self._selected_node.color_value
            style = f"background-color: rgba({rgba[0]}, {rgba[1]}, {rgba[2]}, {rgba[3]/255}); border: 1px solid #ccc;"
        else:
            # 選択されていない場合はデフォルトの灰色
            style = "background-color: #f0f0f0; border: 1px solid #ccc;"
        self.color_picker_button.setStyleSheet(style)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # pack_name, map_name はテスト用に渡すことができます
    # editor = ColormapEditor(pack_name="classic", map_name="Classic")
    editor = ColormapEditor()
    editor.show()
    sys.exit(app.exec())
