from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QSlider, QComboBox, QPushButton,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize # Added QSize
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QLinearGradient, QIcon # Added QtGui imports
from functools import partial

class ParameterPanel(QScrollArea):
    parameters_changed_in_ui_signal = pyqtSignal(float, float, float, int)

    def __init__(self, fractal_controller, parent=None):
        super().__init__(parent)
        self.fractal_controller = fractal_controller
        self.plugin_widgets = {}
        self.coloring_plugin_widgets = {}

        self._init_ui()

        if self.fractal_controller:
            self._populate_fractal_combo()
            self._populate_coloring_algorithm_combo()
            self._populate_color_pack_combo()

            active_pack = self.fractal_controller.get_active_color_pack_name_from_engine()
            if active_pack:
                 self._populate_color_map_list(active_pack)

            self.load_initial_parameters()

            self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
            self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(self._update_fractal_plugin_specific_ui)
            self.fractal_controller.active_coloring_plugin_ui_needs_update.connect(self._update_coloring_plugin_specific_ui)
            self.fractal_controller.active_color_map_changed_externally.connect(self._update_color_selection_from_controller)
        else:
            # Fallback if no controller
            self._set_ui_values(-0.5, 0.0, 3.0, 100)
            if hasattr(self, 'plugin_specific_group'): self.plugin_specific_group.setVisible(False)
            if hasattr(self, 'coloring_group'): self.coloring_group.setEnabled(False)


    def _init_ui(self):
        self.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        self.main_layout = QVBoxLayout(self.content_widget)
        self.content_widget.setLayout(self.main_layout)

        # Fractal Selection
        fractal_group = QGroupBox("フラクタル選択")
        fractal_layout = QVBoxLayout(); self.fractal_combo = QComboBox()
        fractal_layout.addWidget(self.fractal_combo); fractal_group.setLayout(fractal_layout)
        self.main_layout.addWidget(fractal_group)
        self.fractal_combo.currentTextChanged.connect(self._on_fractal_type_changed)

        # Common Parameters
        common_params_group = QGroupBox("共通描画設定")
        self.common_params_layout = QFormLayout()
        self.iter_spinbox = QSpinBox(); self.iter_spinbox.setRange(10,100000)
        self.iter_slider = QSlider(Qt.Orientation.Horizontal); self.iter_slider.setRange(10,10000)
        self.common_params_layout.addRow(QLabel("最大反復回数:"), self.iter_spinbox)
        self.common_params_layout.addRow(self.iter_slider)
        self.center_real_spinbox = QDoubleSpinBox(); self.center_real_spinbox.setRange(-2.5,2.5); self.center_real_spinbox.setDecimals(15); self.center_real_spinbox.setSingleStep(0.01)
        self.common_params_layout.addRow(QLabel("中心 (実部):"), self.center_real_spinbox)
        self.center_imag_spinbox = QDoubleSpinBox(); self.center_imag_spinbox.setRange(-2.0,2.0); self.center_imag_spinbox.setDecimals(15); self.center_imag_spinbox.setSingleStep(0.01)
        self.common_params_layout.addRow(QLabel("中心 (虚部):"), self.center_imag_spinbox)
        self.width_spinbox = QDoubleSpinBox(); self.width_spinbox.setRange(1e-15,10.0); self.width_spinbox.setDecimals(15); self.width_spinbox.setSingleStep(0.1)
        self.common_params_layout.addRow(QLabel("幅:"), self.width_spinbox)
        common_params_group.setLayout(self.common_params_layout)
        self.main_layout.addWidget(common_params_group)

        # Fractal Plugin-Specific Parameters
        self.plugin_specific_group = QGroupBox("フラクタル固有設定")
        self.plugin_specific_layout = QFormLayout()
        self.plugin_specific_group.setLayout(self.plugin_specific_layout)
        self.main_layout.addWidget(self.plugin_specific_group)
        self.plugin_specific_group.setVisible(False)

        # Coloring Settings Group
        self.coloring_group = QGroupBox("カラーリング設定")
        self.true_coloring_layout = QVBoxLayout() # Main layout for this group

        # Coloring Algorithm selection
        form_algo_select = QFormLayout()
        self.coloring_algorithm_combo = QComboBox()
        form_algo_select.addRow(QLabel("アルゴリズム:"), self.coloring_algorithm_combo)
        self.true_coloring_layout.addLayout(form_algo_select)
        self.coloring_algorithm_combo.currentTextChanged.connect(self._on_coloring_algorithm_changed)

        # Coloring Algorithm Specific UI
        self.coloring_plugin_specific_group = QGroupBox("アルゴリズム固有設定")
        self.coloring_plugin_specific_layout = QFormLayout()
        self.coloring_plugin_specific_group.setLayout(self.coloring_plugin_specific_layout)
        self.true_coloring_layout.addWidget(self.coloring_plugin_specific_group)
        self.coloring_plugin_specific_group.setVisible(False)

        # Color Pack selection
        form_pack_select = QFormLayout()
        self.color_pack_combo = QComboBox()
        form_pack_select.addRow(QLabel("カラーパック:"), self.color_pack_combo)
        self.true_coloring_layout.addLayout(form_pack_select)
        self.color_pack_combo.currentTextChanged.connect(self._on_color_pack_changed)

        # Color Map selection
        form_map_select = QFormLayout()
        self.color_map_listwidget = QListWidget()
        self.color_map_listwidget.setIconSize(QSize(96, 18)) # Increased width for better preview
        self.color_map_listwidget.setSpacing(1)
        self.color_map_listwidget.setFixedHeight(120)
        form_map_select.addRow(QLabel("カラーマップ:"), self.color_map_listwidget)
        self.true_coloring_layout.addLayout(form_map_select)
        self.color_map_listwidget.currentItemChanged.connect(self._on_color_map_changed)

        self.coloring_group.setLayout(self.true_coloring_layout)
        self.main_layout.addWidget(self.coloring_group)

        # Render Button
        self.render_button = QPushButton("描画実行")
        self.main_layout.addWidget(self.render_button)
        self.main_layout.addStretch(1)

        # Connect common parameter signals
        self.iter_spinbox.valueChanged.connect(self._on_iter_spinbox_changed)
        self.iter_slider.valueChanged.connect(self._on_iter_slider_changed)
        self.center_real_spinbox.valueChanged.connect(self._on_value_changed_by_ui)
        self.center_imag_spinbox.valueChanged.connect(self._on_value_changed_by_ui)
        self.width_spinbox.valueChanged.connect(self._on_value_changed_by_ui)

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
            gradient = QLinearGradient(0, 0, thumb_width, 0) # Horizontal gradient
            num_color_stops = len(colors)
            for i, color_tuple in enumerate(colors):
                position = i / (num_color_stops - 1) if num_color_stops > 1 else 0.0
                qt_color = QColor(color_tuple[0], color_tuple[1], color_tuple[2])
                gradient.setColorAt(position, qt_color)
            painter.fillRect(0, 0, thumb_width, thumb_height, gradient)

        painter.end()
        return QPixmap.fromImage(img)

    # --- Fractal Plugin UI Methods (略 - 変更なし) ---
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

    @pyqtSlot(str)
    def _on_fractal_type_changed(self, plugin_name: str):
        if not self.fractal_controller or not plugin_name or plugin_name == "プラグインなし": return
        current_engine_plugin = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        if plugin_name == current_engine_plugin: return
        self.fractal_controller.set_active_fractal_plugin_and_redraw(plugin_name)

    def _clear_fractal_plugin_specific_ui(self):
        self.plugin_widgets.clear()
        while self.plugin_specific_layout.count():
            item = self.plugin_specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str)
    def _update_fractal_plugin_specific_ui(self, plugin_name: str):
        self._clear_fractal_plugin_specific_ui()
        if not self.fractal_controller or not plugin_name: self.plugin_specific_group.setVisible(False); return
        param_defs = self.fractal_controller.get_fractal_plugin_parameter_definitions_from_engine(plugin_name)
        if not param_defs: self.plugin_specific_group.setVisible(False); return
        self.plugin_specific_group.setVisible(True)
        self.plugin_specific_group.setTitle(f"{plugin_name} 固有設定")
        current_vals = self.fractal_controller.get_current_fractal_plugin_parameters_from_engine()
        for p_def in param_defs:
            lbl = p_def.get('label', p_def['name']); name = p_def['name']; type = p_def.get('type', 'float')
            val = current_vals.get(name, p_def.get('default')); widget = None
            if type == 'float':
                widget = QDoubleSpinBox(); widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1]); widget.setValue(val if val is not None else 0.0); widget.setSingleStep(p_def.get('step',0.01)); widget.setDecimals(p_def.get('decimals',6))
            elif type == 'int':
                widget = QSpinBox(); widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1]); widget.setValue(val if val is not None else 0); widget.setSingleStep(p_def.get('step',1))
            if widget:
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
                self.plugin_specific_layout.addRow(QLabel(lbl + ":"), widget)
                widget.valueChanged.connect(partial(self._on_fractal_plugin_parameter_changed, param_name=name))
                self.plugin_widgets[name] = widget

    def _on_fractal_plugin_parameter_changed(self, value, param_name: str):
        if not self.fractal_controller: return
        sender = self.sender()
        if isinstance(sender, (QDoubleSpinBox, QSpinBox)):
            self.fractal_controller.set_fractal_plugin_parameter_and_update(param_name, sender.value())
            if '_preset_combo' in self.plugin_widgets:
                self.plugin_widgets['_preset_combo'].blockSignals(True); self.plugin_widgets['_preset_combo'].setCurrentText("カスタム"); self.plugin_widgets['_preset_combo'].blockSignals(False)

    # --- Coloring UI Methods ---
    def _populate_coloring_algorithm_combo(self):
        if not self.fractal_controller: return
        algo_names = self.fractal_controller.get_available_coloring_plugin_names_from_engine()
        active_algo = self.fractal_controller.get_active_coloring_plugin_name_from_engine()
        self.coloring_algorithm_combo.blockSignals(True); self.coloring_algorithm_combo.clear()
        if algo_names:
            self.coloring_algorithm_combo.addItems(algo_names)
            if active_algo and active_algo in algo_names: self.coloring_algorithm_combo.setCurrentText(active_algo)
            elif algo_names: self.coloring_algorithm_combo.setCurrentText(algo_names[0])
        else: self.coloring_algorithm_combo.addItem("N/A"); self.coloring_algorithm_combo.setEnabled(False)
        self.coloring_algorithm_combo.blockSignals(False)

    @pyqtSlot(str)
    def _on_coloring_algorithm_changed(self, algo_name: str):
        if not self.fractal_controller or not algo_name or algo_name == "N/A": return
        if algo_name == self.fractal_controller.get_active_coloring_plugin_name_from_engine(): return
        self.fractal_controller.set_active_coloring_plugin_and_recolor(algo_name)

    def _clear_coloring_plugin_specific_ui(self):
        self.coloring_plugin_widgets.clear()
        while self.coloring_plugin_specific_layout.count():
            item = self.coloring_plugin_specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str)
    def _update_coloring_plugin_specific_ui(self, algo_name: str):
        self._clear_coloring_plugin_specific_ui()
        if not self.fractal_controller or not algo_name: self.coloring_plugin_specific_group.setVisible(False); return
        param_defs = self.fractal_controller.get_coloring_plugin_parameter_definitions_from_engine(algo_name)
        if not param_defs: self.coloring_plugin_specific_group.setVisible(False); return

        self.coloring_plugin_specific_group.setVisible(True)
        self.coloring_plugin_specific_group.setTitle(f"{algo_name} 固有設定")
        current_vals = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine()

        # Add preset combobox for coloring plugins if they have presets
        presets = self.fractal_controller.get_plugin_presets(algo_name) # Assuming fractal_controller has this for coloring plugins too
        if presets:
            preset_combo = QComboBox()
            preset_combo.addItem("カスタム")
            for preset_name in presets.keys(): preset_combo.addItem(preset_name)
            preset_combo.currentTextChanged.connect(
                partial(self._on_coloring_preset_selected, plugin_name=algo_name, presets_data=presets.copy())
            )
            self.coloring_plugin_specific_layout.addRow(QLabel("プリセット:"), preset_combo)
            self.coloring_plugin_widgets['_coloring_preset_combo'] = preset_combo

        for p_def in param_defs:
            lbl=p_def.get('label',p_def['name']); name=p_def['name']; type=p_def.get('type','float')
            val=current_vals.get(name, p_def.get('default')); widget=None
            if type == 'float':
                widget=QDoubleSpinBox(); widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1]); widget.setValue(val if val is not None else 0.0); widget.setSingleStep(p_def.get('step',0.01)); widget.setDecimals(p_def.get('decimals',3))
            elif type == 'int':
                widget=QSpinBox(); widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1]); widget.setValue(val if val is not None else 0); widget.setSingleStep(p_def.get('step',1))
            if widget:
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
                self.coloring_plugin_specific_layout.addRow(QLabel(lbl + ":"), widget)
                widget.valueChanged.connect(partial(self._on_coloring_plugin_parameter_changed, param_name=name))
                self.coloring_plugin_widgets[name] = widget

    def _on_coloring_plugin_parameter_changed(self, value, param_name: str):
        if not self.fractal_controller: return
        sender = self.sender()
        if isinstance(sender, (QDoubleSpinBox, QSpinBox)):
            self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, sender.value())
            if '_coloring_preset_combo' in self.coloring_plugin_widgets:
                self.coloring_plugin_widgets['_coloring_preset_combo'].blockSignals(True)
                self.coloring_plugin_widgets['_coloring_preset_combo'].setCurrentText("カスタム")
                self.coloring_plugin_widgets['_coloring_preset_combo'].blockSignals(False)

    def _on_coloring_preset_selected(self, preset_name: str, plugin_name: str, presets_data: dict):
        if preset_name == "カスタム" or not self.fractal_controller: return
        selected_vals = presets_data.get(preset_name)
        if selected_vals:
            for p_name, val in selected_vals.items():
                if p_name in self.coloring_plugin_widgets:
                    widget = self.coloring_plugin_widgets[p_name]
                    widget.blockSignals(True); widget.setValue(val); widget.blockSignals(False)
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(p_name, val) # Notify even if no UI widget

    def _populate_color_pack_combo(self):
        if not self.fractal_controller: return
        pack_names = self.fractal_controller.get_available_color_pack_names_from_engine()
        active_pack = self.fractal_controller.get_active_color_pack_name_from_engine()
        self.color_pack_combo.blockSignals(True); self.color_pack_combo.clear()
        if pack_names:
            self.color_pack_combo.addItems(pack_names)
            if active_pack and active_pack in pack_names: self.color_pack_combo.setCurrentText(active_pack)
            elif pack_names: self.color_pack_combo.setCurrentText(pack_names[0])
        else: self.color_pack_combo.addItem("N/A"); self.color_pack_combo.setEnabled(False)
        self.color_pack_combo.blockSignals(False)
        if self.color_pack_combo.isEnabled() and self.color_pack_combo.currentText() != "N/A":
             self._populate_color_map_list(self.color_pack_combo.currentText())

    @pyqtSlot(str)
    def _on_color_pack_changed(self, pack_name: str):
        if not self.fractal_controller or not pack_name or pack_name == "N/A": return
        self._populate_color_map_list(pack_name)
        if self.color_map_listwidget.count() > 0:
            first_map_item = self.color_map_listwidget.item(0)
            if first_map_item:
                self.color_map_listwidget.setCurrentItem(first_map_item)
                # If selection didn't change but we want to force update based on new pack's first map:
                if self.fractal_controller.get_active_color_map_name_from_engine() != first_map_item.text() or \
                   self.fractal_controller.get_active_color_pack_name_from_engine() != pack_name:
                     self.fractal_controller.set_active_color_map_and_recolor(pack_name, first_map_item.text())

    def _populate_color_map_list(self, pack_name: str | None):
        self.color_map_listwidget.blockSignals(True)
        self.color_map_listwidget.clear()
        if not self.fractal_controller or not pack_name:
            self.color_map_listwidget.setEnabled(False); self.color_map_listwidget.blockSignals(False); return

        map_names = self.fractal_controller.get_color_map_names_in_pack_from_engine(pack_name)
        active_map_name = self.fractal_controller.get_active_color_map_name_from_engine()

        if map_names:
            self.color_map_listwidget.setEnabled(True)
            for name_str in map_names:
                map_data = self.fractal_controller.get_color_map_data_from_engine(pack_name, name_str)
                list_item = QListWidgetItem(name_str)
                if map_data:
                    thumbnail = self._create_colormap_thumbnail(map_data)
                    list_item.setIcon(QIcon(thumbnail))
                self.color_map_listwidget.addItem(list_item)
                if name_str == active_map_name:
                    self.color_map_listwidget.setCurrentItem(list_item)
        else:
            self.color_map_listwidget.setEnabled(False)
        self.color_map_listwidget.blockSignals(False)

    @pyqtSlot(QListWidgetItem, QListWidgetItem)
    def _on_color_map_changed(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if not self.fractal_controller or not current_item: return
        map_name = current_item.text()
        pack_name = self.color_pack_combo.currentText()
        if not pack_name or pack_name == "N/A": return
        active_pack_ctrl = self.fractal_controller.get_active_color_pack_name_from_engine()
        active_map_ctrl = self.fractal_controller.get_active_color_map_name_from_engine()
        if pack_name == active_pack_ctrl and map_name == active_map_ctrl: return
        self.fractal_controller.set_active_color_map_and_recolor(pack_name, map_name)

    @pyqtSlot(str, str)
    def _update_color_selection_from_controller(self, pack_name: str, map_name: str):
        self.color_pack_combo.blockSignals(True)
        self.color_map_listwidget.blockSignals(True)
        if pack_name != self.color_pack_combo.currentText():
            self.color_pack_combo.setCurrentText(pack_name)
            self._populate_color_map_list(pack_name)
        found = False
        for i in range(self.color_map_listwidget.count()):
            item = self.color_map_listwidget.item(i)
            if item.text() == map_name: self.color_map_listwidget.setCurrentItem(item); found = True; break
        self.color_pack_combo.blockSignals(False); self.color_map_listwidget.blockSignals(False)

    # --- Common UI Parameter Handling (略 - 変更なし) ---
    def _on_iter_spinbox_changed(self, value):
        self.iter_slider.setValue(value); self._on_value_changed_by_ui()
    def _on_iter_slider_changed(self, value):
        if self.iter_spinbox.value() != value: self.iter_spinbox.setValue(value)
        else: self._on_value_changed_by_ui()
    def _on_value_changed_by_ui(self):
        cr=self.center_real_spinbox.value(); ci=self.center_imag_spinbox.value(); w=self.width_spinbox.value(); iters=self.iter_spinbox.value()
        self.parameters_changed_in_ui_signal.emit(cr, ci, w, iters)
    def load_initial_parameters(self):
        if self.fractal_controller:
            params = self.fractal_controller.get_current_common_parameters()
            if params: self._set_ui_values(params.get('center_real',-0.5), params.get('center_imag',0.0), params.get('width',3.0), params.get('max_iterations',100))
            active_fp_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
            if active_fp_name: self._update_fractal_plugin_specific_ui(active_fp_name) # Renamed method
            active_cp_name = self.fractal_controller.get_active_coloring_plugin_name_from_engine()
            if active_cp_name: self._update_coloring_plugin_specific_ui(active_cp_name)
    @pyqtSlot()
    def update_ui_from_controller_parameters(self):
        if self.fractal_controller:
            params = self.fractal_controller.get_current_common_parameters()
            if params: self._set_ui_values(params['center_real'], params['center_imag'], params['width'], params['max_iterations'])
    def _set_ui_values(self, cr, ci, w, iters):
        self.iter_spinbox.blockSignals(True); self.iter_slider.blockSignals(True); self.center_real_spinbox.blockSignals(True); self.center_imag_spinbox.blockSignals(True); self.width_spinbox.blockSignals(True)
        self.iter_spinbox.setValue(int(iters)); self.iter_slider.setValue(int(iters)); self.center_real_spinbox.setValue(cr); self.center_imag_spinbox.setValue(ci); self.width_spinbox.setValue(w)
        self.iter_spinbox.blockSignals(False); self.iter_slider.blockSignals(False); self.center_real_spinbox.blockSignals(False); self.center_imag_spinbox.blockSignals(False); self.width_spinbox.blockSignals(False)
    def get_current_ui_parameters(self) -> dict:
        return {"center_real":self.center_real_spinbox.value(), "center_imag":self.center_imag_spinbox.value(), "width":self.width_spinbox.value(), "max_iterations":self.iter_spinbox.value()}

if __name__ == '__main__':
    # ... (Standalone test code remains complex and is best done via main application) ...
    print("ParameterPanel standalone test requires a comprehensive mock controller and setup.")
    print("Please test through the main application or a dedicated test suite.")
