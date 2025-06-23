from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGroupBox, QFormLayout, QHBoxLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QTabWidget,
    QListWidget, QListWidgetItem, QAbstractSpinBox, QSlider, QListView
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QTimer, QEvent, QModelIndex # QEvent, QModelIndex を追加
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QLinearGradient, QIcon
from functools import partial
from logger.custom_logger import CustomLogger # これが存在することを確認
from .color_map_model import ColorMapModel # 新しいモデルをインポート
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controllers.fractal_controller import FractalController # 型ヒント用にインポート

logger = CustomLogger() # この行を追加

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

    def __init__(self, fractal_controller: 'FractalController', parent=None):
        """
        ParameterPanel を初期化します。

        Args:
            fractal_controller (FractalController): パラメータの管理と更新を行うコントローラー。 # 型ヒントを FractalController に変更
            parent (QWidget, optional): 親ウィジェット。 Defaults to None.
        """
        super().__init__(parent)
        self.fractal_controller = fractal_controller
        self.plugin_widgets = {} # フラクタルプラグイン用
        self.coloring_widgets = {} # カラーリングプラグイン用 (Divergent/Non-Divergent)
        self._focused_value_store = {} # フォーカス時の値を保存する辞書

        # デバウンス用タイマーと再描画要求の状態管理
        self.redraw_timer = QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(300)  # 300msのデバウンス遅延
        self.redraw_timer.timeout.connect(self._execute_redraw)
        self._redraw_request = {'full_recompute': False, 'pending': False}

        # UIの初期化とコントローラーからのデータ読み込み
        self._init_ui()

        if self.fractal_controller:
            # UIに初期データを投入
            self._populate_fractal_combo()
            for target_type in ['divergent', 'non_divergent']:
                self._populate_coloring_algorithm_combo(target_type)
                self._populate_color_pack_combo(target_type)
            self.load_initial_parameters()

            # コントローラーからのシグナルを接続
            self.fractal_controller.parameters_updated_externally.connect(self.update_ui_from_controller_parameters)
            self.fractal_controller.active_fractal_plugin_ui_needs_update.connect(self._update_fractal_plugin_specific_ui)
            # active_coloring_plugin_ui_needs_update は、より多くの情報を提供する必要があるか、置き換えられる可能性があります
            # 現時点では、現在選択されている target_type のアクティブなプラグインのUIを更新すると仮定します。
            # ターゲットタイプを変更する場合は、以下のより具体的なシグナルが推奨されます。
            self.fractal_controller.active_coloring_plugin_ui_needs_update.connect(
                lambda algo_name: self._update_coloring_plugin_specific_ui(algo_name, None) # target_type に None を渡し、現在のUI選択を使用します
            )
            # FractalController からの実際のシグナル名に接続
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
            # self.fractal_controller.rendering_state_changed.connect(self._on_rendering_state_changed) # この行は MainWindow に移動されました
        else:
            # コントローラーが利用できない場合のフォールバックUI設定
            self._set_ui_values(100)
            if hasattr(self, 'plugin_specific_group'): self.plugin_specific_group.setVisible(False)
            if hasattr(self, 'coloring_tabs'): self.coloring_tabs.setEnabled(False)

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
        # fractal_group = QGroupBox("フラクタル選択")
        # fractal_layout = QVBoxLayout(); self.fractal_combo = QComboBox()
        # fractal_layout.addWidget(self.fractal_combo); fractal_group.setLayout(fractal_layout)
        fractal_group = QGroupBox("フラクタル選択")
        fractal_form_layout = QFormLayout() # QVBoxLayout から QFormLayout に変更
        fractal_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        fractal_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.fractal_combo = QComboBox()
        fractal_form_layout.addRow(QLabel("タイプ:"), self.fractal_combo) # ラベルとウィジェットのペアとして追加
        fractal_group.setLayout(fractal_form_layout)
        self.main_layout.addWidget(fractal_group)
        self.fractal_combo.currentTextChanged.connect(self._on_fractal_type_changed)

        # 共通パラメータ
        common_params_group = QGroupBox("共通描画設定")
        self.common_params_layout = QFormLayout()
        self.common_params_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.common_params_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.iter_spinbox = QSpinBox()
        self.iter_spinbox.setRange(10, 100000)
        self.iter_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.iter_spinbox.installEventFilter(self)

        self.iter_slider = QSlider(Qt.Orientation.Horizontal)
        self.iter_slider.setRange(10, 100000)

        # スピンボックスとスライダーを横に並べるためのレイアウト
        iter_widget_layout = QHBoxLayout()
        iter_widget_layout.setContentsMargins(0, 0, 0, 0)
        iter_widget_layout.addWidget(self.iter_spinbox, 1) # スピンボックスが幅の約1/4を占める
        iter_widget_layout.addWidget(self.iter_slider, 3)  # スライダーが幅の約3/4を占める
        iter_widget = QWidget()
        iter_widget.setLayout(iter_widget_layout)

        self.common_params_layout.addRow(QLabel("最大反復回数:"), iter_widget)
        common_params_group.setLayout(self.common_params_layout)
        self.main_layout.addWidget(common_params_group)

        # フラクタルプラグイン固有設定
        self.plugin_specific_group = QGroupBox("フラクタル固有設定")
        self.plugin_specific_layout = QFormLayout()
        self.plugin_specific_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.plugin_specific_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.plugin_specific_group.setLayout(self.plugin_specific_layout)
        self.main_layout.addWidget(self.plugin_specific_group)
        self.plugin_specific_group.setVisible(False)

        # カラーリング設定をタブで分ける
        # QGroupBoxを削除し、QTabWidgetを直接メインレイアウトに追加してUIの階層を浅くし、すっきりと見せます。
        self.coloring_tabs = QTabWidget()
        self.main_layout.addWidget(self.coloring_tabs)

        divergent_tab = self._create_coloring_tab('divergent')
        self.coloring_tabs.addTab(divergent_tab, "発散部")

        non_divergent_tab = self._create_coloring_tab('non_divergent')
        self.coloring_tabs.addTab(non_divergent_tab, "非発散部")

        self.main_layout.addStretch(1)

        # 再描画をトリガーするシグナル接続
        self.iter_spinbox.editingFinished.connect(self._on_value_changed_by_ui)
        self.iter_slider.sliderReleased.connect(self._on_value_changed_by_ui) # スライダー解放時に再描画

        # スピンボックスとスライダーの値を同期させる
        self.iter_spinbox.valueChanged.connect(self.iter_slider.setValue)
        self.iter_slider.valueChanged.connect(self.iter_spinbox.setValue)

    def _create_coloring_tab(self, target_type: str) -> QWidget:
        """指定されたターゲットタイプ（'divergent' または 'non_divergent'）用のUIタブを作成します。"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)

        # このタブのウィジェットを格納する辞書
        widgets = {'plugin_widgets': {}}

        # アルゴリズム選択
        algo_layout = QFormLayout()
        algo_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        algo_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['algo_combo'] = QComboBox()
        algo_layout.addRow(QLabel("アルゴリズム:"), widgets['algo_combo'])
        layout.addLayout(algo_layout)
        widgets['algo_combo'].currentTextChanged.connect(
            partial(self._on_coloring_algorithm_changed, target_type=target_type)
        )

        # アルゴリズム固有設定
        widgets['specific_group'] = QGroupBox("アルゴリズム固有設定")
        widgets['specific_layout'] = QFormLayout()
        widgets['specific_layout'].setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        widgets['specific_layout'].setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['specific_group'].setLayout(widgets['specific_layout'])
        layout.addWidget(widgets['specific_group'])
        widgets['specific_group'].setVisible(False)

        # カラーパック選択
        pack_layout = QFormLayout()
        pack_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        pack_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['pack_combo'] = QComboBox()
        pack_layout.addRow(QLabel("カラーパック:"), widgets['pack_combo'])
        layout.addLayout(pack_layout)
        widgets['pack_combo'].currentTextChanged.connect(
            partial(self._on_color_pack_changed, target_type=target_type)
        )

        # カラーマップ選択
        map_layout = QFormLayout()
        map_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        map_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        widgets['map_list'] = QListView()
        list_view = widgets['map_list']
        list_view.setModel(ColorMapModel(list_view)) # モデルを早期に設定してselectionModelを確保
        list_view.setViewMode(QListView.ViewMode.IconMode)
        list_view.setFlow(QListView.Flow.LeftToRight)
        list_view.setWrapping(True)
        list_view.setResizeMode(QListView.ResizeMode.Adjust)
        list_view.setSpacing(5)
        icon_size = QSize(96, 18)
        list_view.setIconSize(icon_size)
        # グリッドサイズをアイコンとテキスト（下に表示される）に合わせて調整
        list_view.setGridSize(QSize(icon_size.width() + 10, icon_size.height() + 25))
        list_view.setFixedHeight(120)
        list_view.setUniformItemSizes(True) # パフォーマンス向上のため

        map_layout.addRow(QLabel("カラーマップ:"), widgets['map_list'])
        layout.addLayout(map_layout)
        # QListViewではselectionModel().currentChangedを使用する
        widgets['map_list'].selectionModel().currentChanged.connect(
            lambda current, previous, tt=target_type: self._on_color_map_changed(current, previous, tt)
        )

        self.coloring_widgets[target_type] = widgets
        return tab_widget

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
            elif plugin_names: self.fractal_combo.setCurrentText(plugin_names[0]) # アクティブなものがないか、アクティブなものがリストにない場合は最初のものを選択
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

        # コンボボックスの状態に関する詳細ログ
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

    def request_redraw(self, full_recompute: bool):
        """
        デバウンス付きで再描画を要求します。
        短時間に複数の要求があった場合、最後の要求から一定時間後に一度だけ実行されます。
        フル再計算の要求は、再カラーリングのみの要求を上書きします。

        Args:
            full_recompute (bool): Trueの場合、フラクタル計算を含む完全な再描画を要求します。
                                   Falseの場合、再カラーリングのみを要求します。
        """
        # 要求を更新。full_recompute は一度 True になったら、タイマーが実行されるまで False に戻らないようにする。
        self._redraw_request['full_recompute'] = self._redraw_request.get('full_recompute', False) or full_recompute
        self._redraw_request['pending'] = True

        logger.log(f"再描画を要求しました (フル再計算: {self._redraw_request['full_recompute']})。タイマーを開始します。", level="DEBUG")
        self.redraw_timer.start() # タイマーを再スタート

    def _execute_redraw(self):
        """
        タイマーのタイムアウト時に実際に再描画をトリガーします。
        """
        if not self._redraw_request.get('pending', False):
            return

        if self.fractal_controller:
            full_recompute = self._redraw_request.get('full_recompute', False)
            logger.log(f"デバウンスされた再描画を実行します (フル再計算: {full_recompute})", level="INFO")
            if full_recompute:
                self.fractal_controller.trigger_render(full_recompute=True)
            else:
                self.fractal_controller.trigger_recolor()

        # 要求をリセット
        self._redraw_request['pending'] = False
        self._redraw_request['full_recompute'] = False

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
                widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
                widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1])

                # プラグインから step と decimals を取得、なければデフォルト値
                step_val = p_def.get('step', 1e-7) # より細かいデフォルトステップ
                decimals_val = p_def.get('decimals', 15) # より多くのデフォルト桁数

                widget.setDecimals(decimals_val)   # (1) Decimals を最初に設定
                widget.setSingleStep(step_val)     # (2) SingleStep を次に設定

                current_plugin_val = current_vals.get(name, p_def.get('default'))
                widget.setValue(current_plugin_val if current_plugin_val is not None else 0.0) # (3) 最後に値を設定

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
            if original_value is not None:
                if current_value != original_value:
                    logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: Value changed for {param_name} from {original_value} to {current_value}. Requesting full render.", level="DEBUG")
                    # パラメータは valueChanged で既に設定済み
                    self.request_redraw(full_recompute=True)
                else:
                    logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: Value not changed for {param_name}. Skipping render request.", level="DEBUG")
            else:
                # original_value がない場合は、FocusIn が発生しなかったか、予期せぬ状態。
                # 不要な再描画を防ぐため、警告を出して何もしない。
                logger.log(f"ParameterPanel._on_plugin_parameter_editing_finished: No original value found for {param_name}. Assuming no change and skipping render request.", level="WARNING")

    def _populate_coloring_algorithm_combo(self, target_type: str):
        """
        指定されたターゲットタイプのカラーリングアルゴリズム選択用コンボボックスに、利用可能なアルゴリズム名を設定します。
        Args:
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller: return

        try:
            combo_box = self.coloring_widgets[target_type]['algo_combo']
        except KeyError:
            logger.log(f"Error: Combo box not found for target_type '{target_type}' in _populate_coloring_algorithm_combo", level="ERROR")
            return

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
            # algo が N/A の場合、特定のUIをクリアする可能性があります
            if algo_name == "N/A":
                self._clear_coloring_plugin_specific_ui(target_type)
                try:
                    group_to_hide = self.coloring_widgets[target_type]['specific_group']
                    group_to_hide.setVisible(False)
                except KeyError:
                    logger.log(f"Error: Widgets for target_type '{target_type}' not found in _on_coloring_algorithm_changed.", level="ERROR")
            return

        # Check if this algo is already active for this target type
        if algo_name == self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type):
             logger.log(f"ParameterPanel._on_coloring_algorithm_changed: Algo '{algo_name}' for target '{target_type}' already active. Triggering UI update.", level="DEBUG")
             # アルゴリズム名が両方で同じであっても、ターゲットを切り替えるとUIの更新が必要になる場合があるため、UIを更新します。
             self._update_coloring_plugin_specific_ui(algo_name, target_type)
             return

        self.fractal_controller.set_active_coloring_plugin_and_recolor(plugin_name=algo_name, target_type=target_type)
        # コントローラーは、_update_coloring_plugin_specific_ui に接続されている active_coloring_plugin_ui_needs_update を発行するか、
        # より包括的な更新のために active_coloring_target_and_plugin_changed_externally を発行する必要があります。
        # 直接更新が必要な場合: self._update_coloring_plugin_specific_ui(algo_name, target_type)


    # _on_coloring_target_changed は coloring_target_combo が削除されたため不要。
    # 呼び出し元の self.coloring_target_combo.currentTextChanged.connect(self._on_coloring_target_changed) も削除済み。

    def _clear_coloring_plugin_specific_ui(self, target_type: str):
        """
        指定されたターゲットタイプのカラーリングプラグイン固有のパラメータUI要素をクリアします。
        Args:
            target_type (str): 'divergent' または 'non_divergent'.
        """
        try:
            widgets = self.coloring_widgets[target_type]
            plugin_widgets = widgets['plugin_widgets']
            specific_layout = widgets['specific_layout']
        except KeyError:
            logger.log(f"Error: Widgets for target_type '{target_type}' not found in _clear_coloring_plugin_specific_ui.", level="ERROR")
            return

        plugin_widgets.clear()
        while specific_layout.count():
            item = specific_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    @pyqtSlot(str, str)
    def _update_coloring_plugin_specific_ui(self, algo_name: str, target_type: str):
        """
        指定されたカラーリングアルゴリズムの固有パラメータUIを構築・更新します。
        コントローラーからパラメータ定義、プリセット、現在の値を取得してUIに反映します。

        Args:
            algo_name (str): UIを更新する対象のカラーリングアルゴリズムの名前。
            target_type (str): 対象タイプ ('divergent' or 'non_divergent').
        """
        self._clear_coloring_plugin_specific_ui(target_type) # まず特定のUIをクリアする

        try:
            widgets = self.coloring_widgets[target_type]
            plugin_widgets = widgets['plugin_widgets']
            specific_group = widgets['specific_group']
            specific_layout = widgets['specific_layout']
        except KeyError:
            logger.log(f"Error: Widgets for target_type '{target_type}' not found in _update_coloring_plugin_specific_ui.", level="ERROR")
            return

        if not self.fractal_controller or not algo_name or algo_name == "N/A":
            if specific_group: specific_group.setVisible(False)
            logger.log(f"コントローラーがないか、algo_name または algo_name が N/A です。{target_type} の特定のグループを非表示にしています。", level="DEBUG")
            return

        param_defs = self.fractal_controller.get_coloring_plugin_parameter_definitions_from_engine(algo_name, target_type=target_type)

        if not param_defs:
            if specific_group: specific_group.setVisible(False)
            logger.log(f"'{algo_name}' ({target_type}) の param_defs が見つかりません。特定のグループを非表示にしています。", level="DEBUG")
            return

        if specific_group:
            specific_group.setVisible(True)
            logger.log(f"起動時の {target_type} のカラーリングアルゴリズムを'{algo_name}'に設定。", level="DEBUG")

        target_display_name = "発散部" if target_type == 'divergent' else "非発散部"
        if specific_group: specific_group.setTitle(f"{algo_name} ({target_display_name}) 固有設定")
        current_vals = self.fractal_controller.get_current_coloring_plugin_parameters_from_engine(target_type=target_type)
        logger.log(f"{target_type} 固有のパラメータの現在の値: {current_vals}", level="DEBUG")

        presets = self.fractal_controller.get_plugin_presets(algo_name, target_type=target_type)
        if presets:
            logger.log(f"'{algo_name}' ({target_type}) のプリセットが見つかりました: {list(presets.keys())}", level="DEBUG")
            preset_combo = QComboBox()
            preset_combo.addItem("カスタム")
            for preset_name in presets.keys(): preset_combo.addItem(preset_name)
            preset_combo.currentTextChanged.connect(
                partial(self._on_coloring_preset_selected, plugin_name=algo_name, presets_data=presets.copy(), target_type=target_type)
            )
            if specific_layout: specific_layout.addRow(QLabel("プリセット:"), preset_combo)
            if plugin_widgets: plugin_widgets['_coloring_preset_combo'] = preset_combo
        else:
            logger.log(f"'{algo_name}' のプリセットはありません。", level="DEBUG")

        logger.log(f"'{algo_name}' の param_defs をループ処理中です。定義の数: {len(param_defs) if param_defs else 0}", level="DEBUG")
        for p_def in param_defs:
            name = p_def['name'] # name を先に取得
            lbl_text = p_def.get('label', name)
            p_type = p_def.get('type', 'float')
            default_val = p_def.get('default')
            current_val = current_vals.get(name, default_val)
            widget = None

            logger.log(f"p_defの処理: name='{name}', type='{p_type}', label='{lbl_text}', default='{default_val}', current_val_from_engine='{current_vals.get(name)}', final_val_for_widget='{current_val}'", level="DEBUG")

            if p_type == 'float':
                widget = QDoubleSpinBox()
                widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
                widget.setRange(p_def.get('range',(-1e9,1e9))[0], p_def.get('range',(-1e9,1e9))[1])
                # setValue と setSingleStep/setDecimals の順序をプラグイン固有UIと合わせる
                widget.setDecimals(p_def.get('decimals',2))
                widget.setSingleStep(p_def.get('step',0.01))
                widget.setValue(current_val if current_val is not None else 0.0)
                logger.log(f"'{name}' の QDoubleSpinBox を値 {widget.value()} で作成しました", level="DEBUG")
            elif p_type == 'int':
                widget = QSpinBox()
                widget.setRange(p_def.get('range',(-2**31,2**31-1))[0], p_def.get('range',(-2**31,2**31-1))[1])
                widget.setSingleStep(p_def.get('step',1))
                widget.setValue(current_val if current_val is not None else 0)
                logger.log(f"'{name}' の QSpinBox を値 {widget.value()} で作成しました", level="DEBUG")

            if widget:
                if 'tooltip' in p_def:
                    widget.setToolTip(p_def['tooltip'])

                if specific_layout is not None:
                    specific_layout.addRow(QLabel(lbl_text + ":"), widget)
                # else: # specific_layout is None の場合のログは削除
                    # logger.log(f"CRITICAL ERROR: specific_layout is None for {target_type} when trying to add widget for {name}.", level="CRITICAL")

                plugin_widgets[name] = widget
                # シグナル接続
                if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                    widget.valueChanged.connect(partial(self._on_coloring_plugin_parameter_changed, param_name=name, target_type=target_type))
                    widget.editingFinished.connect(partial(self._on_coloring_plugin_parameter_editing_finished, param_name=name, target_type=target_type))
                    widget.installEventFilter(self)
                # `if plugin_widgets: plugin_widgets[name] = widget` の重複行を削除 (既に上で登録済み)
            else:
                logger.log(f"警告: アルゴリズム '{algo_name}' ({target_type}) のタイプ '{p_type}' のパラメータ '{name}' のウィジェットが作成されませんでした。", level="WARNING")

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

        plugin_widgets = self.coloring_widgets[target_type]['plugin_widgets']

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

        widget = self.coloring_widgets[target_type]['plugin_widgets'].get(param_name)

        if widget and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            # focused_value_store のキーは、eventFilter での設定方法と一致している必要があります
            focus_key = widget # 新しいロジックでは、ウィジェット自体がキーです
            original_value = self._focused_value_store.pop(focus_key, None)
            current_value = widget.value()

            if original_value is not None:
                if current_value != original_value:
                    logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Value changed for {param_name} ({target_type}) from {original_value} to {current_value}. Setting param and requesting recolor.", level="DEBUG")
                    self.fractal_controller.set_coloring_plugin_parameter_and_recolor(param_name, current_value, target_type=target_type, allow_recolor=False)
                    self.request_redraw(full_recompute=False)
                else:
                    logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Value not changed for {param_name} ({target_type}). Skipping.", level="DEBUG")
            else:
                # original_value がない場合は、FocusIn が発生しなかったか、予期せぬ状態。
                # 不要な再描画を防ぐため、警告を出して何もしない。
                logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: No original value for {param_name} ({target_type}). Assuming no change and skipping recolor.", level="WARNING")
        elif widget:
            logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Widget {param_name} ({target_type}) is not a SpinBox/DoubleSpinBox. Type: {type(widget)}. Skipping.", level="WARNING")
        else:
            logger.log(f"ParameterPanel._on_coloring_plugin_parameter_editing_finished: Widget for {param_name} ({target_type}) not found. Skipping.", level="WARNING")

    def _populate_color_pack_combo(self, target_type: str):
        """
        指定されたターゲットタイプのカラーパック選択用コンボボックスに、利用可能なカラーパック名を設定します。
        Args:
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller: return

        combo_box = self.coloring_widgets[target_type]['pack_combo']
        pack_names = self.fractal_controller.get_available_color_pack_names_from_engine() # パックはグローバルであり、target_type に固有ではありません
        active_pack = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type) # アクティブなパックはターゲットごとに設定可能

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

        map_list_widget: QListView = self.coloring_widgets[target_type]['map_list']
        self._populate_color_map_list(pack_name, target_type) # Pass target_type

        model = map_list_widget.model()
        if model and model.rowCount() > 0:
            first_map_index = model.index(0, 0)
            if first_map_index.isValid():
                map_list_widget.setCurrentIndex(first_map_index) # これにより _on_color_map_changed がトリガーされます
                # setCurrentItem が既に選択されている場合にトリガーされない、またはその他の理由でトリガーされない場合は、
                # 状態が矛盾している場合にコントローラーが更新されることを確認してください。
                first_map_item_name = first_map_index.data(Qt.ItemDataRole.DisplayRole)
                if self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type) != first_map_item_name or \
                   self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type) != pack_name:
                     self.fractal_controller.set_active_color_map_and_recolor(pack_name, first_map_item_name, target_type=target_type)

    def _populate_color_map_list(self, pack_name: str | None, target_type: str):
        """
        指定されたカラーパック内のカラーマップをリストウィジェットに表示します。

        Args:
            pack_name (str | None): 表示するカラーマップが含まれるカラーパックの名前。Noneの場合はリストを無効化。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        map_list_widget: QListView = self.coloring_widgets[target_type]['map_list']

        map_list_widget.blockSignals(True)
        # 以前のモデルをクリア
        map_list_widget.setModel(None)

        if not self.fractal_controller or not pack_name:
            map_list_widget.setEnabled(False)
            map_list_widget.blockSignals(False)
            return

        map_names = self.fractal_controller.get_color_map_names_in_pack_from_engine(pack_name) # マップはパック内でグローバルです
        active_map_name = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)
        # Active pack for this target, to ensure we are only setting current item if pack is also correct
        active_pack_for_target = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)

        if map_names:
            map_list_widget.setEnabled(True)
            map_items_data = []
            current_item_index = -1
            for i, name_str in enumerate(map_names):
                map_data = self.fractal_controller.get_color_map_data_from_engine(pack_name, name_str)
                icon = QIcon()
                if map_data:
                    thumbnail = self._create_colormap_thumbnail(map_data)
                    icon = QIcon(thumbnail)

                map_items_data.append({'name': name_str, 'icon': icon})

                if name_str == active_map_name and pack_name == active_pack_for_target:
                    current_item_index = i

            model = ColorMapModel()
            model.populate_data(map_items_data)
            map_list_widget.setModel(model)

            if current_item_index != -1:
                index_to_select = model.index(current_item_index, 0)
                map_list_widget.setCurrentIndex(index_to_select)
        else:
            map_list_widget.setEnabled(False)
        map_list_widget.blockSignals(False)

    @pyqtSlot(QModelIndex, QModelIndex, str) # current, previous, target_type
    def _on_color_map_changed(self, current: QModelIndex, previous: QModelIndex, target_type: str):
        """
        カラーマップリストウィジェットの選択が変更されたときに呼び出されるスロット。
        コントローラーに選択されたカラーマップをアクティブにするよう通知します。

        Args:
            current (QModelIndex): 新しく選択されたモデルインデックス。
            previous (QModelIndex): 以前選択されていたモデルインデックス。
            target_type (str): 'divergent' または 'non_divergent'.
        """
        if not self.fractal_controller or not current.isValid(): return
        map_name = current.data(Qt.ItemDataRole.DisplayRole)

        pack_name = self.coloring_widgets[target_type]['pack_combo'].currentText()

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

        try:
            widgets = self.coloring_widgets[target_type]
            pack_combo = widgets['pack_combo']
            map_list_widget: QListView = widgets['map_list']
        except KeyError:
            logger.log(f"Error: Widgets for target_type '{target_type}' not found in _update_color_selection_from_controller.", level="ERROR")
            return

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
            model = map_list_widget.model()
            if (not model or model.rowCount() == 0) and pack_name and pack_name != "N/A":
                self._populate_color_map_list(pack_name, target_type)

        model = map_list_widget.model()
        if not model:
            logger.log(f"Map list model for '{target_type}' is not available after trying to populate.", level="WARNING")
            pack_combo.blockSignals(False)
            map_list_widget.blockSignals(False)
            return

        found = False
        for i in range(model.rowCount()):
            index = model.index(i, 0)
            item_name = index.data(Qt.ItemDataRole.DisplayRole)
            if item_name == map_name:
                map_list_widget.setCurrentIndex(index)
                found = True
                break
        if not found:
            logger.log(f"Map '{map_name}' not found in list for pack '{pack_name}' ({target_type}).", level="WARNING")

        pack_combo.blockSignals(False)
        map_list_widget.blockSignals(False)

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
                logger.log(f"Value not changed for {widget_object_name}. Skipping render request.", level="DEBUG")
            elif original_value is None:
                # original_value がない場合は、FocusIn が発生しなかったか、予期せぬ状態。
                # 不要な再描画を防ぐため、警告を出して何もしない。
                trigger_render_flag = False
                logger.log(f"No original value for {widget_object_name}. Assuming no change and skipping render request.", level="WARNING")
            else: # Value changed
                trigger_render_flag = True
                logger.log(f"Value changed for {widget_object_name} from {original_value} to {current_value}. Requesting render.", level="DEBUG")

        elif isinstance(sender_widget, QSlider):
            # スライダーが解放されたときは、値が変更されたとみなし、再描画とシグナル発行を行う
            param_changed_for_signal = True
            trigger_render_flag = True
            logger.log(f"Slider released ({widget_object_name}). Assuming value changed and triggering render.", level="DEBUG")

        else:
            # 知らないタイプのウィジェットからの場合 (例えばボタンなど、通常ここには来ないはずだが念のため)
            logger.log(f"Sender is an unexpected widget type: {widget_object_name}. Assuming render is needed.", level="WARNING")
            param_changed_for_signal = True # 不明な場合は通知しておく

        if param_changed_for_signal:
            # 現在は iter_spinbox の値のみをシグナルで送っている。
            # 将来的に他の共通パラメータも扱うようになったら、ここを修正する必要がある。
            iters = self.iter_spinbox.value()
            self.parameters_changed_in_ui_signal.emit(iters)

        if trigger_render_flag:
            if self.fractal_controller:
                logger.log(f"Requesting full render for {widget_object_name}", level="DEBUG")
                self.request_redraw(full_recompute=True)
            else:
                logger.log("fractal_controller is None, cannot request render.", level="WARNING")
        else:
            logger.log(f"Render request skipped for {widget_object_name} as value did not change.", level="DEBUG")

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

            # カラーリングUI
            for target_type in ['divergent', 'non_divergent']:
                widgets = self.coloring_widgets[target_type]
                combo_algo = widgets['algo_combo']
                combo_pack = widgets['pack_combo']
                list_map = widgets['map_list']

                # アルゴリズム
                active_algo = self.fractal_controller.get_active_coloring_plugin_name_from_engine(target_type=target_type)
                if active_algo and active_algo != "N/A":
                    combo_algo.blockSignals(True)
                    combo_algo.setCurrentText(active_algo)
                    combo_algo.blockSignals(False)
                    self._update_coloring_plugin_specific_ui(active_algo, target_type=target_type)
                elif combo_algo.count() > 0:
                    first_algo = combo_algo.itemText(0)
                    if first_algo and first_algo != "N/A":
                        combo_algo.setCurrentText(first_algo) # シグナル経由で更新

                # カラーパックとマップ
                active_pack = self.fractal_controller.get_active_color_pack_name_from_engine(target_type=target_type)
                active_map = self.fractal_controller.get_active_color_map_name_from_engine(target_type=target_type)
                if active_pack and active_map:
                    combo_pack.blockSignals(True)
                    combo_pack.setCurrentText(active_pack)
                    combo_pack.blockSignals(False)
                    self._populate_color_map_list(active_pack, target_type=target_type)
                    model = list_map.model()
                    if model:
                        for i in range(model.rowCount()):
                            if model.index(i, 0).data() == active_map:
                                list_map.setCurrentIndex(model.index(i, 0))
                                break
                elif combo_pack.count() > 0:
                    first_pack = combo_pack.itemText(0)
                    if first_pack and first_pack != "N/A":
                        combo_pack.setCurrentText(first_pack) # シグナル経由で更新

    @pyqtSlot(dict) # 引数として dict を受け取ることを明示
    def update_ui_from_controller_parameters(self, params: dict):
        """
        コントローラーから共通パラメータが外部的に更新された場合にUIを更新するスロット。
        """
        if self.fractal_controller:
            self._set_ui_values(params['max_iterations'])
    def _set_ui_values(self, iterations: int): # 他の共通パラメータも引数に追加する可能性あり
        """UIの共通パラメータ値を設定します。現在は最大反復回数のみを設定します。

        Args:
            iterations (int): 設定する最大反復回数。
        """
        self.iter_spinbox.blockSignals(True)
        self.iter_spinbox.setValue(iterations)
        self.iter_spinbox.blockSignals(False)
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
        logger.log(f"受信 is_rendering = {is_rendering}", level="DEBUG")

        def _update_ui():
            if hasattr(self, 'fractal_combo'):
                logger.log(f"fractal_combo.setEnabled の設定({not is_rendering}) (before). Current state: {self.fractal_combo.isEnabled()}", level="DEBUG")
                self.fractal_combo.setEnabled(not is_rendering)
                logger.log(f"fractal_combo.isEnabled() is now {self.fractal_combo.isEnabled()} (after).", level="DEBUG")
            else:
                logger.log("self.fractal_combo は存在しません。", level="WARNING")

        QTimer.singleShot(0, _update_ui)
        logger.log("_update_ui を QTimer.singleShot でスケジュールしました。", level="DEBUG")

    def eventFilter(self, obj, event):
        """
        QSpinBox と QDoubleSpinBox のフォーカスイベントを監視し、
        フォーカスイン時に値を保存します。
        """
        if isinstance(obj, (QSpinBox, QDoubleSpinBox)):
            if event.type() == QEvent.Type.FocusIn:
                self._focused_value_store[obj] = obj.value()
                logger.log(f"FocusIn on {obj.objectName()}. Stored value: {obj.value()}", level="DEBUG")
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

        logger.log(f"プリセット '{preset_name}' をプラグイン '{plugin_name}' に適用中 (ターゲット: '{target_type}')", level="DEBUG")

        widgets = self.coloring_widgets[target_type]
        plugin_widgets_dict = widgets['plugin_widgets']
        algo_combo = widgets['algo_combo']

        selected_vals = presets_data.get(preset_name)
        if selected_vals:
            current_ui_algo_name = algo_combo.currentText()
            if current_ui_algo_name != plugin_name:
                logger.log(f"プラグイン '{plugin_name}' のプリセット選択ですが、UI は {target_type} 用に '{current_ui_algo_name}' を表示しています。プリセットの適用を中止します。", level="WARNING")
                return

            all_params_set_for_preset = True
            params_to_set_in_controller = {}

            for p_name, val in selected_vals.items():
                widget = plugin_widgets_dict.get(p_name)
                if widget:
                    widget.blockSignals(True) # 即時のフィードバックループを防ぐために、値を設定中はシグナルをブロックします
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.setValue(val)
                        # ユーザーが変更せずにクリックして離れた場合に、元に戻ったり不要なレンダリングがトリガーされたりしないように、
                        # このウィジェットに保存されているフォーカスイン値をクリアします。
                        if widget in self._focused_value_store:
                            del self._focused_value_store[widget]
                    # TODO: 必要であれば他のウィジェットタイプ（例：列挙型用のQComboBox）のサポートを追加

                    widget.blockSignals(False) # シグナルをアンブロック
                    params_to_set_in_controller[p_name] = val # コントローラー用のパラメータを収集
                else:
                    all_params_set_for_preset = False
                    logger.log(f"Widget for preset parameter '{p_name}' not found in {target_type} UI.", level="WARNING")

            # コントローラーのパラメータを更新し、再カラーリングを1回トリガーします。
            if params_to_set_in_controller:
                # 個別に設定し、最後に再カラーリングを1回トリガーします。
                for p_name, val in params_to_set_in_controller.items():
                    # allow_recolor=False でコントローラーに設定
                    self.fractal_controller.set_coloring_plugin_parameter_and_recolor(p_name, val, target_type=target_type, allow_recolor=False)
                self.request_redraw(full_recompute=False) # 最後に再カラーリングを要求

            if not all_params_set_for_preset:
                 logger.log(f"Not all parameters from preset '{preset_name}' were applied to the UI for {target_type}.", level="WARNING")

    @pyqtSlot(str, str) # preset_name 引数を削除
    def update_active_coloring_target_and_plugin_from_controller(self, target_type: str, plugin_name: str): # preset_name 引数を削除
        """
        コントローラーからの指示でアクティブなカラーリングターゲットとプラグインを更新します。
        """
        logger.log(f"ParameterPanel.update_active_coloring_target_and_plugin_from_controller: target='{target_type}', plugin='{plugin_name}'", level="DEBUG") # preset_name をログから削除

        try:
            algo_combo = self.coloring_widgets[target_type]['algo_combo']
        except KeyError:
            logger.log(f"Error: Widgets for target_type '{target_type}' not found in update_active_coloring_target_and_plugin_from_controller.", level="ERROR")
            return

        # 1. アルゴリズムコンボボックスの選択を更新
        algo_combo.blockSignals(True)
        current_algo_text = algo_combo.currentText()
        if current_algo_text != plugin_name:
            items = [algo_combo.itemText(i) for i in range(algo_combo.count())]
            if plugin_name not in items:
                logger.log(f"Plugin '{plugin_name}' not found in combo for {target_type}, re-populating.", level="INFO")
                self._populate_coloring_algorithm_combo(target_type)
            algo_combo.setCurrentText(plugin_name)
        algo_combo.blockSignals(False)

        # 2. 新しいアルゴリズム用にプラグイン固有のUIを更新
        self._update_coloring_plugin_specific_ui(plugin_name, target_type)


if __name__ == '__main__':
    pass
