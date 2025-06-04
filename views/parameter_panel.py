from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QSlider, QComboBox, QPushButton,
    QListWidget, QListWidgetItem, QAbstractSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QTimer, QEvent # Added QEvent
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QLinearGradient, QIcon
from functools import partial
from logger.custom_logger import CustomLogger # Ensure this is present

logger = CustomLogger() # Add this line

class ParameterPanel(QScrollArea):
    """
    フラクタル計算とカラーリングに関連する各種パラメータを設定するためのUIパネル。

    ユーザーがフラクタルタイプ、共通パラメータ（中心座標、幅、反復回数）、
    フラクタル固有パラメータ、カラーリングアルゴリズム、カラーパック、カラーマップを
    選択・調整できるようにします。
    変更は `FractalController` と連携して処理されます。
    """
    parameters_changed_in_ui_signal = pyqtSignal(int)
    """共通パラメータ (中心実部, 中心虚部, 幅, 最大反復回数) がUIで変更されたときに発行されるシグナル。"""

    def __init__(self, fractal_controller, parent=None):
        """
        ParameterPanel を初期化します。

        Args:
            fractal_controller (FractalController): パラメータの管理と更新を行うコントローラー。
            parent (QWidget, optional): 親ウィジェット。 Defaults to None.
        """
        super().__init__(parent)
        self.fractal_controller = fractal_controller
        self.plugin_widgets = {}
        self.coloring_plugin_widgets = {}
        self._focused_value_store = {} # フォーカス時の値を保存する辞書
        self._slider_original_value = {} # スライダー操作開始時の値を保存する辞書

        # UIの初期化とコントローラーからのデータ読み込み
        self._init_ui()

        if self.fractal_controller:
            self._populate_fractal_combo()
            self._populate_coloring_algorithm_combo()
            self._populate_color_pack_combo()

            active_pack = self.fractal_controller.get_active_color_pack_name_from_engine()
            if active_pack:
                 self._populate_color_map_list(active_pack)

            # コントローラーから初期パラメータをロードしてUIに反映
            self.load_initial_parameters()

            self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
            self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(self._update_fractal_plugin_specific_ui)
            self.fractal_controller.active_coloring_plugin_ui_needs_update.connect(self._update_coloring_plugin_specific_ui)
            self.fractal_controller.active_color_map_changed_externally.connect(self._update_color_selection_from_controller)
            # self.fractal_controller.rendering_state_changed.connect(self._on_rendering_state_changed) # This line is moved to MainWindow
        else:
            # コントローラーが利用できない場合のフォールバックUI設定
            self._set_ui_values(100)
            if hasattr(self, 'plugin_specific_group'): self.plugin_specific_group.setVisible(False)
            if hasattr(self, 'coloring_group'): self.coloring_group.setEnabled(False)


    def _init_ui(self):
        """
        パラメータパネルのユーザーインターフェース要素を初期化し、配置します。
        """
        self.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        self.main_layout = QVBoxLayout(self.content_widget)
        self.content_widget.setLayout(self.main_layout)

        # フラクタル選択
        fractal_group = QGroupBox("フラクタル選択")
        fractal_layout = QVBoxLayout(); self.fractal_combo = QComboBox()
        fractal_layout.addWidget(self.fractal_combo); fractal_group.setLayout(fractal_layout)
        self.main_layout.addWidget(fractal_group)
        self.fractal_combo.currentTextChanged.connect(self._on_fractal_type_changed)
        # 共通パラメータ
        common_params_group = QGroupBox("共通描画設定")
        self.common_params_layout = QFormLayout()
        self.iter_spinbox = QSpinBox(); self.iter_spinbox.setRange(10,100000)
        self.iter_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.iter_spinbox.installEventFilter(self) # イベントフィルターをインストール
        self.iter_slider = QSlider(Qt.Orientation.Horizontal); self.iter_slider.setRange(10,10000)
        self.common_params_layout.addRow(QLabel("最大反復回数:"), self.iter_spinbox)
        self.common_params_layout.addRow(self.iter_slider)
        common_params_group.setLayout(self.common_params_layout)
        self.main_layout.addWidget(common_params_group)

        # フラクタルプラグイン固有設定
        self.plugin_specific_group = QGroupBox("フラクタル固有設定")
        self.plugin_specific_layout = QFormLayout()
        self.plugin_specific_group.setLayout(self.plugin_specific_layout)
        self.main_layout.addWidget(self.plugin_specific_group)
        self.plugin_specific_group.setVisible(False)

        # カラーリング設定グループ
        self.coloring_group = QGroupBox("カラーリング設定")
        self.true_coloring_layout = QVBoxLayout() # このグループのメインレイアウト

        # カラーリングアルゴリズム選択
        form_algo_select = QFormLayout()
        self.coloring_algorithm_combo = QComboBox()
        form_algo_select.addRow(QLabel("アルゴリズム:"), self.coloring_algorithm_combo)
        self.true_coloring_layout.addLayout(form_algo_select)
        self.coloring_algorithm_combo.currentTextChanged.connect(self._on_coloring_algorithm_changed)

        # カラーリングアルゴリズム固有UI
        self.coloring_plugin_specific_group = QGroupBox("アルゴリズム固有設定")
        self.coloring_plugin_specific_layout = QFormLayout()
        self.coloring_plugin_specific_group.setLayout(self.coloring_plugin_specific_layout)
        self.true_coloring_layout.addWidget(self.coloring_plugin_specific_group)
        self.coloring_plugin_specific_group.setVisible(False)

        # カラーパック選択
        form_pack_select = QFormLayout()
        self.color_pack_combo = QComboBox()
        form_pack_select.addRow(QLabel("カラーパック:"), self.color_pack_combo)
        self.true_coloring_layout.addLayout(form_pack_select)
        self.color_pack_combo.currentTextChanged.connect(self._on_color_pack_changed)

        # カラーマップ選択
        form_map_select = QFormLayout()
        self.color_map_listwidget = QListWidget()
        self.color_map_listwidget.setIconSize(QSize(96, 18)) # より良いプレビューのために幅を増やしました
        self.color_map_listwidget.setSpacing(1)
        self.color_map_listwidget.setFixedHeight(120)
        form_map_select.addRow(QLabel("カラーマップ:"), self.color_map_listwidget)
        self.true_coloring_layout.addLayout(form_map_select)
        self.color_map_listwidget.currentItemChanged.connect(self._on_color_map_changed)

        self.coloring_group.setLayout(self.true_coloring_layout)
        self.main_layout.addWidget(self.coloring_group)

        # 描画ボタン
        self.render_button = QPushButton("描画実行")
        self.main_layout.addWidget(self.render_button)
        self.main_layout.addStretch(1)
        # 共通パラメータシグナルの接続
        self.iter_spinbox.valueChanged.connect(self._on_iter_spinbox_changed)
        self.iter_slider.valueChanged.connect(self._on_iter_slider_changed)
        # 再描画をトリガーするシグナル接続
        self.iter_spinbox.editingFinished.connect(self._on_value_changed_by_ui)
        self.iter_slider.sliderReleased.connect(self._on_value_changed_by_ui)
        self.iter_slider.sliderPressed.connect(self._on_iter_slider_pressed) # sliderPressedシグナルを接続

    def _create_colormap_thumbnail(self, colors: list[tuple[int,int,int]], thumb_width: int = 96, thumb_height: int = 18) -> QPixmap:
        """
        指定された色のリストからカラーマップのサムネイル画像を生成します。

        Args:
            colors (list[tuple[int,int,int]]): RGB色のタプルのリスト。
            thumb_width (int, optional): サムネイルの幅。 Defaults to 96.
            thumb_height (int, optional): サムネイルの高さ。 Defaults to 18.

        Returns:
            QPixmap: 生成されたサムネイル画像。色が指定されていない場合はグレーの画像。
        """
        if not colors:
            img = QImage(thumb_width, thumb_height, QImage.Format.Format_RGB888)
            img.fill(Qt.GlobalColor.gray)
            return QPixmap.fromImage(img)

        img = QImage(thumb_width, thumb_height, QImage.Format.Format_RGB888)
        painter = QPainter(img)

        if len(colors) == 1:
            painter.fillRect(0, 0, thumb_width, thumb_height, QColor(colors[0][0], colors[0][1], colors[0][2]))
        else:
            gradient = QLinearGradient(0, 0, thumb_width, 0) # 水平グラデーション
            num_color_stops = len(colors)
            for i, color_tuple in enumerate(colors):
                position = i / (num_color_stops - 1) if num_color_stops > 1 else 0.0
                qt_color = QColor(color_tuple[0], color_tuple[1], color_tuple[2])
                gradient.setColorAt(position, qt_color)
            painter.fillRect(0, 0, thumb_width, thumb_height, gradient)

        painter.end()
        return QPixmap.fromImage(img)

    def _populate_fractal_combo(self):
        """
        フラクタル選択用コンボボックスに、利用可能なフラクタルプラグイン名を設定します。
        """
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
        """
        フラクタル選択コンボボックスの選択が変更されたときに呼び出されるスロット。
        コントローラーに選択されたフラクタルプラグインをアクティブにするよう通知します。

        Args:
            plugin_name (str): 選択されたフラクタルプラグインの名前。
        """
        logger.log(f"ParameterPanel._on_fractal_type_changed: Called with plugin_name = {plugin_name}", level="DEBUG")

        if self.fractal_controller and hasattr(self.fractal_controller, 'is_rendering') and self.fractal_controller.is_rendering:
            logger.log("ParameterPanel._on_fractal_type_changed: Fractal type change blocked, rendering in progress.", level="DEBUG")
            return

        # Detailed logs about combo box state
        if hasattr(self, 'fractal_combo'):
            logger.log(f"ParameterPanel._on_fractal_type_changed: fractal_combo.isEnabled() = {self.fractal_combo.isEnabled()}", level="DEBUG")
            logger.log(f"ParameterPanel._on_fractal_type_changed: fractal_combo.isVisible() = {self.fractal_combo.isVisible()}", level="DEBUG")
            logger.log(f"ParameterPanel._on_fractal_type_changed: fractal_combo.hasFocus() = {self.fractal_combo.hasFocus()}", level="DEBUG")
            logger.log(f"ParameterPanel._on_fractal_type_changed: fractal_combo.currentText() = {self.fractal_combo.currentText()}", level="DEBUG")
            logger.log(f"ParameterPanel._on_fractal_type_changed: fractal_combo.count() = {self.fractal_combo.count()}", level="DEBUG")
        else:
            logger.log("ParameterPanel._on_fractal_type_changed: self.fractal_combo does not exist (for detailed logging).", level="WARNING")

        if not self.fractal_controller or not plugin_name or plugin_name == "プラグインなし":
            logger.log(f"ParameterPanel._on_fractal_type_changed: No controller, no plugin_name ('{plugin_name}'), or 'No plugin' selected. Returning.", level="DEBUG")
            return
        current_engine_plugin = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
        if plugin_name == current_engine_plugin:
            logger.log(f"ParameterPanel._on_fractal_type_changed: Selected plugin '{plugin_name}' is already active. Returning.", level="DEBUG")
            return

        logger.log(f"ParameterPanel._on_fractal_type_changed: Calling controller to set active fractal plugin: {plugin_name}", level="DEBUG")
        self.fractal_controller.set_active_fractal_plugin_and_redraw(plugin_name)
        # フラクタルタイプ変更後、意図しないフォーカス移動を防ぐためにコンボボックスにフォーカスを戻す
        self.setFocus()

    def _clear_fractal_plugin_specific_ui(self):
        """
        フラクタルプラグイン固有のパラメータUI要素をクリアします。
        """
        self.plugin_widgets.clear()
        while self.plugin_specific_layout.count():
            item = self.plugin_specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str)
    def _update_fractal_plugin_specific_ui(self, plugin_name: str):
        """
        指定されたフラクタルプラグインの固有パラメータUIを構築・更新します。
        コントローラーからパラメータ定義と現在の値を取得してUIに反映します。

        Args:
            plugin_name (str): UIを更新する対象のフラクタルプラグインの名前。
        """
        self._clear_fractal_plugin_specific_ui()
        if not self.fractal_controller or not plugin_name: self.plugin_specific_group.setVisible(False); return
        param_defs = self.fractal_controller.get_fractal_plugin_parameter_definitions_from_engine(plugin_name)
        if not param_defs: self.plugin_specific_group.setVisible(False); return
        self.plugin_specific_group.setVisible(True)
        self.plugin_specific_group.setTitle(f"{plugin_name} 固有設定")
        current_vals = self.fractal_controller.get_current_fractal_plugin_parameters_from_engine()
        for p_def in param_defs:
            lbl = p_def.get('label', p_def['name']); name = p_def['name']; type = p_def.get('type', 'float')
            widget = None # widget を初期化
            if type == 'float':
                widget = QDoubleSpinBox()
                widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1])

                # プラグインから step と decimals を取得、なければデフォルト値
                step_val = p_def.get('step', 1e-7) # より細かいデフォルトステップ
                decimals_val = p_def.get('decimals', 15) # より多くのデフォルト桁数

                widget.setDecimals(decimals_val)   # (1) Decimals を最初に設定
                widget.setSingleStep(step_val)     # (2) SingleStep を次に設定

                current_plugin_val = current_vals.get(name, p_def.get('default'))
                widget.setValue(current_plugin_val if current_plugin_val is not None else 0.0) # (3) 最後に値を設定

                if p_def.get('hide_spin_buttons', False):
                    widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

            elif type == 'int':
                widget = QSpinBox(); widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1]); widget.setValue(current_vals.get(name, p_def.get('default')) if current_vals.get(name, p_def.get('default')) is not None else 0); widget.setSingleStep(p_def.get('step',1))
            if widget:
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
                self.plugin_specific_layout.addRow(QLabel(lbl + ":"), widget)
                self.plugin_widgets[name] = widget
                # 値変更シグナルを接続 (debounceのためvalueChangedではなく、より汎用的なeditingFinishedを使用するケースも検討)
                if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                    # 既存の valueChanged シグナル接続
                    widget.valueChanged.connect(partial(self._on_fractal_plugin_parameter_changed, param_name=name))
                    # 新規: editingFinished シグナルを接続 (Enterキー押下またはフォーカスアウト)
                    widget.editingFinished.connect(partial(self._on_plugin_parameter_editing_finished, param_name=name))
                    widget.installEventFilter(self) # イベントフィルターをインストール
                # 他のウィジェットタイプの場合のシグナル接続はここに記述

    def _on_fractal_plugin_parameter_changed(self, value, param_name: str):
        """
        フラクタルプラグイン固有パラメータがUIで変更されたときに呼び出されるスロット。
        コントローラーにパラメータの更新を通知します。

        Args:
            value: 変更後の値。
            param_name (str): 変更されたパラメータの名前。
        """
        if not self.fractal_controller: return
        self.fractal_controller.set_fractal_plugin_parameter(param_name, value)
        # ここでは再描画をトリガーしない。editingFinishedで対応。

    @pyqtSlot() # param_name を受け取るために slot デコレーターを調整する必要があるかもしれません。partialで対応済み。
    def _on_plugin_parameter_editing_finished(self, param_name: str):
        """
        フラクタルプラグイン固有パラメータの入力フィールドで編集が完了した
        (Enterキー押下またはフォーカスアウト) ときに呼び出されるスロット。
        パラメータを更新し、再描画をトリガーします。
        """
        if not self.fractal_controller: return

        widget = self.plugin_widgets.get(param_name)
        if widget:
            value = None
            original_value = self._focused_value_store.pop(widget, None) # 保存された値を取得し削除
            current_value = None

            if isinstance(widget, QDoubleSpinBox):
                current_value = widget.value()
            elif isinstance(widget, QSpinBox):
                current_value = widget.value()
            # 他のウィジェットタイプもここに追加可能

            if current_value is not None:
                # パラメータ更新は valueChanged で既に行われていると仮定
                pass

            # 値が変更された場合のみ再描画
            if original_value is not None and current_value != original_value:
                logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: Value changed for {param_name} from {original_value} to {current_value}. Triggering render.", level="DEBUG")
                self.fractal_controller.trigger_render()
            elif original_value is None:
                logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: No original value found for {param_name}. Triggering render as a fallback.", level="DEBUG")
                # フォールバックとして、元の値がない場合は再描画（初回フォーカス時など）
                self.fractal_controller.trigger_render()
            else:
                logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: Value not changed for {param_name}. Current: {current_value}. Original: {original_value}. Skipping render.", level="DEBUG")
        else:
            # ウィジェットが見つからない場合、従来通り再描画 (安全策)
            logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: Widget for {param_name} not found. Triggering render as a fallback.", level="WARNING")
            self.fractal_controller.trigger_render()

    def _populate_coloring_algorithm_combo(self):
        """
        カラーリングアルゴリズム選択用コンボボックスに、利用可能なアルゴリズム名を設定します。
        """
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
        """
        カラーリングアルゴリズム選択コンボボックスの選択が変更されたときに呼び出されるスロット。
        コントローラーに選択されたアルゴリズムをアクティブにするよう通知します。

        Args:
            algo_name (str): 選択されたカラーリングアルゴリズムの名前。
        """
        if not self.fractal_controller or not algo_name or algo_name == "N/A": return
        if algo_name == self.fractal_controller.get_active_coloring_plugin_name_from_engine(): return
        self.fractal_controller.set_active_coloring_plugin_and_recolor(algo_name)

    def _clear_coloring_plugin_specific_ui(self):
        self.coloring_plugin_widgets.clear()
        while self.coloring_plugin_specific_layout.count():
            """
            カラーリングプラグイン固有のパラメータUI要素をクリアします。
            """
            item = self.coloring_plugin_specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str)
    def _update_coloring_plugin_specific_ui(self, algo_name: str):
        self._clear_coloring_plugin_specific_ui()
        """
        指定されたカラーリングアルゴリズムの固有パラメータUIを構築・更新します。
        コントローラーからパラメータ定義、プリセット、現在の値を取得してUIに反映します。

        Args:
            algo_name (str): UIを更新する対象のカラーリングアルゴリズムの名前。
        """
        if not self.fractal_controller or not algo_name: self.coloring_plugin_specific_group.setVisible(False); return
        param_defs = self.fractal_controller.get_coloring_plugin_parameter_definitions_from_engine(algo_name)
        if not param_defs: self.coloring_plugin_specific_group.setVisible(False); return

        self.coloring_plugin_specific_group.setVisible(True)
        self.coloring_plugin_specific_group.setTitle(f"{algo_name} 固有設定")
        current_vals = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine()

        # カラーリングプラグインにプリセットがある場合、プリセットコンボボックスを追加
        presets = self.fractal_controller.get_plugin_presets(algo_name) # fractal_controller もカラーリングプラグイン用にこれを持っていると仮定
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
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)): # QSpinBox, QDoubleSpinBox のみ editingFinished を接続
                    widget.editingFinished.connect(partial(self._on_coloring_plugin_parameter_editing_finished, param_name=name))
                widget.installEventFilter(self) # イベントフィルターをインストール
                self.coloring_plugin_widgets[name] = widget

    def _on_coloring_plugin_parameter_changed(self, value, param_name: str):
        """
        カラーリングプラグイン固有パラメータのUI要素の値が変更されたときに呼び出されるスロット。
        主にUI内部の状態更新（例：プリセットコンボボックスを「カスタム」に設定）のために使用します。
        再描画やコントローラーへのパラメータ設定は editingFinished で行います。

        Args:
            value (any): 変更後の値 (スロット接続の都合上存在するが、直接は使用しないことが多い)。
            param_name (str): 変更されたパラメータの名前。
        """
        if not self.fractal_controller: return
        sender = self.sender()
        # 値が変更されたらプリセットを「カスタム」表示にする
        if isinstance(sender, (QDoubleSpinBox, QSpinBox)):
            if '_coloring_preset_combo' in self.coloring_plugin_widgets:
                preset_combo = self.coloring_plugin_widgets['_coloring_preset_combo']
                if preset_combo.currentText() != "カスタム":
                    preset_combo.blockSignals(True)
                    preset_combo.setCurrentText("カスタム")
                    preset_combo.blockSignals(False)
        logger.log(f"ParameterPanel._on_coloring_plugin_parameter_changed: Parameter {param_name} changed in UI. Actual update and recolor will be on editing finished.", level="DEBUG")
        # ここではコントローラーへのパラメータ設定や再描画は行わない

    @pyqtSlot() # param_name を受け取るために slot デコレーターを調整する必要があるかもしれません。partialで対応済み。
    def _on_coloring_plugin_parameter_editing_finished(self, param_name: str):
        """
        カラーリングプラグイン固有パラメータの入力フィールドで編集が完了した
        (Enterキー押下またはフォーカスアウト) ときに呼び出されるスロット。
        値が変更されていれば、コントローラーにパラメータを更新し、再カラーリングを要求します。
        """
        if not self.fractal_controller: return

        widget = self.coloring_plugin_widgets.get(param_name)
        if widget and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            original_value = self._focused_value_store.pop(widget, None)
            current_value = widget.value()

            if original_value is not None and current_value != original_value:
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Value changed for {param_name} from {original_value} to {current_value}. Setting param and recoloring.", level="DEBUG")
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, current_value)
            elif original_value is None: # フォーカスイン時の値がない (通常は発生しないはずだが念のため)
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: No original value for {param_name}. Setting param and recoloring as fallback.", level="DEBUG")
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, current_value)
            else: # 値が変更されていない
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Value not changed for {param_name}. Current: {current_value}. Original: {original_value}. Skipping recolor.", level="DEBUG")
        elif widget:
            logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Widget {param_name} is not a SpinBox/DoubleSpinBox. Type: {type(widget)}. Skipping.", level="DEBUG")
        else:
            logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Widget for {param_name} not found. Skipping.", level="WARNING")

    def _populate_color_pack_combo(self):
        """
        カラーパック選択用コンボボックスに、利用可能なカラーパック名を設定します。
        """
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
        """
        カラーパック選択コンボボックスの選択が変更されたときに呼び出されるスロット。
        選択されたカラーパック内のカラーマップリストを更新し、最初のマップを選択します。

        Args:
            pack_name (str): 選択されたカラーパックの名前。
        """
        if not self.fractal_controller or not pack_name or pack_name == "N/A": return
        self._populate_color_map_list(pack_name)
        if self.color_map_listwidget.count() > 0:
            first_map_item = self.color_map_listwidget.item(0)
            if first_map_item:
                self.color_map_listwidget.setCurrentItem(first_map_item)
                # 選択が変更されなかったが、新しいパックの最初のマップに基づいて強制的に更新したい場合:
                if self.fractal_controller.get_active_color_map_name_from_engine() != first_map_item.text() or \
                   self.fractal_controller.get_active_color_pack_name_from_engine() != pack_name:
                     self.fractal_controller.set_active_color_map_and_recolor(pack_name, first_map_item.text())

    def _populate_color_map_list(self, pack_name: str | None):
        """
        指定されたカラーパック内のカラーマップをリストウィジェットに表示します。

        Args:
            pack_name (str | None): 表示するカラーマップが含まれるカラーパックの名前。Noneの場合はリストを無効化。
        """
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
        """
        カラーマップリストウィジェットの選択が変更されたときに呼び出されるスロット。
        コントローラーに選択されたカラーマップをアクティブにするよう通知します。

        Args:
            current_item (QListWidgetItem): 新しく選択されたリストアイテム。
            previous_item (QListWidgetItem): 以前選択されていたリストアイテム。
        """
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
        """
        コントローラーからの指示でカラーパックとカラーマップの選択をUIに反映します。

        Args:
            pack_name (str): 選択するカラーパックの名前。
            map_name (str): 選択するカラーマップの名前。
        """
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

    def _on_iter_spinbox_changed(self, value):
        """最大反復回数スピンボックスの値が変更されたときにスライダーを更新します。"""
        self.iter_slider.setValue(value)
        # self._on_value_changed_by_ui() # ここでは再描画をトリガーしない
    def _on_iter_slider_changed(self, value):
        """最大反復回数スライダーの値が変更されたときにスピンボックスを更新します。"""
        if self.iter_spinbox.value() != value:
            self.iter_spinbox.setValue(value)
        # else: self._on_value_changed_by_ui() # ここでは再描画をトリガーしない
    def _on_iter_slider_pressed(self):
        """iter_sliderが押されたときに現在の値を保存します。"""
        sender_slider = self.sender()
        if isinstance(sender_slider, QSlider):
            self._slider_original_value[sender_slider] = sender_slider.value()
            logger.log(f"ParameterPanel._on_iter_slider_pressed: Slider {sender_slider.objectName()} pressed. Stored value: {sender_slider.value()}", level="DEBUG")
    def _on_value_changed_by_ui(self):
        """
        共通パラメータ関連のUI要素 (中心座標、幅、反復回数) の編集が完了したときに呼び出されます。
        `parameters_changed_in_ui_signal` を発行し、値が変更されていれば再描画を試みます。
        """
        if hasattr(self, 'fractal_combo') and (self.fractal_combo.hasFocus() or self.fractal_combo.view().isVisible()):
            logger.log("ParameterPanel._on_value_changed_by_ui: Skipping trigger because fractal_combo is active.", level="DEBUG")
            return

        sender_widget = self.sender()
        if not sender_widget:
            logger.log("ParameterPanel._on_value_changed_by_ui: Sender widget is None. Skipping.", level="WARNING")
            return

        trigger_render_flag = True # デフォルトで再描画する
        param_changed_for_signal = False # parameters_changed_in_ui_signal を発行するかどうか
        widget_object_name = sender_widget.objectName() if hasattr(sender_widget, 'objectName') else str(type(sender_widget))

        if isinstance(sender_widget, (QSpinBox, QDoubleSpinBox)):
            original_value = self._focused_value_store.pop(sender_widget, None)
            current_value = sender_widget.value()
            param_changed_for_signal = True # SpinBox/DoubleSpinBox の編集完了は常に通知対象

            if original_value is not None and current_value == original_value:
                trigger_render_flag = False
                logger.log(f"ParameterPanel._on_value_changed_by_ui (SpinBox): Value not changed for {widget_object_name}. Current: {current_value}. Original: {original_value}. Skipping render.", level="DEBUG")
            elif original_value is None:
                logger.log(f"ParameterPanel._on_value_changed_by_ui (SpinBox): No original value for {widget_object_name}. Rendering.", level="DEBUG")
            else: # Value changed
                logger.log(f"ParameterPanel._on_value_changed_by_ui (SpinBox): Value changed for {widget_object_name} from {original_value} to {current_value}. Rendering.", level="DEBUG")

        elif isinstance(sender_widget, QSlider):
            original_value = self._slider_original_value.pop(sender_widget, None)
            current_value = sender_widget.value()
            param_changed_for_signal = True # Slider の編集完了も常に通知対象

            if original_value is not None and current_value == original_value:
                trigger_render_flag = False
                logger.log(f"ParameterPanel._on_value_changed_by_ui (Slider): Value not changed for {widget_object_name}. Current: {current_value}. Original: {original_value}. Skipping render.", level="DEBUG")
            elif original_value is None:
                logger.log(f"ParameterPanel._on_value_changed_by_ui (Slider): No original value for {widget_object_name}. Rendering.", level="DEBUG")
            else: # Value changed
                logger.log(f"ParameterPanel._on_value_changed_by_ui (Slider): Value changed for {widget_object_name} from {original_value} to {current_value}. Rendering.", level="DEBUG")
        else:
            # 知らないタイプのウィジェットからの場合 (例えばボタンなど、通常ここには来ないはずだが念のため)
            logger.log(f"ParameterPanel._on_value_changed_by_ui: Sender is an unexpected widget type: {widget_object_name}. Assuming render is needed.", level="WARNING")
            param_changed_for_signal = True # 不明な場合は通知しておく

        if param_changed_for_signal:
            # 現在は iter_spinbox の値のみをシグナルで送っている。
            # 将来的に他の共通パラメータも扱うようになったら、ここを修正する必要がある。
            iters = self.iter_spinbox.value()
            self.parameters_changed_in_ui_signal.emit(iters)

        if trigger_render_flag:
            if self.fractal_controller:
                logger.log(f"ParameterPanel._on_value_changed_by_ui: Calling fractal_controller.trigger_render() for {widget_object_name}", level="DEBUG")
                self.fractal_controller.trigger_render()
            else:
                logger.log("ParameterPanel._on_value_changed_by_ui: fractal_controller is None, cannot trigger render.", level="WARNING")
        else:
            logger.log(f"ParameterPanel._on_value_changed_by_ui: Render skipped for {widget_object_name} as value did not change.", level="DEBUG")

    def load_initial_parameters(self):
        """
        コントローラーから初期パラメータを取得し、UIに設定します。
        フラクタル固有UIとカラーリング固有UIも更新します。
        """
        if self.fractal_controller:
            params = self.fractal_controller.get_current_common_parameters()
            if params: self._set_ui_values(params.get('max_iterations',100))
            active_fp_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
            if active_fp_name: self._update_fractal_plugin_specific_ui(active_fp_name)
            active_cp_name = self.fractal_controller.get_active_coloring_plugin_name_from_engine()
            if active_cp_name: self._update_coloring_plugin_specific_ui(active_cp_name)
    @pyqtSlot(dict) # 引数として dict を受け取ることを明示
    def update_ui_from_controller_parameters(self, params: dict):
        """
        コントローラーから共通パラメータが外部的に更新された場合にUIを更新するスロット。
        """
        if self.fractal_controller:
            self._set_ui_values(params['max_iterations'])
    def _set_ui_values(self, iterations: int): # 他の共通パラメータも引数に追加する可能性あり
        self.iter_spinbox.blockSignals(True)
        self.iter_slider.blockSignals(True)
        self.iter_spinbox.setValue(iterations)
        self.iter_slider.setValue(iterations) # スライダーも同期
        self.iter_spinbox.blockSignals(False)
        self.iter_slider.blockSignals(False)
    def get_current_ui_parameters(self) -> dict:
        """
        現在のUIから共通パラメータの値を取得して辞書として返します。

        Returns:
            dict: 'max_iterations' をキーとする辞書。
        """
        return {"max_iterations":self.iter_spinbox.value()}

    @pyqtSlot(bool)
    def _on_rendering_state_changed(self, is_rendering: bool):
        """
        レンダリング状態が変更されたときに呼び出されるスロット。
        フラクタルタイプ選択コンボボックスの有効/無効を切り替えます。
        """
        logger.log(f"ParameterPanel._on_rendering_state_changed: Received is_rendering = {is_rendering}", level="DEBUG")

        def _update_ui():
            if hasattr(self, 'fractal_combo'):
                logger.log(f"ParameterPanel._on_rendering_state_changed (_update_ui): Setting fractal_combo.setEnabled({not is_rendering}) (before). Current state: {self.fractal_combo.isEnabled()}", level="DEBUG")
                self.fractal_combo.setEnabled(not is_rendering)
                logger.log(f"ParameterPanel._on_rendering_state_changed (_update_ui): fractal_combo.isEnabled() is now {self.fractal_combo.isEnabled()} (after).", level="DEBUG")
            else:
                logger.log("ParameterPanel._on_rendering_state_changed (_update_ui): self.fractal_combo does not exist.", level="WARNING")

        QTimer.singleShot(0, _update_ui)
        logger.log(f"ParameterPanel._on_rendering_state_changed: Scheduled _update_ui with QTimer.singleShot", level="DEBUG")

    def eventFilter(self, obj, event):
        """
        QSpinBox と QDoubleSpinBox のフォーカスイベントを監視し、
        フォーカスイン時に値を保存します。
        """
        if isinstance(obj, (QSpinBox, QDoubleSpinBox)):
            if event.type() == QEvent.Type.FocusIn:
                self._focused_value_store[obj] = obj.value()
                logger.log(f"ParameterPanel.eventFilter: FocusIn on {obj.objectName()}. Stored value: {obj.value()}", level="DEBUG")
            # FocusOut時の値クリアはeditingFinished内で行うのでここでは不要
        return super().eventFilter(obj, event)

    def _on_coloring_preset_selected(self, preset_name: str, plugin_name: str, presets_data: dict):
        """
        カラーリングプラグインのプリセットコンボボックスの選択が変更されたときに呼び出されるスロット。
        選択されたプリセットの値を対応するUI要素に設定し、コントローラーに通知します。

        Args:
            preset_name (str): 選択されたプリセットの名前。
            plugin_name (str): 対象のプラグイン名。
            presets_data (dict): プラグインのプリセットデータ。
        """
        if preset_name == "カスタム" or not self.fractal_controller: return
        selected_vals = presets_data.get(preset_name)
        if selected_vals:
            # プリセットが選択された場合、関連するすべてのパラメータを更新し、最後に一度だけ再描画をトリガーするのが理想。
            # しかし、set_coloring_plugin_parameter_and_recolor が個別に再描画するため、複数回再描画される可能性がある。
            # パフォーマンスが問題になる場合は、コントローラーに一括更新メソッドを設けることを検討。
            for p_name, val in selected_vals.items():
                if p_name in self.coloring_plugin_widgets:
                    widget = self.coloring_plugin_widgets[p_name]
                    widget.blockSignals(True)
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.setValue(val)
                         # プリセット適用時はフォーカス値をクリアまたは更新するべきか検討。
                         # ここでは一旦、プリセットからの値設定は即時反映とするため、
                         # _focused_value_store から該当ウィジェットのエントリを削除して、
                         # 次の編集時に正しく動作するようにする。
                        if widget in self._focused_value_store:
                            del self._focused_value_store[widget]
                    widget.blockSignals(False)

                # コントローラーへの通知と再カラーリング
                # logger.log(f"Preset selected: Setting {p_name} to {val} and recoloring.", "DEBUG")
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(p_name, val)

            # プリセットを適用した後、関連するウィジェットのフォーカス時の値をクリアまたは更新する。
            # これにより、プリセット適用後に値を変更せずにフォーカスアウトしても不要な再描画が走らないようにする。
            # ただし、上記のループ内で個別ウィジェットに対して focused_value_store を操作するのは煩雑なので、
            # プリセット適用後は、関連ウィジェットの editingFinished が発行された際に、
            # original_value が None となり、常に再描画が試みられる（これは許容範囲か）。
            # より丁寧には、プリセット適用時に値を _focused_value_store にも能動的にセットすることが考えられる。
            # 今回は、上記のループ内でウィジェットごとに focused_value_store をクリアする対応は一旦コメントアウトしておく。
            # -> widget.setValue の後に focused_value_store から削除するように修正。

if __name__ == '__main__':
    from logger.custom_logger import CustomLogger
    logger = CustomLogger()
    # ... (スタンドアロンテストコードは複雑なため、メインアプリケーションでのテストを推奨) ...
    logger.log("ParameterPanelのスタンドアロンテストには包括的なモックコントローラとセットアップが必要です。", level="INFO")
    logger.log("メインアプリケーションまたは専用のテストスイートでテストしてください。", level="INFO")
