from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QHBoxLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QTabWidget,
    QListWidget, QListWidgetItem, QAbstractSpinBox, QFileDialog,
    QInputDialog, QMessageBox, QToolBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QTimer, QEvent
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QLinearGradient, QIcon
from functools import partial
from logger.custom_logger import CustomLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controllers.fractal_controller import FractalController

logger = CustomLogger()

class ParameterPanel(QWidget):
    """
    フラクタル計算とカラーリングに関連する各種パラメータを設定するためのUIパネル。
    QToolBoxを使用して、設定をカテゴリ別に整理します。
    """
    parameters_changed_in_ui_signal = pyqtSignal(dict)

    def __init__(self, fractal_controller: 'FractalController', parent=None):
        super().__init__(parent)
        self.fractal_controller = fractal_controller
        self.plugin_widgets = {}
        self.coloring_widgets = {}
        self._focused_value_store = {}

        self.redraw_timer = QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(150)
        self.redraw_timer.timeout.connect(self._execute_redraw)
        self._redraw_request = {'full_recompute': False, 'is_preview': False, 'pending': False}

        self._init_ui()

        if self.fractal_controller:
            self._populate_fractal_combo()
            for target_type in ['divergent', 'non_divergent']:
                self._populate_coloring_algorithm_combo(target_type)
                self._populate_color_pack_combo(target_type)
            self.load_initial_parameters()
            self._connect_controller_signals()
        else:
            self._set_ui_for_no_controller()

    def _connect_controller_signals(self):
        """コントローラーからのシグナルを接続します。"""
        self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
        self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(self._on_active_fractal_plugin_changed)
        self.fractal_controller.active_coloring_plugin_ui_needs_update.connect(
            lambda algo_name: self._update_coloring_plugin_specific_ui(algo_name, self.get_active_coloring_target_type())
        )
        if hasattr(self.fractal_controller, 'active_coloring_target_and_plugin_changed_externally'):
            self.fractal_controller.active_coloring_target_and_plugin_changed_externally.connect(
                self.update_active_coloring_target_and_plugin_from_controller
            )
        else:
            logger.log("警告: FractalController に 'active_coloring_target_and_plugin_changed_externally' シグナルが存在しません。", level="WARNING")

        if hasattr(self.fractal_controller, 'active_color_map_changed_externally'):
            self.fractal_controller.active_color_map_changed_externally.connect(
                self._update_color_selection_from_controller
            )
        else:
            logger.log("警告: FractalController に 'active_color_map_changed_externally' シグナルが存在しません。", level="WARNING")

        if hasattr(self.fractal_controller, 'configuration_applied'):
            self.fractal_controller.configuration_applied.connect(self.load_initial_parameters)

    def _set_ui_for_no_controller(self):
        """コントローラーが利用できない場合のフォールバックUI設定。"""
        self._set_ui_values(100)
        if hasattr(self, 'main_tabs'): self.main_tabs.setEnabled(False)

    def _init_ui(self):
        """
        パラメータパネルのUIを初期化し、QTabWidgetを使用して配置します。
        """
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.main_tabs = QTabWidget()
        self.main_layout.addWidget(self.main_tabs)

        # --- 1. プリセットページ ---
        preset_page = self._create_preset_page()
        self.main_tabs.addTab(preset_page, "プリセット")

        # --- 2. 描画設定ページ ---
        render_settings_page = self._create_render_settings_page()
        self.main_tabs.addTab(render_settings_page, "描画設定")

        # --- 3. カラーリングページ ---
        self.coloring_tabs = QTabWidget()
        divergent_tab = self._create_coloring_tab('divergent')
        self.coloring_tabs.addTab(divergent_tab, "発散部")
        non_divergent_tab = self._create_coloring_tab('non_divergent')
        self.coloring_tabs.addTab(non_divergent_tab, "非発散部")
        self.main_tabs.addTab(self.coloring_tabs, "カラーリング")

        self._connect_ui_signals()

    def _create_preset_page(self) -> QWidget:
        """プリセット管理用のページウィジェットを作成します。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(9, 9, 9, 9)

        self._init_preset_ui_elements()
        layout.addWidget(self.preset_group_box)
        layout.addStretch(1)

        return page

    def _create_render_settings_page(self) -> QWidget:
        """描画設定用のページウィジェットを作成します。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(9, 9, 9, 9)

        fractal_group = QGroupBox("フラクタル選択")
        fractal_form_layout = QFormLayout()
        fractal_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        fractal_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.fractal_combo = QComboBox()
        fractal_form_layout.addRow(QLabel("タイプ:"), self.fractal_combo)
        fractal_group.setLayout(fractal_form_layout)
        layout.addWidget(fractal_group)

        common_params_group = QGroupBox("共通描画設定")
        self.common_params_layout = QFormLayout()
        self.common_params_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.common_params_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.center_real_spinbox = QDoubleSpinBox()
        self.center_real_spinbox.setDecimals(10); self.center_real_spinbox.setRange(-1e6, 1e6); self.center_real_spinbox.setSingleStep(0.01); self.center_real_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.common_params_layout.addRow(QLabel("中心実部:"), self.center_real_spinbox)

        self.center_imag_spinbox = QDoubleSpinBox()
        self.center_imag_spinbox.setDecimals(10); self.center_imag_spinbox.setRange(-1e6, 1e6); self.center_imag_spinbox.setSingleStep(0.01); self.center_imag_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.common_params_layout.addRow(QLabel("中心虚部:"), self.center_imag_spinbox)

        self.zoom_spinbox = QDoubleSpinBox()
        self.zoom_spinbox.setDecimals(4); self.zoom_spinbox.setRange(0.01, 1e6); self.zoom_spinbox.setSingleStep(0.01); self.zoom_spinbox.setValue(1.0); self.zoom_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.common_params_layout.addRow(QLabel("ズーム倍率:"), self.zoom_spinbox)

        self.width_label = QLabel("-")
        self.common_params_layout.addRow(QLabel("表示幅(拡大率):"), self.width_label)

        self.iter_spinbox = QSpinBox()
        self.iter_spinbox.setRange(10, 100000); self.iter_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.common_params_layout.addRow(QLabel("最大反復回数:"), self.iter_spinbox)
        common_params_group.setLayout(self.common_params_layout)
        layout.addWidget(common_params_group)

        self.plugin_specific_group = QGroupBox("フラクタル固有設定")
        self.plugin_specific_layout = QFormLayout()
        self.plugin_specific_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.plugin_specific_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.plugin_specific_group.setLayout(self.plugin_specific_layout)
        layout.addWidget(self.plugin_specific_group)
        self.plugin_specific_group.setVisible(False)

        layout.addStretch(1)
        return page

    def _connect_ui_signals(self):
        """UIウィジェットのシグナルを接続します。"""
        self.center_real_spinbox.installEventFilter(self)
        self.center_imag_spinbox.installEventFilter(self)
        self.zoom_spinbox.installEventFilter(self)
        self.iter_spinbox.installEventFilter(self)

        self.fractal_combo.currentTextChanged.connect(self._on_fractal_type_changed)

        self.iter_spinbox.editingFinished.connect(self._on_value_changed_by_ui)
        self.iter_spinbox.valueChanged.connect(self._on_common_parameter_changed_for_preview)
        self.center_real_spinbox.editingFinished.connect(self._on_value_changed_by_ui)
        self.center_imag_spinbox.editingFinished.connect(self._on_value_changed_by_ui)
        self.center_real_spinbox.valueChanged.connect(self._on_common_parameter_changed_for_preview)
        self.center_imag_spinbox.valueChanged.connect(self._on_common_parameter_changed_for_preview)
        self.zoom_spinbox.editingFinished.connect(self._on_zoom_spinbox_changed)
        self.zoom_spinbox.valueChanged.connect(self._on_zoom_spinbox_changed)

        self.export_presets_button.clicked.connect(self._on_export_presets)
        self.load_preset_button.clicked.connect(self._on_load_preset)
        self.save_preset_button.clicked.connect(self._on_save_preset)
        self.delete_preset_button.clicked.connect(self._on_delete_preset)
        self.import_presets_button.clicked.connect(self._on_import_presets)

    def _init_preset_ui_elements(self):
        """プリセット管理用のUI要素を初期化します。"""
        self.preset_group_box = QGroupBox("プリセット管理")
        preset_layout = QVBoxLayout()

        self.presets_combo_box = QComboBox()

        top_buttons_layout = QHBoxLayout()
        self.load_preset_button = QPushButton("読み込み")
        self.save_preset_button = QPushButton("保存")
        self.delete_preset_button = QPushButton("削除")
        top_buttons_layout.addWidget(self.load_preset_button)
        top_buttons_layout.addWidget(self.save_preset_button)
        top_buttons_layout.addWidget(self.delete_preset_button)

        bottom_buttons_layout = QHBoxLayout()
        self.export_presets_button = QPushButton("エクスポート")
        self.import_presets_button = QPushButton("インポート")
        bottom_buttons_layout.addWidget(self.export_presets_button)
        bottom_buttons_layout.addWidget(self.import_presets_button)

        preset_layout.addWidget(self.presets_combo_box)
        preset_layout.addLayout(top_buttons_layout)
        preset_layout.addLayout(bottom_buttons_layout)
        self.preset_group_box.setLayout(preset_layout)

    def _create_coloring_tab(self, target_type: str) -> QWidget:
        """指定されたターゲットタイプ（'divergent' または 'non_divergent'）用のUIタブを作成します。"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(9, 9, 9, 9)

        widgets = {'plugin_widgets': {}}

        algo_layout = QFormLayout()
        algo_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        algo_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['algo_combo'] = QComboBox()
        algo_layout.addRow(QLabel("アルゴリズム:"), widgets['algo_combo'])
        layout.addLayout(algo_layout)
        widgets['algo_combo'].currentTextChanged.connect(
            partial(self._on_coloring_algorithm_changed, target_type=target_type)
        )

        widgets['specific_group'] = QGroupBox("アルゴリズム固有設定")
        widgets['specific_layout'] = QFormLayout()
        widgets['specific_layout'].setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        widgets['specific_layout'].setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['specific_group'].setLayout(widgets['specific_layout'])
        layout.addWidget(widgets['specific_group'])
        widgets['specific_group'].setVisible(False)

        pack_layout = QFormLayout()
        pack_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        pack_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['pack_combo'] = QComboBox()
        pack_layout.addRow(QLabel("カラーパック:"), widgets['pack_combo'])
        layout.addLayout(pack_layout)
        widgets['pack_combo'].currentTextChanged.connect(
            partial(self._on_color_pack_changed, target_type=target_type)
        )

        map_layout = QFormLayout()
        map_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        map_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['map_list'] = QListWidget()
        widgets['map_list'].setIconSize(QSize(96, 18))
        widgets['map_list'].setSpacing(1)
        widgets['map_list'].setFixedHeight(120)
        map_layout.addRow(QLabel("カラーマップ:"), widgets['map_list'])
        layout.addLayout(map_layout)
        widgets['map_list'].currentItemChanged.connect(
            lambda current, previous, tt=target_type: self._on_color_map_changed(current, previous, tt)
        )

        layout.addStretch(1)
        self.coloring_widgets[target_type] = widgets
        return tab_widget

    def _create_colormap_thumbnail(self, colors: list[tuple[int,int,int]], thumb_width: int = 96, thumb_height: int = 18) -> QPixmap:
        if not colors:
            img = QImage(thumb_width, thumb_height, QImage.Format.Format_RGB888)
            img.fill(Qt.GlobalColor.gray)
            return QPixmap.fromImage(img)

        img = QImage(thumb_width, thumb_height, QImage.Format.Format_RGB888)
        painter = QPainter(img)

        if len(colors) == 1:
            painter.fillRect(0, 0, thumb_width, thumb_height, QColor(colors[0][0], colors[0][1], colors[0][2]))
        else:
            gradient = QLinearGradient(0, 0, thumb_width, 0)
            num_color_stops = len(colors)
            for i, color_tuple in enumerate(colors):
                position = i / (num_color_stops - 1) if num_color_stops > 1 else 0.0
                qt_color = QColor(color_tuple[0], color_tuple[1], color_tuple[2])
                gradient.setColorAt(position, qt_color)
            painter.fillRect(0, 0, thumb_width, thumb_height, gradient)

        painter.end()
        return QPixmap.fromImage(img)

    def _populate_fractal_combo(self):
        if not self.fractal_controller: return
        plugin_names = self.fractal_controller.get_available_fractal_plugin_names_from_engine()
        active_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        self.fractal_combo.blockSignals(True); self.fractal_combo.clear()
        if plugin_names:
            self.fractal_combo.addItems(plugin_names)
            if active_name and active_name in plugin_names: self.fractal_combo.setCurrentText(active_name)
            elif plugin_names: self.fractal_combo.setCurrentText(plugin_names[0])
        else: self.fractal_combo.addItem("プラグインなし"); self.fractal_combo.setEnabled(False)
        self.fractal_combo.blockSignals(False)

    def populate_presets_combo_box(self):
        if not hasattr(self, 'presets_combo_box'): return
        self.presets_combo_box.blockSignals(True)
        current_text = self.presets_combo_box.currentText()
        self.presets_combo_box.clear()
        all_presets = self.fractal_controller.settings_manager.get_presets()
        active_fractal_type = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        filtered_names = [name for name, config in all_presets.items()
                          if config.get('fractal_plugin_name') == active_fractal_type]
        if filtered_names:
            self.presets_combo_box.addItems(sorted(filtered_names))
            if current_text in filtered_names:
                self.presets_combo_box.setCurrentText(current_text)
        self.presets_combo_box.blockSignals(False)

    @pyqtSlot()
    def _on_load_preset(self):
        preset_name = self.presets_combo_box.currentText()
        if preset_name:
            self.fractal_controller.load_preset(preset_name)
        else:
            QMessageBox.warning(self, "プリセットなし", "読み込むプリセットが選択されていません。")

    @pyqtSlot()
    def _on_save_preset(self):
        preset_name, ok = QInputDialog.getText(self, "プリセットの保存", "プリセット名を入力してください:")
        if ok and preset_name:
            self.fractal_controller.save_current_config_as_preset(preset_name)
            self.populate_presets_combo_box()
            self.presets_combo_box.setCurrentText(preset_name)

    @pyqtSlot()
    def _on_delete_preset(self):
        preset_name = self.presets_combo_box.currentText()
        if not preset_name:
            QMessageBox.warning(self, "プリセットなし", "削除するプリセットが選択されていません。")
            return
        reply = QMessageBox.question(self, "プリセットの削除",
                                     f"プリセット '{preset_name}' を本当に削除しますか？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.fractal_controller.delete_preset(preset_name)
            self.populate_presets_combo_box()

    @pyqtSlot()
    def _on_export_presets(self):
        if not self.fractal_controller: return
        file_path, _ = QFileDialog.getSaveFileName(self, "プリセットをエクスポート", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            success, message = self.fractal_controller.export_presets(file_path)
            if success:
                QMessageBox.information(self, "エクスポート成功", message)
            else:
                QMessageBox.warning(self, "エクスポート失敗", message)

    @pyqtSlot()
    def _on_import_presets(self):
        if not self.fractal_controller: return
        file_path, _ = QFileDialog.getOpenFileName(self, "プリセットをインポート", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            reply = QMessageBox.question(self, "プリセットのインポート",
                                         "既存の同名プリセットを上書きしますか？\n'はい'で上書き、'いいえ'でスキップします。",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel: return
            overwrite = (reply == QMessageBox.StandardButton.Yes)
            success, message = self.fractal_controller.import_presets(file_path, overwrite)
            if success:
                QMessageBox.information(self, "インポート成功", message)
                self.populate_presets_combo_box()
            else:
                QMessageBox.warning(self, "インポート失敗", message)

    @pyqtSlot(str)
    def _on_fractal_type_changed(self, plugin_name: str):
        if self.fractal_controller and hasattr(self.fractal_controller, 'is_rendering') and self.fractal_controller.is_rendering:
            return
        if not self.fractal_controller or not plugin_name or plugin_name == "プラグインなし":
            return
        current_engine_plugin = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        if plugin_name == current_engine_plugin:
            self.populate_presets_combo_box()
            return
        self.fractal_controller.set_active_fractal_plugin_and_redraw(plugin_name)
        self.setFocus()
        self.populate_presets_combo_box()

    def request_redraw(self, full_recompute: bool, is_preview: bool = False):
        if self._redraw_request['pending'] and not self._redraw_request['is_preview'] and is_preview:
            return
        self._redraw_request['full_recompute'] = self._redraw_request.get('full_recompute', False) or full_recompute
        self._redraw_request['is_preview'] = is_preview
        self._redraw_request['pending'] = True
        self.redraw_timer.start()

    def _execute_redraw(self):
        if not self._redraw_request.get('pending', False): return
        if self.fractal_controller:
            full_recompute = self._redraw_request.get('full_recompute', False)
            is_preview = self._redraw_request.get('is_preview', False)
            self.fractal_controller.trigger_render(full_recompute=full_recompute, is_preview=is_preview)
        self._redraw_request['pending'] = False
        self._redraw_request['full_recompute'] = False
        self._redraw_request['is_preview'] = False

    def _clear_fractal_plugin_specific_ui(self):
        self.plugin_widgets.clear()
        while self.plugin_specific_layout.count():
            item = self.plugin_specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str)
    def _update_fractal_plugin_specific_ui(self, plugin_name: str):
        self._clear_fractal_plugin_specific_ui()
        if not self.fractal_controller or not plugin_name:
            self.plugin_specific_group.setVisible(False)
            return
        param_defs = self.fractal_controller.get_fractal_plugin_parameter_definitions_from_engine(plugin_name)
        if not param_defs:
            self.plugin_specific_group.setVisible(False)
            return
        self.plugin_specific_group.setVisible(True)
        self.plugin_specific_group.setTitle(f"{plugin_name} 固有設定")
        current_vals = self.fractal_controller.get_current_fractal_plugin_parameters_from_engine()
        for p_def in param_defs:
            lbl = p_def.get('label', p_def['name']); name = p_def['name']; type = p_def.get('type', 'float')
            widget = None
            if type == 'float':
                widget = QDoubleSpinBox()
                widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
                widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1])
                step_val = p_def.get('step', 1e-7)
                decimals_val = p_def.get('decimals', 15)
                widget.setDecimals(decimals_val)
                widget.setSingleStep(step_val)
                current_plugin_val = current_vals.get(name, p_def.get('default'))
                widget.setValue(current_plugin_val if current_plugin_val is not None else 0.0)
            elif type == 'int':
                widget = QSpinBox()
                widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1])
                widget.setValue(current_vals.get(name, p_def.get('default')) if current_vals.get(name, p_def.get('default')) is not None else 0)
                widget.setSingleStep(p_def.get('step',1))
            if widget:
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
                self.plugin_specific_layout.addRow(QLabel(lbl + ":"), widget)
                self.plugin_widgets[name] = widget
                if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                    widget.valueChanged.connect(partial(self._on_fractal_plugin_parameter_changed_for_preview, param_name=name))
                    widget.editingFinished.connect(partial(self._on_plugin_parameter_editing_finished, param_name=name))
                    widget.installEventFilter(self)

    @pyqtSlot()
    def _on_plugin_parameter_editing_finished(self, param_name: str):
        if not self.fractal_controller: return
        widget = self.plugin_widgets.get(param_name)
        if widget:
            original_value = self._focused_value_store.pop(widget, None)
            current_value = widget.value() if isinstance(widget, (QDoubleSpinBox, QSpinBox)) else None
            if original_value is not None and current_value != original_value:
                self.request_redraw(full_recompute=True, is_preview=False)

    def _populate_coloring_algorithm_combo(self, target_type: str):
        if not self.fractal_controller: return
        try:
            combo_box = self.coloring_widgets[target_type]['algo_combo']
        except KeyError:
            return
        algo_names = self.fractal_controller.get_available_coloring_plugin_names_from_engine(target_type=target_type)
        active_algo = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type)
        combo_box.blockSignals(True); combo_box.clear()
        if algo_names:
            combo_box.addItems(algo_names)
            if active_algo and active_algo in algo_names: combo_box.setCurrentText(active_algo)
            elif algo_names: combo_box.setCurrentText(algo_names[0])
            combo_box.setEnabled(True)
        else:
            combo_box.addItem("N/A"); combo_box.setEnabled(False)
        combo_box.blockSignals(False)

    @pyqtSlot(str, str)
    def _on_coloring_algorithm_changed(self, algo_name: str, target_type: str):
        if not self.fractal_controller or not algo_name or algo_name == "N/A":
            if algo_name == "N/A":
                self._clear_coloring_plugin_specific_ui(target_type)
                try:
                    self.coloring_widgets[target_type]['specific_group'].setVisible(False)
                except KeyError:
                    pass
            return
        if algo_name == self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type):
             self._update_coloring_plugin_specific_ui(algo_name, target_type)
             return
        self.fractal_controller.set_active_coloring_plugin_and_recolor(plugin_name=algo_name, target_type=target_type)

    def _clear_coloring_plugin_specific_ui(self, target_type: str):
        try:
            widgets = self.coloring_widgets[target_type]
            plugin_widgets = widgets['plugin_widgets']
            specific_layout = widgets['specific_layout']
        except KeyError:
            return
        plugin_widgets.clear()
        while specific_layout.count():
            item = specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str, str)
    def _update_coloring_plugin_specific_ui(self, algo_name: str, target_type: str):
        if target_type is None: target_type = self.get_active_coloring_target_type()
        self._clear_coloring_plugin_specific_ui(target_type)
        try:
            widgets = self.coloring_widgets[target_type]
            plugin_widgets = widgets['plugin_widgets']
            specific_group = widgets['specific_group']
            specific_layout = widgets['specific_layout']
        except KeyError:
            return
        if not self.fractal_controller or not algo_name or algo_name == "N/A":
            if specific_group: specific_group.setVisible(False)
            return
        param_defs = self.fractal_controller.get_coloring_plugin_parameter_definitions_from_engine(algo_name, target_type=target_type)
        if not param_defs:
            if specific_group: specific_group.setVisible(False)
            return
        if specific_group:
            specific_group.setVisible(True)
        target_display_name = "発散部" if target_type == 'divergent' else "非発散部"
        if specific_group: specific_group.setTitle(f"{algo_name} ({target_display_name}) 固有設定")
        current_vals = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine(target_type=target_type)
        presets = self.fractal_controller.get_plugin_presets(algo_name, target_type=target_type)
        if presets:
            preset_combo = QComboBox()
            preset_combo.addItem("カスタム")
            preset_combo.addItems(presets.keys())
            preset_combo.currentTextChanged.connect(
                partial(self._on_coloring_preset_selected, plugin_name=algo_name, presets_data=presets.copy(), target_type=target_type)
            )
            if specific_layout: specific_layout.addRow(QLabel("プリセット:"), preset_combo)
            if plugin_widgets: plugin_widgets['_coloring_preset_combo'] = preset_combo
        for p_def in param_defs:
            name = p_def['name']; lbl_text = p_def.get('label', name); p_type = p_def.get('type', 'float')
            default_val = p_def.get('default'); current_val = current_vals.get(name, default_val)
            widget = None
            if p_type == 'float':
                widget = QDoubleSpinBox()
                widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
                widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1])
                widget.setDecimals(p_def.get('decimals',2)); widget.setSingleStep(p_def.get('step',0.01))
                widget.setValue(current_val if current_val is not None else 0.0)
            elif p_type == 'int':
                widget = QSpinBox()
                widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1])
                widget.setSingleStep(p_def.get('step',1)); widget.setValue(current_val if current_val is not None else 0)
            if widget:
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
                if specific_layout is not None: specific_layout.addRow(QLabel(lbl_text + ":"), widget)
                plugin_widgets[name] = widget
                if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                    widget.valueChanged.connect(partial(self._on_coloring_plugin_parameter_changed_for_preview, param_name=name, target_type=target_type))
                    widget.editingFinished.connect(partial(self._on_coloring_plugin_parameter_editing_finished, param_name=name, target_type=target_type))
                    widget.installEventFilter(self)

    @pyqtSlot()
    def _on_coloring_plugin_parameter_editing_finished(self, param_name: str, target_type: str):
        if not self.fractal_controller: return
        widget = self.coloring_widgets[target_type]['plugin_widgets'].get(param_name)
        if widget and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            original_value = self._focused_value_store.pop(widget, None)
            current_value = widget.value()
            if original_value is not None and current_value != original_value:
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, current_value, target_type=target_type, allow_recolor=False)
                self.request_redraw(full_recompute=False, is_preview=False)

    def _populate_color_pack_combo(self, target_type: str):
        if not self.fractal_controller: return
        combo_box = self.coloring_widgets[target_type]['pack_combo']
        pack_names = self.fractal_controller.get_available_color_pack_names_from_engine()
        active_pack = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)
        combo_box.blockSignals(True); combo_box.clear()
        if pack_names:
            combo_box.addItems(pack_names)
            if active_pack and active_pack in pack_names: combo_box.setCurrentText(active_pack)
            elif pack_names: combo_box.setCurrentText(pack_names[0])
            combo_box.setEnabled(True)
        else:
            combo_box.addItem("N/A"); combo_box.setEnabled(False)
        combo_box.blockSignals(False)
        if combo_box.isEnabled() and combo_box.currentText() != "N/A":
             self._populate_color_map_list(combo_box.currentText(), target_type)

    @pyqtSlot(str, str)
    def _on_color_pack_changed(self, pack_name: str, target_type: str):
        if not self.fractal_controller or not pack_name or pack_name == "N/A": return
        map_list_widget = self.coloring_widgets[target_type]['map_list']
        self._populate_color_map_list(pack_name, target_type)
        if map_list_widget.count() > 0:
            first_map_item = map_list_widget.item(0)
            if first_map_item:
                map_list_widget.setCurrentItem(first_map_item)
                if self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type) != first_map_item.text() or \
                   self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type) != pack_name:
                     self.fractal_controller.set_active_color_map_and_recolor(pack_name, first_map_item.text(), target_type=target_type)

    def _populate_color_map_list(self, pack_name: str | None, target_type: str):
        map_list_widget = self.coloring_widgets[target_type]['map_list']
        map_list_widget.blockSignals(True)
        map_list_widget.clear()
        if not self.fractal_controller or not pack_name:
            map_list_widget.setEnabled(False); map_list_widget.blockSignals(False); return
        map_names = self.fractal_controller.get_color_map_names_in_pack_from_engine(pack_name)
        active_map_name = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)
        active_pack_for_target = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)
        if map_names:
            map_list_widget.setEnabled(True)
            for name_str in map_names:
                map_data = self.fractal_controller.get_color_map_data_from_engine(pack_name, name_str)
                list_item = QListWidgetItem(name_str)
                if map_data:
                    thumbnail = self._create_colormap_thumbnail(map_data)
                    list_item.setIcon(QIcon(thumbnail))
                map_list_widget.addItem(list_item)
                if name_str == active_map_name and pack_name == active_pack_for_target:
                    map_list_widget.setCurrentItem(list_item)
        else:
            map_list_widget.setEnabled(False)
        map_list_widget.blockSignals(False)

    @pyqtSlot(QListWidgetItem, QListWidgetItem, str)
    def _on_color_map_changed(self, current_item: QListWidgetItem, previous_item: QListWidgetItem, target_type: str):
        if not self.fractal_controller or not current_item: return
        map_name = current_item.text()
        pack_name = self.coloring_widgets[target_type]['pack_combo'].currentText()
        self.fractal_controller.logger.log(f"ParameterPanel._on_color_map_changed: pack={pack_name}, map={map_name}, target_type={target_type}", level="DEBUG")
        if not pack_name or pack_name == "N/A": return
        active_pack_ctrl = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)
        active_map_ctrl = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)
        if pack_name == active_pack_ctrl and map_name == active_map_ctrl:
            return
        self.fractal_controller.set_active_color_map_and_recolor(pack_name, map_name, target_type=target_type)

    @pyqtSlot(str, str, str)
    def _update_color_selection_from_controller(self, pack_name: str, map_name: str, target_type: str):
        try:
            widgets = self.coloring_widgets[target_type]
            pack_combo = widgets['pack_combo']
            map_list_widget = widgets['map_list']
        except KeyError:
            return
        pack_combo.blockSignals(True)
        map_list_widget.blockSignals(True)
        if pack_combo.currentText() != pack_name:
            items = [pack_combo.itemText(i) for i in range(pack_combo.count())]
            if pack_name not in items:
                 self._populate_color_pack_combo(target_type)
            pack_combo.setCurrentText(pack_name)
            self._populate_color_map_list(pack_name, target_type)
        else:
            if map_list_widget.count() == 0 and pack_name and pack_name != "N/A":
                self._populate_color_map_list(pack_name, target_type)
        found = False
        for i in range(map_list_widget.count()):
            item = map_list_widget.item(i)
            if item.text() == map_name:
                map_list_widget.setCurrentItem(item)
                found = True
                break
        pack_combo.blockSignals(False)
        map_list_widget.blockSignals(False)

    def _on_value_changed_by_ui(self):
        if hasattr(self, 'fractal_combo') and (self.fractal_combo.hasFocus() or self.fractal_combo.view().isVisible()):
            return
        sender_widget = self.sender()
        if not sender_widget: return
        params = self.get_current_ui_parameters()
        if self.fractal_controller:
            self.fractal_controller.handle_programmatic_parameter_change(
                cr=params["center_real"], ci=params["center_imag"],
                w=params["width"], iters=params["max_iterations"]
            )
        self.parameters_changed_in_ui_signal.emit(params)
        self._update_zoom_label(params["width"])
        trigger_render_flag = False
        if isinstance(sender_widget, (QSpinBox, QDoubleSpinBox)):
            original_value = self._focused_value_store.pop(sender_widget, None)
            current_value = sender_widget.value()
            if original_value is not None and current_value != original_value:
                trigger_render_flag = True
        if trigger_render_flag:
            if self.fractal_controller:
                self.request_redraw(full_recompute=True, is_preview=False)

    def load_initial_parameters(self):
        if self.fractal_controller:
            self.populate_presets_combo_box()
            params = self.fractal_controller.get_current_common_parameters()
            if params:
                self._set_ui_values(
                    iterations=params.get('max_iterations', 100),
                    center_real=params.get('center_real', -0.5),
                    center_imag=params.get('center_imag', 0.0),
                    width=params.get('width', 3.0)
                )
            active_fp_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
            if active_fp_name: self._update_fractal_plugin_specific_ui(active_fp_name)
            for target_type in ['divergent', 'non_divergent']:
                widgets = self.coloring_widgets[target_type]
                combo_algo = widgets['algo_combo']
                combo_pack = widgets['pack_combo']
                list_map = widgets['map_list']
                active_algo = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type)
                if active_algo and active_algo != "N/A":
                    combo_algo.blockSignals(True); combo_algo.setCurrentText(active_algo); combo_algo.blockSignals(False)
                    self._update_coloring_plugin_specific_ui(active_algo, target_type=target_type)
                elif combo_algo.count() > 0:
                    first_algo = combo_algo.itemText(0)
                    if first_algo and first_algo != "N/A": combo_algo.setCurrentText(first_algo)
                active_pack = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)
                active_map = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)
                if active_pack and active_map:
                    combo_pack.blockSignals(True); combo_pack.setCurrentText(active_pack); combo_pack.blockSignals(False)
                    self._populate_color_map_list(active_pack, target_type=target_type)
                    for i in range(list_map.count()):
                        if list_map.item(i).text() == active_map:
                            list_map.setCurrentRow(i)
                            break
                elif combo_pack.count() > 0:
                    first_pack = combo_pack.itemText(0)
                    if first_pack and first_pack != "N/A": combo_pack.setCurrentText(first_pack)

    def _set_ui_values(self, iterations: int, center_real: float = None, center_imag: float = None, width: float = None):
        self.iter_spinbox.blockSignals(True)
        self.center_real_spinbox.blockSignals(True)
        self.center_imag_spinbox.blockSignals(True)
        self.zoom_spinbox.blockSignals(True)
        self.iter_spinbox.setValue(iterations)
        if center_real is not None: self.center_real_spinbox.setValue(center_real)
        if center_imag is not None: self.center_imag_spinbox.setValue(center_imag)
        initial_width = 3.0
        if self.fractal_controller and hasattr(self.fractal_controller, 'initial_width'):
            initial_width = getattr(self.fractal_controller, 'initial_width', 3.0)
        if width is not None and width > 0:
            zoom = initial_width / width
            self.zoom_spinbox.setValue(zoom)
            self.width_label.setText(f"{width:.10g}")
        else:
            self.zoom_spinbox.setValue(1.0)
            self.width_label.setText("-")
        self.iter_spinbox.blockSignals(False)
        self.center_real_spinbox.blockSignals(False)
        self.center_imag_spinbox.blockSignals(False)
        self.zoom_spinbox.blockSignals(False)

    @pyqtSlot(dict)
    def update_ui_from_controller_parameters(self, params: dict):
        if self.fractal_controller:
            self._set_ui_values(
                iterations=params.get('max_iterations', 100),
                center_real=params.get('center_real', -0.5),
                center_imag=params.get('center_imag', 0.0),
                width=params.get('width', 3.0)
            )

    def get_current_ui_parameters(self) -> dict:
        initial_width = 3.0
        if self.fractal_controller and hasattr(self.fractal_controller, 'initial_width'):
            initial_width = getattr(self.fractal_controller, 'initial_width', 3.0)
        zoom = self.zoom_spinbox.value()
        width = initial_width / zoom if zoom > 0 else initial_width
        return {
            "max_iterations": self.iter_spinbox.value(),
            "center_real": self.center_real_spinbox.value(),
            "center_imag": self.center_imag_spinbox.value(),
            "width": width,
        }

    @pyqtSlot(bool)
    def _on_rendering_state_changed(self, is_rendering: bool):
        def _update_ui():
            if hasattr(self, 'fractal_combo'):
                self.fractal_combo.setEnabled(not is_rendering)
        QTimer.singleShot(0, _update_ui)

    def eventFilter(self, obj, event):
        if isinstance(obj, (QSpinBox, QDoubleSpinBox)):
            if event.type() == QEvent.Type.FocusIn:
                self._focused_value_store[obj] = obj.value()
        return super().eventFilter(obj, event)

    def _on_coloring_preset_selected(self, preset_name: str, plugin_name: str, presets_data: dict, target_type: str):
        if preset_name == "カスタム" or not self.fractal_controller: return
        widgets = self.coloring_widgets[target_type]
        plugin_widgets_dict = widgets['plugin_widgets']
        algo_combo = widgets['algo_combo']
        selected_vals = presets_data.get(preset_name)
        if selected_vals:
            current_ui_algo_name = algo_combo.currentText()
            if current_ui_algo_name != plugin_name: return
            params_to_set_in_controller = {}
            for p_name, val in selected_vals.items():
                widget = plugin_widgets_dict.get(p_name)
                if widget:
                    widget.blockSignals(True)
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.setValue(val)
                        if widget in self._focused_value_store:
                            del self._focused_value_store[widget]
                    widget.blockSignals(False)
                    params_to_set_in_controller[p_name] = val
            if params_to_set_in_controller:
                for p_name, val in params_to_set_in_controller.items():
                    self.fractal_controller.set_coloring_plugin_parameter_and_recolor(p_name, val, target_type=target_type, allow_recolor=False)
                self.request_redraw(full_recompute=False, is_preview=False)

    @pyqtSlot(str, str)
    def update_active_coloring_target_and_plugin_from_controller(self, target_type: str, plugin_name: str):
        try:
            algo_combo = self.coloring_widgets[target_type]['algo_combo']
        except KeyError:
            return
        algo_combo.blockSignals(True)
        current_algo_text = algo_combo.currentText()
        if current_algo_text != plugin_name:
            items = [algo_combo.itemText(i) for i in range(algo_combo.count())]
            if plugin_name not in items:
                self._populate_coloring_algorithm_combo(target_type)
            algo_combo.setCurrentText(plugin_name)
        algo_combo.blockSignals(False)
        self._update_coloring_plugin_specific_ui(plugin_name, target_type)

    def _on_common_parameter_changed_for_preview(self, value):
        if not self.fractal_controller: return
        params = self.get_current_ui_parameters()
        self.width_label.setText(f"{params['width']:.10g}")
        self.fractal_controller.handle_programmatic_parameter_change(
            cr=params["center_real"], ci=params["center_imag"],
            w=params["width"], iters=params["max_iterations"]
        )
        self.request_redraw(full_recompute=True, is_preview=True)
        self._update_zoom_label(params["width"])

    def _on_fractal_plugin_parameter_changed_for_preview(self, value, param_name: str):
        if not self.fractal_controller: return
        self.fractal_controller.set_fractal_plugin_parameter(param_name, value)
        self.request_redraw(full_recompute=True, is_preview=True)

    def _on_coloring_plugin_parameter_changed_for_preview(self, value, param_name: str, target_type: str):
        if not self.fractal_controller: return
        try:
            plugin_widgets = self.coloring_widgets[target_type]['plugin_widgets']
            if '_coloring_preset_combo' in plugin_widgets:
                preset_combo = plugin_widgets['_coloring_preset_combo']
                if preset_combo.currentText() != "カスタム":
                    preset_combo.blockSignals(True)
                    preset_combo.setCurrentText("カスタム")
                    preset_combo.blockSignals(False)
        except KeyError:
            return
        self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, value, target_type=target_type, allow_recolor=False)
        self.request_redraw(full_recompute=False, is_preview=True)

    def get_active_coloring_target_type(self) -> str:
        idx = self.coloring_tabs.currentIndex() if hasattr(self, 'coloring_tabs') else 0
        return 'divergent' if idx == 0 else 'non_divergent'

    def get_current_color_pack_and_map(self, target_type: str = None) -> tuple[str|None, str|None]:
        if target_type is None:
            target_type = self.get_active_coloring_target_type()
        widgets = self.coloring_widgets.get(target_type, {})
        pack_combo = widgets.get('pack_combo')
        map_list = widgets.get('map_list')
        pack_name = pack_combo.currentText() if pack_combo and pack_combo.currentIndex() >= 0 else None
        map_item = map_list.currentItem() if map_list and map_list.currentRow() >= 0 else None
        map_name = map_item.text() if map_item else None
        if (not pack_name or pack_name == 'N/A') and self.fractal_controller:
            pack_name = self.fractal_controller.get_active_color_pack_name_from_engine(target_type)
        if not map_name and self.fractal_controller:
            map_name = self.fractal_controller.get_active_color_map_name_from_engine(target_type)
        return pack_name, map_name

    @pyqtSlot(str)
    def _on_active_fractal_plugin_changed(self, plugin_name: str):
        self._populate_fractal_combo()
        self._update_fractal_plugin_specific_ui(plugin_name)

    def _update_zoom_label(self, width=None):
        initial_width = 3.0
        if self.fractal_controller and hasattr(self.fractal_controller, 'initial_width'):
            initial_width = getattr(self.fractal_controller, 'initial_width', 3.0)
        w = width
        if w is None:
            try:
                w = float(self.width_label.text())
            except (ValueError, TypeError):
                w = initial_width
        if w > 0:
            zoom = initial_width / w
            self.zoom_spinbox.setValue(zoom)
            self.width_label.setText(f"{w:.10g}")
        else:
            self.zoom_spinbox.setValue(1.0)
            self.width_label.setText("-")

    def _on_zoom_spinbox_changed(self):
        params = self.get_current_ui_parameters()
        self.width_label.setText(f"{params['width']:.10g}")
        if self.fractal_controller:
            self.fractal_controller.handle_programmatic_parameter_change(
                cr=params["center_real"], ci=params["center_imag"],
                w=params["width"], iters=params["max_iterations"]
            )
        self.parameters_changed_in_ui_signal.emit(params)

if __name__ == '__main__':
    pass
