
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QLineEdit
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt

from .widgets import GradientPreviewWidget, NodeEditorView

class UIManager:
    """ColormapEditorのUI要素の作成と管理を担当するクラス"""

    def __init__(self, main_window):
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        """UIの全体的なレイアウトを初期化"""
        main_widget = QWidget()
        self.main_window.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        self._create_actions()
        self._create_menu_bar()

        left_panel = self._create_left_panel()
        center_panel = self._create_center_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(center_panel, 1)
        main_layout.addWidget(right_panel)

    def _create_actions(self):
        """メニューバーのアクションを作成"""
        self.main_window.new_action = QAction("新規作成", self.main_window)
        self.main_window.new_action.setEnabled(False)

        self.main_window.open_action = QAction("開く...", self.main_window)
        self.main_window.save_action = QAction("上書き保存", self.main_window)
        self.main_window.save_as_action = QAction("名前を付けて保存...", self.main_window)

        self.main_window.undo_action = QAction("元に戻す", self.main_window)
        self.main_window.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.main_window.undo_action.setEnabled(False)

        self.main_window.redo_action = QAction("やり直し", self.main_window)
        self.main_window.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.main_window.redo_action.setEnabled(False)

    def _create_menu_bar(self):
        """メニューバーを作成"""
        menu_bar = self.main_window.menuBar()
        file_menu = menu_bar.addMenu("ファイル")
        file_menu.addAction(self.main_window.new_action)
        file_menu.addSeparator()
        file_menu.addAction(self.main_window.open_action)
        file_menu.addAction(self.main_window.save_action)
        file_menu.addAction(self.main_window.save_as_action)

        edit_menu = menu_bar.addMenu("編集")
        edit_menu.addAction(self.main_window.undo_action)
        edit_menu.addAction(self.main_window.redo_action)

    def _create_left_panel(self) -> QWidget:
        """左パネル（ファイル情報、カラーマップリスト）を作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setFixedWidth(250)

        self.main_window.file_name_label = QLabel("File: (None)")
        self.main_window.pack_name_label = QLabel("Pack: (None)")
        self.main_window.colormap_list = QListWidget()

        self.main_window.add_button = QPushButton("Add")
        self.main_window.copy_button = QPushButton("Copy")
        self.main_window.rename_button = QPushButton("Rename")
        self.main_window.remove_button = QPushButton("Remove")

        btn_layout1 = QHBoxLayout()
        btn_layout1.addWidget(self.main_window.add_button)
        btn_layout1.addWidget(self.main_window.copy_button)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.main_window.rename_button)
        btn_layout2.addWidget(self.main_window.remove_button)

        layout.addWidget(self.main_window.file_name_label)
        layout.addWidget(self.main_window.pack_name_label)
        layout.addWidget(self.main_window.colormap_list)
        layout.addLayout(btn_layout1)
        layout.addLayout(btn_layout2)

        return panel

    def _create_center_panel(self) -> QWidget:
        """中央パネル（グラディエントプレビュー、ノードエディタ）を作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.main_window.gradient_preview = GradientPreviewWidget()
        self.main_window.gradient_preview.setFixedHeight(150)
        self.main_window.node_editor = NodeEditorView(self.main_window)

        self.main_window.direct_edit_label = QLabel("ダイレクト編集モード: グラデーションをクリックして色を編集")
        self.main_window.direct_edit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_window.direct_edit_label.setVisible(False)

        layout.addWidget(QLabel("Gradient Preview"))
        layout.addWidget(self.main_window.gradient_preview)
        layout.addWidget(QLabel("Node Editor"))
        layout.addWidget(self.main_window.node_editor)
        layout.addWidget(self.main_window.direct_edit_label)

        return panel

    def _create_right_panel(self) -> QWidget:
        """右パネル（ノード情報、ユーティリティ）を作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setFixedWidth(300)

        self.main_window.color_picker_button = QPushButton("色を選択")
        self.main_window.color_picker_button.setMinimumHeight(40)
        self.main_window.color_picker_button.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")

        node_info_layout = QVBoxLayout()
        node_info_layout.addWidget(QLabel("Node Info"))
        self.main_window.node_color_edit = QLineEdit()
        self.main_window.node_color_edit.setPlaceholderText("Color: #RRGGBBAA")
        node_info_layout.addWidget(self.main_window.node_color_edit)
        self.main_window.node_pos_edit = QLineEdit()
        self.main_window.node_pos_edit.setPlaceholderText("Position: 0.0")
        node_info_layout.addWidget(self.main_window.node_pos_edit)

        utilities_layout = QVBoxLayout()
        utilities_layout.addWidget(QLabel("Utilities"))
        self.main_window.random_generate_button = QPushButton("Random Generate")
        self.main_window.extract_image_button = QPushButton("Extract from Image")
        self.main_window.flip_button = QPushButton("Flip Horizontal")
        utilities_layout.addWidget(self.main_window.random_generate_button)
        utilities_layout.addWidget(self.main_window.extract_image_button)
        utilities_layout.addWidget(self.main_window.flip_button)

        layout.addWidget(self.main_window.color_picker_button)
        layout.addLayout(node_info_layout)
        layout.addStretch()
        layout.addLayout(utilities_layout)

        return panel

    def update_ui_from_state(self, state_manager):
        """現在の状態に基づいてUIを更新"""
        color_pack = state_manager.get_current_state()
        if color_pack:
            file_path = getattr(color_pack, 'file_path', None)
            self.main_window.file_name_label.setText(f"File: {os.path.basename(file_path) if file_path else '(None)'}")
            self.main_window.pack_name_label.setText(f"Pack: {color_pack.pack_name}")
            
            current_map_name = self.main_window.get_selected_colormap_name()
            self.main_window.colormap_list.clear()
            new_selection_row = -1
            for i, cmap in enumerate(color_pack.maps):
                self.main_window.colormap_list.addItem(cmap.map_name)
                if cmap.map_name == current_map_name:
                    new_selection_row = i
            
            if new_selection_row != -1:
                self.main_window.colormap_list.setCurrentRow(new_selection_row)
            elif self.main_window.colormap_list.count() > 0:
                self.main_window.colormap_list.setCurrentRow(0)
        else:
            self.main_window.file_name_label.setText("File: (None)")
            self.main_window.pack_name_label.setText("Pack: (None)")
            self.main_window.colormap_list.clear()

        self.main_window.undo_action.setEnabled(state_manager.can_undo())
        self.main_window.redo_action.setEnabled(state_manager.can_redo())
        self.main_window.new_action.setEnabled(color_pack is not None)
