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
        self.coloring_plugin_widgets_divergent = {} # 発散部用
        self.coloring_plugin_widgets_non_divergent = {} # 非発散部用
        self._focused_value_store = {} # フォーカス時の値を保存する辞書
        self._slider_original_value = {} # スライダー操作開始時の値を保存する辞書

        # UIの初期化とコントローラーからのデータ読み込み
        self._init_ui()

        if self.fractal_controller:
            self._populate_fractal_combo()
            # Divergent
            self._populate_coloring_algorithm_combo(target_type='divergent')
            self._populate_color_pack_combo(target_type='divergent')
            active_pack_divergent = self.fractal_controller.get_active_color_pack_name_from_engine(target_type='divergent')
            if active_pack_divergent:
                 self._populate_color_map_list(active_pack_divergent, target_type='divergent')
            # Non-Divergent
            self._populate_coloring_algorithm_combo(target_type='non_divergent')
            self._populate_color_pack_combo(target_type='non_divergent')
            active_pack_non_divergent = self.fractal_controller.get_active_color_pack_name_from_engine(target_type='non_divergent')
            if active_pack_non_divergent:
                 self._populate_color_map_list(active_pack_non_divergent, target_type='non_divergent')

            # コントローラーから初期パラメータをロードしてUIに反映
            self.load_initial_parameters()

            self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
            self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(self._update_fractal_plugin_specific_ui)
            # active_coloring_plugin_ui_needs_update might need to provide more info or be replaced
            # For now, assume it updates the UI for the currently selected target_type's active plugin.
            # The more specific signal below is preferred for changing target_type.
            self.fractal_controller.active_coloring_plugin_ui_needs_update.connect(
                lambda algo_name: self._update_coloring_plugin_specific_ui(algo_name, None) # Pass None for target_type to use current UI selection
            )
            # Connect to the actual signal name from FractalController
            if hasattr(self.fractal_controller, 'active_coloring_target_and_plugin_changed_externally'):
                self.fractal_controller.active_coloring_target_and_plugin_changed_externally.connect(
                    self.update_active_coloring_target_and_plugin_from_controller
                )
            else:
                logger.log("Warning: FractalController does not have 'active_coloring_target_and_plugin_changed_externally' signal.", level="WARNING")

            if hasattr(self.fractal_controller, 'active_color_map_changed_externally'):
                self.fractal_controller.active_color_map_changed_externally.connect(
                    self._update_color_selection_from_controller
                )
            else:
                logger.log("Warning: FractalController does not have 'active_color_map_changed_externally' signal.", level="WARNING")
            # self.fractal_controller.rendering_state_changed.connect(self._on_rendering_state_changed) # This line is moved to MainWindow
        else:
            # コントローラーが利用できない場合のフォールバックUI設定
            self._set_ui_values(100)
            if hasattr(self, 'plugin_specific_group'): self.plugin_specific_group.setVisible(False)
            # coloring_group は存在し続けるが、個々のサブグループを無効化する必要があるかもしれない
            if hasattr(self, 'coloring_group'): self.coloring_group.setEnabled(False) # Keep disabling the main group for now
            # if hasattr(self, 'divergent_coloring_group'): self.divergent_coloring_group.setEnabled(False)
            # if hasattr(self, 'non_divergent_coloring_group'): self.non_divergent_coloring_group.setEnabled(False)


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
        self.coloring_group.setLayout(self.true_coloring_layout)
        self.main_layout.addWidget(self.coloring_group)

        # 発散部カラーリング設定グループ
        self.divergent_coloring_group = QGroupBox("発散部カラーリング設定")
        divergent_coloring_layout = QVBoxLayout()
        self.divergent_coloring_group.setLayout(divergent_coloring_layout)
        self.true_coloring_layout.addWidget(self.divergent_coloring_group)

        # 発散部 - アルゴリズム選択
        divergent_algo_layout = QFormLayout()
        self.coloring_algorithm_combo_divergent = QComboBox()
        divergent_algo_layout.addRow(QLabel("アルゴリズム:"), self.coloring_algorithm_combo_divergent)
        divergent_coloring_layout.addLayout(divergent_algo_layout)
        self.coloring_algorithm_combo_divergent.currentTextChanged.connect(
            partial(self._on_coloring_algorithm_changed, target_type='divergent')
        )

        # 発散部 - アルゴリズム固有設定
        self.coloring_plugin_specific_group_divergent = QGroupBox("アルゴリズム固有設定")
        self.coloring_plugin_specific_layout_divergent = QFormLayout()
        self.coloring_plugin_specific_group_divergent.setLayout(self.coloring_plugin_specific_layout_divergent)
        divergent_coloring_layout.addWidget(self.coloring_plugin_specific_group_divergent)
        self.coloring_plugin_specific_group_divergent.setVisible(False)

        # 発散部 - カラーパック選択
        divergent_pack_layout = QFormLayout()
        self.color_pack_combo_divergent = QComboBox()
        divergent_pack_layout.addRow(QLabel("カラーパック:"), self.color_pack_combo_divergent)
        divergent_coloring_layout.addLayout(divergent_pack_layout)
        self.color_pack_combo_divergent.currentTextChanged.connect(
            partial(self._on_color_pack_changed, target_type='divergent')
        )

        # 発散部 - カラーマップ選択
        divergent_map_layout = QFormLayout()
        self.color_map_listwidget_divergent = QListWidget()
        self.color_map_listwidget_divergent.setIconSize(QSize(96, 18))
        self.color_map_listwidget_divergent.setSpacing(1)
        self.color_map_listwidget_divergent.setFixedHeight(120)
        divergent_map_layout.addRow(QLabel("カラーマップ:"), self.color_map_listwidget_divergent)
        divergent_coloring_layout.addLayout(divergent_map_layout)
        self.color_map_listwidget_divergent.currentItemChanged.connect(
            lambda current, previous, target_type='divergent': self._on_color_map_changed(current, previous, target_type)
        )

        # 非発散部カラーリング設定グループ
        self.non_divergent_coloring_group = QGroupBox("非発散部カラーリング設定")
        non_divergent_coloring_layout = QVBoxLayout()
        self.non_divergent_coloring_group.setLayout(non_divergent_coloring_layout)
        self.true_coloring_layout.addWidget(self.non_divergent_coloring_group)

        # 非発散部 - アルゴリズム選択
        non_divergent_algo_layout = QFormLayout()
        self.coloring_algorithm_combo_non_divergent = QComboBox()
        non_divergent_algo_layout.addRow(QLabel("アルゴリズム:"), self.coloring_algorithm_combo_non_divergent)
        non_divergent_coloring_layout.addLayout(non_divergent_algo_layout)
        self.coloring_algorithm_combo_non_divergent.currentTextChanged.connect(
            partial(self._on_coloring_algorithm_changed, target_type='non_divergent')
        )

        # 非発散部 - アルゴリズム固有設定
        self.coloring_plugin_specific_group_non_divergent = QGroupBox("アルゴリズム固有設定")
        self.coloring_plugin_specific_layout_non_divergent = QFormLayout()
        self.coloring_plugin_specific_group_non_divergent.setLayout(self.coloring_plugin_specific_layout_non_divergent)
        non_divergent_coloring_layout.addWidget(self.coloring_plugin_specific_group_non_divergent)
        self.coloring_plugin_specific_group_non_divergent.setVisible(False)

        # 非発散部 - カラーパック選択
        non_divergent_pack_layout = QFormLayout()
        self.color_pack_combo_non_divergent = QComboBox()
        non_divergent_pack_layout.addRow(QLabel("カラーパック:"), self.color_pack_combo_non_divergent)
        non_divergent_coloring_layout.addLayout(non_divergent_pack_layout)
        self.color_pack_combo_non_divergent.currentTextChanged.connect(
            partial(self._on_color_pack_changed, target_type='non_divergent')
        )

        # 非発散部 - カラーマップ選択
        non_divergent_map_layout = QFormLayout()
        self.color_map_listwidget_non_divergent = QListWidget()
        self.color_map_listwidget_non_divergent.setIconSize(QSize(96, 18))
        self.color_map_listwidget_non_divergent.setSpacing(1)
        self.color_map_listwidget_non_divergent.setFixedHeight(120)
        non_divergent_map_layout.addRow(QLabel("カラーマップ:"), self.color_map_listwidget_non_divergent)
        non_divergent_coloring_layout.addLayout(non_divergent_map_layout)
        self.color_map_listwidget_non_divergent.currentItemChanged.connect(
            lambda current, previous, target_type='non_divergent': self._on_color_map_changed(current, previous, target_type)
        )

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

    def _populate_coloring_algorithm_combo(self, target_type: str):
        """
        指定されたターゲットタイプのカラーリングアルゴリズム選択用コンボボックスに、利用可能なアルゴリズム名を設定します。
        Args:
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller: return

        combo_box = None
        if target_type == 'divergent':
            combo_box = self.coloring_algorithm_combo_divergent
        elif target_type == 'non_divergent':
            combo_box = self.coloring_algorithm_combo_non_divergent
        else:
            logger.log(f"Error: Invalid target_type '{target_type}' in _populate_coloring_algorithm_combo", level="ERROR")
            return

        if combo_box is None: # Should not happen
             logger.log(f"Error: Combo box not found for target_type '{target_type}'", level="ERROR")
             return

        logger.log(f"ParameterPanel._populate_coloring_algorithm_combo: Populating for target_type = {target_type}", level="DEBUG")

        algo_names = self.fractal_controller.get_available_coloring_plugin_names_from_engine(target_type=target_type)
        active_algo = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type)

        combo_box.blockSignals(True); combo_box.clear()
        if algo_names:
            combo_box.addItems(algo_names)
            if active_algo and active_algo in algo_names: combo_box.setCurrentText(active_algo)
            elif algo_names: combo_box.setCurrentText(algo_names[0]) # Select first one if no active one or active not in list
            combo_box.setEnabled(True)
        else:
            combo_box.addItem("N/A"); combo_box.setEnabled(False)
        combo_box.blockSignals(False)

    @pyqtSlot(str, str) # algo_name, target_type (from partial)
    def _on_coloring_algorithm_changed(self, algo_name: str, target_type: str):
        """
        カラーリングアルゴリズム選択コンボボックスの選択が変更されたときに呼び出されるスロット。
        コントローラーに選択されたアルゴリズムをアクティブにするよう通知します。

        Args:
            algo_name (str): 選択されたカラーリングアルゴリズムの名前。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller or not algo_name or algo_name == "N/A":
            # Potentially clear specific UI if algo is N/A
            if algo_name == "N/A":
                self._clear_coloring_plugin_specific_ui(target_type)
                group_to_hide = self.coloring_plugin_specific_group_divergent if target_type == 'divergent' else self.coloring_plugin_specific_group_non_divergent
                group_to_hide.setVisible(False)
            return

        # Check if this algo is already active for this target type
        if algo_name == self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type):
             logger.log(f"ParameterPanel._on_coloring_algorithm_changed: Algo '{algo_name}' for target '{target_type}' already active. Triggering UI update.", level="DEBUG")
             # Still update UI, as switching between targets might require UI refresh even if algo name is same for both
             self._update_coloring_plugin_specific_ui(algo_name, target_type)
             return

        self.fractal_controller.set_active_coloring_plugin_and_recolor(plugin_name=algo_name, target_type=target_type)
        # The controller should emit active_coloring_plugin_ui_needs_update which is connected to _update_coloring_plugin_specific_ui
        # or active_coloring_target_and_plugin_changed_externally for a more holistic update.
        # If direct update is needed: self._update_coloring_plugin_specific_ui(algo_name, target_type)


    # _on_coloring_target_changed は coloring_target_combo が削除されたため不要。
    # 呼び出し元の self.coloring_target_combo.currentTextChanged.connect(self._on_coloring_target_changed) も削除済み。

    def _clear_coloring_plugin_specific_ui(self, target_type: str):
        """
        指定されたターゲットタイプのカラーリングプラグイン固有のパラメータUI要素をクリアします。
        Args:
            target_type (str): 'divergent' または 'non_divergent'.
        """
        plugin_widgets = None
        specific_layout = None
        if target_type == 'divergent':
            plugin_widgets = self.coloring_plugin_widgets_divergent
            specific_layout = self.coloring_plugin_specific_layout_divergent
        elif target_type == 'non_divergent':
            plugin_widgets = self.coloring_plugin_widgets_non_divergent
            specific_layout = self.coloring_plugin_specific_layout_non_divergent
        else:
            logger.log(f"Error: Invalid target_type '{target_type}' in _clear_coloring_plugin_specific_ui", level="ERROR")
            return

        if plugin_widgets is None or specific_layout is None: # Should not happen if logic is correct
            logger.log(f"Error: plugin_widgets or specific_layout is None for {target_type}", level="ERROR")
            return

        plugin_widgets.clear()
        while specific_layout.count():
            item = specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str, str) # Added target_type to slot signature, assuming it's passed by caller
    def _update_coloring_plugin_specific_ui(self, algo_name: str, target_type: str):
        """
        指定されたカラーリングアルゴリズムの固有パラメータUIを構築・更新します。
        コントローラーからパラメータ定義、プリセット、現在の値を取得してUIに反映します。

        Args:
            algo_name (str): UIを更新する対象のカラーリングアルゴリズムの名前。
            target_type (str): 対象タイプ ('divergent' or 'non_divergent').
        """
        self._clear_coloring_plugin_specific_ui(target_type) # Clear the specific UI first

        logger.log(f"ParameterPanel._update_coloring_plugin_specific_ui for algo: '{algo_name}', target: '{target_type}'", level="DEBUG")

        plugin_widgets = None
        specific_group = None
        specific_layout = None

        if target_type == 'divergent':
            plugin_widgets = self.coloring_plugin_widgets_divergent
            specific_group = self.coloring_plugin_specific_group_divergent
            specific_layout = self.coloring_plugin_specific_layout_divergent
        elif target_type == 'non_divergent':
            plugin_widgets = self.coloring_plugin_widgets_non_divergent
            specific_group = self.coloring_plugin_specific_group_non_divergent
            specific_layout = self.coloring_plugin_specific_layout_non_divergent
        else:
            logger.log(f"Error: Invalid target_type '{target_type}' in _update_coloring_plugin_specific_ui", level="ERROR")
            return

        # specific_layout が割り当てられた後
        # layout_type_name = "NoneType" # 初期化
        # layout_id = "N/A" # 初期化
        # if specific_layout is not None:
        #     layout_type_name = __builtins__.type(specific_layout).__name__ # ここを修正
        #     layout_id = id(specific_layout)
        # logger.log(f"Targeting layout for {target_type}: {layout_type_name} - ID: {layout_id}", level="DEBUG")

        if not self.fractal_controller or not algo_name or algo_name == "N/A":
            if specific_group: specific_group.setVisible(False)
            logger.log(f"No controller, algo_name, or algo_name is N/A. Hiding specific group for {target_type}.", level="DEBUG")
            return

        param_defs = self.fractal_controller.get_coloring_plugin_parameter_definitions_from_engine(algo_name, target_type=target_type)
        logger.log(f"param_defs for '{algo_name}' ({target_type}): {param_defs}", level="DEBUG") # Log param_defs content

        if not param_defs:
            if specific_group: specific_group.setVisible(False)
            logger.log(f"No param_defs found for '{algo_name}' ({target_type}). Hiding specific group.", level="DEBUG")
            return

        if specific_group:
            specific_group.setVisible(True)
            logger.log(f"Specific group for {target_type} set to visible for algo '{algo_name}'.", level="DEBUG")

        target_display_name = "発散部" if target_type == 'divergent' else "非発散部"
        if specific_group: specific_group.setTitle(f"{algo_name} ({target_display_name}) 固有設定")
        current_vals = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine(target_type=target_type)
        logger.log(f"Current values for {target_type} specific params: {current_vals}", level="DEBUG")

        presets = self.fractal_controller.get_plugin_presets(algo_name, target_type=target_type)
        if presets:
            logger.log(f"Presets found for '{algo_name}' ({target_type}): {list(presets.keys())}", level="DEBUG")
            preset_combo = QComboBox()
            preset_combo.addItem("カスタム")
            for preset_name in presets.keys(): preset_combo.addItem(preset_name)
            preset_combo.currentTextChanged.connect(
                partial(self._on_coloring_preset_selected, plugin_name=algo_name, presets_data=presets.copy(), target_type=target_type)
            )
            if specific_layout: specific_layout.addRow(QLabel("プリセット:"), preset_combo)
            if plugin_widgets: plugin_widgets['_coloring_preset_combo'] = preset_combo
        else:
            logger.log(f"No presets found for '{algo_name}' ({target_type}).", level="DEBUG")

        logger.log(f"Looping through param_defs for '{algo_name}' ({target_type}). Number of defs: {len(param_defs) if param_defs else 0}", level="DEBUG")
        for p_def in param_defs:
            lbl_text=p_def.get('label',p_def['name']); name=p_def['name']; type=p_def.get('type','float')
            val=current_vals.get(name, p_def.get('default')); widget=None
            logger.log(f"Processing p_def: name='{name}', type='{type}', label='{lbl_text}', default='{p_def.get('default')}', current_val_from_engine='{current_vals.get(name)}', final_val_for_widget='{val}'", level="DEBUG")

            if type == 'float':
                widget=QDoubleSpinBox()
                widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1])
                widget.setValue(val if val is not None else 0.0)
                widget.setSingleStep(p_def.get('step',0.01))
                widget.setDecimals(p_def.get('decimals',3))
                logger.log(f"Created QDoubleSpinBox for '{name}' with value {widget.value()}", level="DEBUG")
            elif type == 'int':
                widget=QSpinBox()
                widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1])
                widget.setValue(val if val is not None else 0)
                widget.setSingleStep(p_def.get('step',1))
                logger.log(f"Created QSpinBox for '{name}' with value {widget.value()}", level="DEBUG")

            if widget:
                if 'tooltip' in p_def: widget.setToolTip(p_def['tooltip'])
                if specific_layout:
                    specific_layout.addRow(QLabel(lbl_text + ":"), widget)
                    # logger.log(f"Added widget for '{name}' to layout for {target_type}. Layout row count: {specific_layout.rowCount()}", level="DEBUG")
                # else:
                    # logger.log(f"ERROR: specific_layout is None when trying to add widget for '{name}' ({target_type})", level="ERROR")
                widget.valueChanged.connect(partial(self._on_coloring_plugin_parameter_changed, param_name=name, target_type=target_type))
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.editingFinished.connect(partial(self._on_coloring_plugin_parameter_editing_finished, param_name=name, target_type=target_type))
                widget.installEventFilter(self)
                if plugin_widgets: plugin_widgets[name] = widget
            else:
                logger.log(f"Widget not created for p_def: {p_def}", level="WARNING")

    def _on_coloring_plugin_parameter_changed(self, value, param_name: str, target_type: str):
        """
        カラーリングプラグイン固有パラメータのUI要素の値が変更されたときに呼び出されるスロット。
        主にUI内部の状態更新（例：プリセットコンボボックスを「カスタム」に設定）のために使用します。
        再描画やコントローラーへのパラメータ設定は editingFinished で行います。

        Args:
            value (any): 変更後の値 (スロット接続の都合上存在するが、直接は使用しないことが多い)。
            param_name (str): 変更されたパラメータの名前。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller: return
        sender = self.sender()

        plugin_widgets = self.coloring_plugin_widgets_divergent if target_type == 'divergent' else self.coloring_plugin_widgets_non_divergent

        if isinstance(sender, (QDoubleSpinBox, QSpinBox)):
            if '_coloring_preset_combo' in plugin_widgets:
                preset_combo = plugin_widgets['_coloring_preset_combo']
                if preset_combo.currentText() != "カスタム":
                    preset_combo.blockSignals(True)
                    preset_combo.setCurrentText("カスタム")
                    preset_combo.blockSignals(False)
        logger.log(f"ParameterPanel._on_coloring_plugin_parameter_changed: Parameter {param_name} for {target_type} changed in UI. Actual update and recolor will be on editing finished.", level="DEBUG")

    @pyqtSlot() # param_name と target_type を受け取るために slot デコレーターを調整する必要があるかもしれません。partialで対応済み。
    def _on_coloring_plugin_parameter_editing_finished(self, param_name: str, target_type: str):
        """
        カラーリングプラグイン固有パラメータの入力フィールドで編集が完了した
        (Enterキー押下またはフォーカスアウト) ときに呼び出されるスロット。
        値が変更されていれば、コントローラーにパラメータを更新し、再カラーリングを要求します。
        Args:
            param_name (str): 変更されたパラメータの名前。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller: return

        plugin_widgets = self.coloring_plugin_widgets_divergent if target_type == 'divergent' else self.coloring_plugin_widgets_non_divergent
        widget = plugin_widgets.get(param_name)

        if widget and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            original_value = self._focused_value_store.pop(widget, None) # pop from the shared store
            current_value = widget.value()

            if original_value is not None and current_value != original_value:
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Value changed for {param_name} ({target_type}) from {original_value} to {current_value}. Setting param and recoloring.", level="DEBUG")
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, current_value, target_type=target_type)
            elif original_value is None:
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: No original value for {param_name} ({target_type}). Setting param and recoloring as fallback.", level="DEBUG")
                self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, current_value, target_type=target_type)
            else:
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Value not changed for {param_name} ({target_type}). Current: {current_value}. Original: {original_value}. Skipping recolor.", level="DEBUG")
        elif widget:
            logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Widget {param_name} ({target_type}) is not a SpinBox/DoubleSpinBox. Type: {type(widget)}. Skipping.", level="DEBUG")
        else:
            logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Widget for {param_name} ({target_type}) not found. Skipping.", level="WARNING")

    def _populate_color_pack_combo(self, target_type: str):
        """
        指定されたターゲットタイプのカラーパック選択用コンボボックスに、利用可能なカラーパック名を設定します。
        Args:
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller: return

        combo_box = self.color_pack_combo_divergent if target_type == 'divergent' else self.color_pack_combo_non_divergent

        pack_names = self.fractal_controller.get_available_color_pack_names_from_engine() # Packs are global, not target_type specific
        active_pack = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type) # Active pack can be per target

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

    @pyqtSlot(str, str) # pack_name, target_type (from partial)
    def _on_color_pack_changed(self, pack_name: str, target_type: str):
        """
        カラーパック選択コンボボックスの選択が変更されたときに呼び出されるスロット。
        選択されたカラーパック内のカラーマップリストを更新し、最初のマップを選択します。

        Args:
            pack_name (str): 選択されたカラーパックの名前。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller or not pack_name or pack_name == "N/A": return

        map_list_widget = self.color_map_listwidget_divergent if target_type == 'divergent' else self.color_map_listwidget_non_divergent
        self._populate_color_map_list(pack_name, target_type) # Pass target_type

        if map_list_widget.count() > 0:
            first_map_item = map_list_widget.item(0)
            if first_map_item:
                map_list_widget.setCurrentItem(first_map_item) # This will trigger _on_color_map_changed
                # If setCurrentItem doesn't trigger if it's already selected, or for other reasons,
                # ensure the controller is updated if the state is inconsistent.
                if self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type) != first_map_item.text() or \
                   self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type) != pack_name:
                     self.fractal_controller.set_active_color_map_and_recolor(pack_name, first_map_item.text(), target_type=target_type)

    def _populate_color_map_list(self, pack_name: str | None, target_type: str):
        """
        指定されたカラーパック内のカラーマップをリストウィジェットに表示します。

        Args:
            pack_name (str | None): 表示するカラーマップが含まれるカラーパックの名前。Noneの場合はリストを無効化。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        map_list_widget = self.color_map_listwidget_divergent if target_type == 'divergent' else self.color_map_listwidget_non_divergent

        map_list_widget.blockSignals(True)
        map_list_widget.clear()
        if not self.fractal_controller or not pack_name:
            map_list_widget.setEnabled(False); map_list_widget.blockSignals(False); return

        map_names = self.fractal_controller.get_color_map_names_in_pack_from_engine(pack_name) # Maps are global within a pack
        active_map_name = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)
        # Active pack for this target, to ensure we are only setting current item if pack is also correct
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

    @pyqtSlot(QListWidgetItem, QListWidgetItem, str) # current, previous, target_type (from partial)
    def _on_color_map_changed(self, current_item: QListWidgetItem, previous_item: QListWidgetItem, target_type: str):
        """
        カラーマップリストウィジェットの選択が変更されたときに呼び出されるスロット。
        コントローラーに選択されたカラーマップをアクティブにするよう通知します。

        Args:
            current_item (QListWidgetItem): 新しく選択されたリストアイテム。
            previous_item (QListWidgetItem): 以前選択されていたリストアイテム。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller or not current_item: return
        map_name = current_item.text()

        pack_combo = self.color_pack_combo_divergent if target_type == 'divergent' else self.color_pack_combo_non_divergent
        pack_name = pack_combo.currentText()

        if not pack_name or pack_name == "N/A": return

        active_pack_ctrl = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)
        active_map_ctrl = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)

        if pack_name == active_pack_ctrl and map_name == active_map_ctrl:
            logger.log(f"Color map {map_name} in pack {pack_name} for {target_type} is already active.", level="DEBUG")
            return
        self.fractal_controller.set_active_color_map_and_recolor(pack_name, map_name, target_type=target_type)

    @pyqtSlot(str, str, str) # pack_name, map_name, target_type
    def _update_color_selection_from_controller(self, pack_name: str, map_name: str, target_type: str):
        """
        コントローラーからの指示でカラーパックとカラーマップの選択をUIに反映します。
        Args:
            pack_name (str): 選択するカラーパックの名前。
            map_name (str): 選択するカラーマップの名前。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        logger.log(f"ParameterPanel._update_color_selection_from_controller for target '{target_type}', pack '{pack_name}', map '{map_name}'", level="DEBUG")

        pack_combo = None
        map_list_widget = None

        if target_type == 'divergent':
            pack_combo = self.color_pack_combo_divergent
            map_list_widget = self.color_map_listwidget_divergent
        elif target_type == 'non_divergent':
            pack_combo = self.color_pack_combo_non_divergent
            map_list_widget = self.color_map_listwidget_non_divergent
        else:
            logger.log(f"Invalid target_type '{target_type}' in _update_color_selection_from_controller", level="ERROR")
            return

        if not pack_combo or not map_list_widget: return # Should not happen

        pack_combo.blockSignals(True)
        map_list_widget.blockSignals(True)

        if pack_combo.currentText() != pack_name:
            # Check if pack_name exists in combo, if not, re-populate packs (though packs are usually static)
            items = [pack_combo.itemText(i) for i in range(pack_combo.count())]
            if pack_name not in items:
                 logger.log(f"Pack '{pack_name}' not found in combo for {target_type}, re-populating packs.", level="INFO")
                 self._populate_color_pack_combo(target_type) # Re-populate packs
            pack_combo.setCurrentText(pack_name)
            self._populate_color_map_list(pack_name, target_type) # Ensure map list is for the new pack
        else:
            # If pack hasn't changed, still ensure the map list is correctly populated (e.g., if it was empty before)
            if map_list_widget.count() == 0 and pack_name and pack_name != "N/A":
                self._populate_color_map_list(pack_name, target_type)


        found = False
        for i in range(map_list_widget.count()):
            item = map_list_widget.item(i)
            if item.text() == map_name:
                map_list_widget.setCurrentItem(item)
                found = True
                break
        if not found:
            logger.log(f"Map '{map_name}' not found in list for pack '{pack_name}' ({target_type}).", level="WARNING")

        pack_combo.blockSignals(False)
        map_list_widget.blockSignals(False)

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

            # Fractal plugin UI
            active_fp_name = self.fractal_controller.get_active_fractal_plugin_name_from_engine()
            if active_fp_name: self._update_fractal_plugin_specific_ui(active_fp_name)

            # Coloring plugin UI - Initialize for 'divergent' first
            # self.coloring_target_combo.blockSignals(True) # 削除されたためコメントアウト
            # self.coloring_target_combo.setCurrentText("発散部") # 削除されたためコメントアウト
            # self.coloring_target_combo.blockSignals(False) # 削除されたためコメントアウト

            # self._populate_coloring_algorithm_combo() # Populates based on "発散部" # 修正が必要なためコメントアウト

            # active_target_type = 'divergent' # Since we just set it
            # # Ensure active_cp_name is fetched for the current target_type
            # active_cp_name = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=active_target_type)

            # if active_cp_name and active_cp_name != "N/A":
            #      # self.coloring_algorithm_combo.blockSignals(True) # 古い要素のためコメントアウト
            #      # self.coloring_algorithm_combo.setCurrentText(active_cp_name) # 古い要素のためコメントアウト
            #      # self.coloring_algorithm_combo.blockSignals(False) # 古い要素のためコメントアウト
            #      # self._update_coloring_plugin_specific_ui(active_cp_name, target_type=active_target_type) # 修正が必要なためコメントアウト
            #      pass # TODO: 新しい divergent/non-divergent UI 要素に対して設定を行う
            # elif False : # self.coloring_algorithm_combo.count() > 0 : # 古い要素のため False に変更
            #     # first_algo = self.coloring_algorithm_combo.itemText(0) # 古い要素のためコメントアウト
            #     # if first_algo and first_algo != "N/A":
            #     #     self.coloring_algorithm_combo.blockSignals(True) # 古い要素のためコメントアウト
            #     #     self.coloring_algorithm_combo.setCurrentText(first_algo) # 古い要素のためコメントアウト
            #     #     self.coloring_algorithm_combo.blockSignals(False) # 古い要素のためコメントアウト
            #     #     self._update_coloring_plugin_specific_ui(first_algo, target_type=active_target_type) # 修正が必要なためコメントアウト
            #     #     self.fractal_controller.set_active_coloring_plugin_and_recolor(plugin_name=first_algo, target_type=active_target_type) # 修正が必要
            # Divergent
            active_algo_div = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type='divergent')
            if active_algo_div and active_algo_div != "N/A":
                 self.coloring_algorithm_combo_divergent.blockSignals(True)
                 self.coloring_algorithm_combo_divergent.setCurrentText(active_algo_div)
                 self.coloring_algorithm_combo_divergent.blockSignals(False)
                 self._update_coloring_plugin_specific_ui(active_algo_div, target_type='divergent')
            elif self.coloring_algorithm_combo_divergent.count() > 0:
                first_algo_div = self.coloring_algorithm_combo_divergent.itemText(0)
                if first_algo_div and first_algo_div != "N/A":
                    self.coloring_algorithm_combo_divergent.setCurrentText(first_algo_div) # This will trigger _on_coloring_algorithm_changed
                    # Controller update will happen in _on_coloring_algorithm_changed if text actually changes

            active_pack_div = self.fractal_controller.get_active_color_pack_name_from_engine(target_type='divergent')
            active_map_div = self.fractal_controller.get_active_color_map_name_from_engine(target_type='divergent')
            if active_pack_div and active_map_div:
                self.color_pack_combo_divergent.blockSignals(True)
                self.color_pack_combo_divergent.setCurrentText(active_pack_div)
                self.color_pack_combo_divergent.blockSignals(False)
                self._populate_color_map_list(active_pack_div, target_type='divergent')
                # Find and set current item for map
                for i in range(self.color_map_listwidget_divergent.count()):
                    if self.color_map_listwidget_divergent.item(i).text() == active_map_div:
                        self.color_map_listwidget_divergent.setCurrentRow(i)
                        break
            elif self.color_pack_combo_divergent.count() > 0: # if no active, select first pack and map
                 first_pack_div = self.color_pack_combo_divergent.itemText(0)
                 if first_pack_div and first_pack_div != "N/A":
                    self.color_pack_combo_divergent.setCurrentText(first_pack_div) # Triggers pack changed -> populates map list & selects first map


            # Non-Divergent
            active_algo_non_div = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type='non_divergent')
            if active_algo_non_div and active_algo_non_div != "N/A":
                 self.coloring_algorithm_combo_non_divergent.blockSignals(True)
                 self.coloring_algorithm_combo_non_divergent.setCurrentText(active_algo_non_div)
                 self.coloring_algorithm_combo_non_divergent.blockSignals(False)
                 self._update_coloring_plugin_specific_ui(active_algo_non_div, target_type='non_divergent')
            elif self.coloring_algorithm_combo_non_divergent.count() > 0:
                first_algo_non_div = self.coloring_algorithm_combo_non_divergent.itemText(0)
                if first_algo_non_div and first_algo_non_div != "N/A":
                     self.coloring_algorithm_combo_non_divergent.setCurrentText(first_algo_non_div)

            active_pack_non_div = self.fractal_controller.get_active_color_pack_name_from_engine(target_type='non_divergent')
            active_map_non_div = self.fractal_controller.get_active_color_map_name_from_engine(target_type='non_divergent')
            if active_pack_non_div and active_map_non_div:
                self.color_pack_combo_non_divergent.blockSignals(True)
                self.color_pack_combo_non_divergent.setCurrentText(active_pack_non_div)
                self.color_pack_combo_non_divergent.blockSignals(False)
                self._populate_color_map_list(active_pack_non_div, target_type='non_divergent')
                for i in range(self.color_map_listwidget_non_divergent.count()):
                    if self.color_map_listwidget_non_divergent.item(i).text() == active_map_non_div:
                        self.color_map_listwidget_non_divergent.setCurrentRow(i)
                        break
            elif self.color_pack_combo_non_divergent.count() > 0:
                 first_pack_non_div = self.color_pack_combo_non_divergent.itemText(0)
                 if first_pack_non_div and first_pack_non_div != "N/A":
                    self.color_pack_combo_non_divergent.setCurrentText(first_pack_non_div)


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

    def _on_coloring_preset_selected(self, preset_name: str, plugin_name: str, presets_data: dict, target_type: str):
        """
        カラーリングプラグインのプリセットコンボボックスの選択が変更されたときに呼び出されるスロット。
        選択されたプリセットの値を対応するUI要素に設定し、コントローラーに通知します。

        Args:
            preset_name (str): 選択されたプリセットの名前。
            plugin_name (str): 対象のプラグイン名。
            presets_data (dict): プラグインのプリセットデータ。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if preset_name == "カスタム" or not self.fractal_controller: return

        logger.log(f"Applying preset '{preset_name}' for plugin '{plugin_name}' on target '{target_type}'", level="DEBUG")

        plugin_widgets_dict = self.coloring_plugin_widgets_divergent if target_type == 'divergent' else self.coloring_plugin_widgets_non_divergent
        algo_combo = self.coloring_algorithm_combo_divergent if target_type == 'divergent' else self.coloring_algorithm_combo_non_divergent

        selected_vals = presets_data.get(preset_name)
        if selected_vals:
            # Verify the currently selected algorithm in the UI matches the plugin_name for this preset.
            # This is a sanity check.
            current_ui_algo_name = algo_combo.currentText()
            if current_ui_algo_name != plugin_name:
                logger.log(f"Preset selection for plugin '{plugin_name}' but UI shows '{current_ui_algo_name}' for {target_type}. Aborting preset application.", level="WARNING")
                return

            all_params_set_for_preset = True
            params_to_set_in_controller = {}

            for p_name, val in selected_vals.items():
                if p_name in plugin_widgets_dict:
                    widget = plugin_widgets_dict[p_name]
                    widget.blockSignals(True) # Block signals while setting value to prevent immediate feedback loops
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.setValue(val)
                        # Clear any stored focus-in value for this widget to ensure that if the user
                        # clicks away without changing, it doesn't revert or trigger unwanted renders.
                        if widget in self._focused_value_store:
                            del self._focused_value_store[widget]
                    # TODO: Add support for other widget types if necessary (e.g., QComboBox for enums)
                    else:
                        logger.log(f"Widget '{p_name}' for preset is not a SpinBox/DoubleSpinBox. Type: {type(widget)}. Value not set from preset.", level="WARNING")

                    widget.blockSignals(False) # Unblock signals
                    params_to_set_in_controller[p_name] = val # Collect params for controller
                else:
                    all_params_set_for_preset = False
                    logger.log(f"Widget for preset parameter '{p_name}' not found in {target_type} UI.", level="WARNING")

            # Update all parameters in the controller in a batch if possible, then trigger one recolor.
            # This assumes FractalController has a method like set_coloring_plugin_parameters_batch_and_recolor
            # or we set them individually then trigger recolor.
            if params_to_set_in_controller:
                # Option 1: Batch update (preferred if available)
                if hasattr(self.fractal_controller, 'set_coloring_plugin_parameters_batch_and_recolor'):
                    self.fractal_controller.set_coloring_plugin_parameters_batch_and_recolor(params_to_set_in_controller, target_type=target_type, allow_recolor=True)
                else:
                    # Option 2: Individual updates then one recolor
                    for p_name, val in params_to_set_in_controller.items():
                        self.fractal_controller.set_coloring_plugin_parameter(p_name, val, target_type=target_type, allow_recolor=False) # Set without recolor first
                    self.fractal_controller.trigger_recolor(target_type=target_type) # Then trigger recolor once

            if not all_params_set_for_preset:
                 logger.log(f"Not all parameters from preset '{preset_name}' were applied to the UI for {target_type}.", level="WARNING")

            # After applying a preset, ensure the preset combo itself (if it was part of `plugin_widgets_dict`)
            # correctly reflects the chosen preset name, and not "カスタム" if the preset was successfully applied.
            # This should already be the case as the user selected it, but good to be mindful.
            # The UI update for parameters should be handled by the controller signals if parameters changed there.

    @pyqtSlot(str, str) # preset_name argument removed
    def update_active_coloring_target_and_plugin_from_controller(self, target_type: str, plugin_name: str): # preset_name argument removed
        """
        コントローラーからの指示でアクティブなカラーリングターゲットとプラグインを更新します。
        """
        logger.log(f"ParameterPanel.update_active_coloring_target_and_plugin_from_controller: target='{target_type}', plugin='{plugin_name}'", level="DEBUG") # preset_name removed from log

        algo_combo = None
        # plugin_widgets_dict = None # No longer needed for preset logic

        if target_type == 'divergent':
            algo_combo = self.coloring_algorithm_combo_divergent
            # plugin_widgets_dict = self.coloring_plugin_widgets_divergent # No longer needed
        elif target_type == 'non_divergent':
            algo_combo = self.coloring_algorithm_combo_non_divergent
            # plugin_widgets_dict = self.coloring_plugin_widgets_non_divergent # No longer needed
        else:
            logger.log(f"Invalid target_type '{target_type}' received.", level="ERROR")
            return

        if not algo_combo: return # Should not happen

        # 1. Update algorithm combo box selection
        algo_combo.blockSignals(True)
        current_algo_text = algo_combo.currentText()
        if current_algo_text != plugin_name:
            items = [algo_combo.itemText(i) for i in range(algo_combo.count())]
            if plugin_name not in items:
                logger.log(f"Plugin '{plugin_name}' not found in combo for {target_type}, re-populating.", level="INFO")
                self._populate_coloring_algorithm_combo(target_type)
            algo_combo.setCurrentText(plugin_name)
        algo_combo.blockSignals(False)

        # 2. Update the plugin specific UI for the new algorithm
        self._update_coloring_plugin_specific_ui(plugin_name, target_type)

        # 3. Preset related logic removed
        # if preset_name:
        #     ...
        # else:
        #     ...


if __name__ == '__main__':
    pass
