import time
from export.image_exporter import ImageExporter # ExporterSignals は ImageExporter 内部で使用されます
# FractalEngine がインポートされている場合、型が正しく指定されていると仮定しますが、このファイルでは渡されるだけなので必須ではありません。
# from src.app.models.fractal_engine import FractalEngine # FractalEngineモデルのインポート (型ヒント用)
from .fractal_renderer import FractalRenderer
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, pyqtSlot
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class FractalController(QObject):
    image_rendered = pyqtSignal(object)
    status_updated = pyqtSignal(str)
    parameters_updated_externally = pyqtSignal()
    active_fractal_plugin_ui_needs_update = pyqtSignal(str)
    active_coloring_plugin_ui_needs_update = pyqtSignal(str)
    active_color_map_changed_externally = pyqtSignal(str, str)
    rendering_task_started = pyqtSignal() # New signal

    # 高解像度エクスポート処理用のシグナル
    export_started = pyqtSignal()
    export_progress_updated = pyqtSignal(int)
    export_process_finished = pyqtSignal(bool, str) # bool: 成功フラグ, str: メッセージ (ファイルパスまたはエラー)

    def __init__(self, fractal_engine):
        super().__init__()
        self.fractal_engine = fractal_engine
        self.main_window = None
        self.last_compute_time_ms = 0.0
        self.last_coloring_time_ms = 0.0
        self.initial_width = self.fractal_engine.width if self.fractal_engine else 3.0
        self.logger = CustomLogger() # Add logger instance

        self.current_exporter: ImageExporter | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.current_renderer_task: FractalRenderer | None = None
        # オプション: 必要に応じて同時エクスポート数を制限します。例: self.thread_pool.setMaxThreadCount(1)

    def set_main_window(self, main_window):
        self.main_window = main_window
        self.update_status_display()

    # --- フラクタル共通パラメータ処理 ---
    def update_common_fractal_parameters(self, center_real, center_imag, width, max_iterations, escape_radius=None):
        if self.fractal_engine:
            self.fractal_engine.set_common_parameters(center_real, center_imag, width, max_iterations, escape_radius)
            self.fractal_engine.last_fractal_data_cache = None
        self.update_status_display()

    def get_current_common_parameters(self):
        return self.fractal_engine.get_common_parameters() if self.fractal_engine else {}

    def get_current_engine_parameters(self):
        return self.fractal_engine.get_common_parameters() if self.fractal_engine else {}

    # --- フラクタルプラグイン管理 ---
    def get_available_fractal_plugin_names_from_engine(self) -> list[str]:
        return self.fractal_engine.get_available_fractal_plugin_names() if self.fractal_engine else []

    def get_active_fractal_plugin_name_from_engine(self) -> str | None:
        if self.fractal_engine and self.fractal_engine.get_active_fractal_plugin():
            return self.fractal_engine.get_active_fractal_plugin().name
        return None

    def get_fractal_plugin_parameter_definitions_from_engine(self, plugin_name: str) -> list:
        if self.fractal_engine:
            plugin = self.fractal_engine.plugin_manager.get_fractal_plugin(plugin_name)
            if plugin: return plugin.get_parameters_definition()
        return []

    def get_current_fractal_plugin_parameters_from_engine(self) -> dict:
        return self.fractal_engine.get_fractal_plugin_parameters() if self.fractal_engine else {}

    def set_fractal_plugin_parameter(self, param_name: str, value: any):
        if self.fractal_engine:
            self.fractal_engine.set_fractal_plugin_parameter(param_name, value)
            self.update_status_display()

    def set_fractal_plugin_parameter_and_update(self, param_name: str, value: any):
        """
        フラクタルプラグインの特定のパラメータを設定し、フラクタルを再計算・再描画します。
        UIからのパラメータ変更時に使用されることを想定しています。
        """
        if self.fractal_engine:
            # 1. エンジンにパラメータを設定
            self.fractal_engine.set_fractal_plugin_parameter(param_name, value)

            # 2. パラメータが外部から変更されたことを通知 (設定保存や他のUI要素の更新のため)
            self.parameters_updated_externally.emit()

            # 3. アクティブなフラクタルプラグインのUIが更新を必要とするかもしれないことを通知
            active_plugin_name = self.get_active_fractal_plugin_name_from_engine()
            if active_plugin_name:
                self.active_fractal_plugin_ui_needs_update.emit(active_plugin_name)

            # 4. 完全な再計算と再描画をトリガー
            self.trigger_render(full_recompute=True)
            # trigger_render内でupdate_status_displayが呼ばれるため、ここでは不要

    def set_active_fractal_plugin_and_redraw(self, plugin_name: str):
        if not self.fractal_engine: return
        success = self.fractal_engine.set_active_fractal_plugin(plugin_name)
        if success:
            self.parameters_updated_externally.emit()
            self.active_fractal_plugin_ui_needs_update.emit(plugin_name)
            self.trigger_render(full_recompute=True)
        else:
            self.active_fractal_plugin_ui_needs_update.emit("")

    # --- Coloring Plugin and Map Management (略 - 変更なし) ---
    def get_available_coloring_plugin_names_from_engine(self) -> list[str]:
        return self.fractal_engine.get_available_coloring_plugin_names() if self.fractal_engine else []
    def get_active_coloring_plugin_name_from_engine(self) -> str | None:
        if self.fractal_engine and self.fractal_engine.get_active_coloring_plugin(): return self.fractal_engine.get_active_coloring_plugin().name
        return None
    def get_coloring_plugin_parameter_definitions_from_engine(self, plugin_name: str) -> list:
        if self.fractal_engine:
            plugin = self.fractal_engine.plugin_manager.get_coloring_plugin(plugin_name)
            if plugin: return plugin.get_parameters_definition()
        return []

    def get_plugin_presets(self, plugin_name: str) -> list:
        """
        指定されたカラーリングプラグインのプリセットを取得します。
        FractalEngineのPluginManagerに処理を委譲します。
        """
        if self.fractal_engine and hasattr(self.fractal_engine, 'plugin_manager'):
            # plugin_nameがカラーリングプラグイン用であると想定
            plugin = self.fractal_engine.plugin_manager.get_coloring_plugin(plugin_name)
            if plugin and hasattr(plugin, 'get_presets'):
                try:
                    return plugin.get_presets()
                except Exception as e:
                    logger.log(f"プラグイン '{plugin_name}' のプリセット取得中にエラー: {e}", level="WARNING")
                    return []
        return []

    def get_current_coloring_plugin_parameters_from_engine(self) -> dict:
        return self.fractal_engine.get_coloring_plugin_parameters() if self.fractal_engine else {}
    def set_active_coloring_plugin_and_recolor(self, plugin_name: str):
        if not self.fractal_engine: return
        success = self.fractal_engine.set_active_coloring_plugin(plugin_name)
        if success: self.active_coloring_plugin_ui_needs_update.emit(plugin_name); self.trigger_recolor()
        else: self.active_coloring_plugin_ui_needs_update.emit("")
    def set_coloring_plugin_parameter_and_recolor(self, param_name: str, value: any):
        if self.fractal_engine:
            self.fractal_engine.set_coloring_plugin_parameter(param_name, value)
            self.update_status_display(); self.trigger_recolor()
    def get_available_color_pack_names_from_engine(self) -> list[str]:
        return self.fractal_engine.get_available_color_pack_names() if self.fractal_engine else []
    def get_active_color_pack_name_from_engine(self) -> str | None:
        if self.fractal_engine: return self.fractal_engine.get_current_color_map_selection()[0]
        return None
    def get_color_map_names_in_pack_from_engine(self, pack_name: str) -> list[str]:
        return self.fractal_engine.get_available_color_map_names_in_pack(pack_name) if self.fractal_engine else []
    def get_active_color_map_name_from_engine(self) -> str | None:
        if self.fractal_engine: return self.fractal_engine.get_current_color_map_selection()[1]
        return None
    def get_color_map_data_from_engine(self, pack_name: str, map_name: str) -> list[tuple[int,int,int]] | None:
        if self.fractal_engine: return self.fractal_engine.color_manager.get_color_map_data(pack_name, map_name)
        return None
    def set_active_color_map_and_recolor(self, pack_name: str, map_name: str):
        if not self.fractal_engine: return
        success = self.fractal_engine.set_active_color_map(pack_name, map_name)
        if success: self.active_color_map_changed_externally.emit(pack_name, map_name); self.trigger_recolor()

    # --- レンダリング処理 ---
    def trigger_render(self, image_width_px=None, image_height_px=None, full_recompute: bool = True):
        if not self.fractal_engine:
            self.status_updated.emit("エラー: フラクタルエンジン未設定")
            return

        if self.current_renderer_task is not None and not self.thread_pool.waitForDone(10): # Check active task with timeout
            self.logger.log("FractalController: Previous rendering task still active. Not starting a new one.", level="WARNING") # Uses self.logger
            self.status_updated.emit("前の描画処理がまだ実行中です。")
            return

        self.status_updated.emit(f"描画準備中...") # Initial brief message

        render_width = image_width_px if image_width_px is not None else self.fractal_engine.image_width_px
        render_height = image_height_px if image_height_px is not None else self.fractal_engine.image_height_px

        if render_width <= 0 or render_height <= 0:
            self.status_updated.emit("エラー: 画像サイズ不正")
            self.logger.log(f"FractalController: Invalid image size for render: {render_width}x{render_height}", level="ERROR") # Uses self.logger
            return

        self.current_renderer_task = FractalRenderer(
            self.fractal_engine,
            render_width,
            render_height,
            full_recompute
        )

        self.current_renderer_task.signals.rendering_started.connect(self._on_renderer_started)
        self.current_renderer_task.signals.rendering_finished.connect(self._on_renderer_finished)
        self.current_renderer_task.signals.rendering_failed.connect(self._on_renderer_failed)

        self.thread_pool.start(self.current_renderer_task)
        self.logger.log(f"FractalController: Queued FractalRenderer for {render_width}x{render_height}, full_recompute={full_recompute}", level="INFO") # Uses self.logger

    @pyqtSlot()
    def _on_renderer_started(self):
        self.logger.log("FractalController: Renderer task started signal received.", level="DEBUG") # Uses self.logger
        self.rendering_task_started.emit()

    @pyqtSlot(object, float, float)
    def _on_renderer_finished(self, colored_image, compute_time_ms, coloring_time_ms):
        self.logger.log(f"FractalController: Renderer task finished. Compute: {compute_time_ms:.1f}ms, Color: {coloring_time_ms:.1f}ms", level="INFO") # Uses self.logger
        self.last_compute_time_ms = compute_time_ms
        self.last_coloring_time_ms = coloring_time_ms
        self.image_rendered.emit(colored_image)
        self.update_status_display() # Generate and emit final status message
        self.current_renderer_task = None

    @pyqtSlot(str)
    def _on_renderer_failed(self, error_message):
        self.logger.log(f"FractalController: Renderer task failed: {error_message}", level="ERROR") # Uses self.logger
        self.status_updated.emit(f"描画エラー: {error_message}")
        self.current_renderer_task = None

    def trigger_recolor(self):
        self.trigger_render(full_recompute=False)

    def update_status_display(self):
        # ... (実装は前回のまま、変更なし) ...
        if not self.fractal_engine: self.status_updated.emit("フラクタルエンジン未準備."); return
        active_fp = self.fractal_engine.get_active_fractal_plugin()
        active_cp = self.fractal_engine.get_active_coloring_plugin()
        cpk_name, cm_name = self.fractal_engine.get_current_color_map_selection()
        if not active_fp or not active_cp: self.status_updated.emit("プラグイン未設定."); return
        common_p = self.fractal_engine.get_common_parameters()
        fp_p = self.fractal_engine.get_fractal_plugin_parameters()
        cp_p = self.fractal_engine.get_coloring_plugin_parameters()
        w = common_p.get('width', self.initial_width); zoom = self.initial_width/w if w>0 else 0
        status = [f"F: {active_fp.name}", f"C: {active_cp.name} ({cpk_name}/{cm_name})"]
        status.append(f"中心:({common_p.get('center_real',0):.3f},{common_p.get('center_imag',0):.3f})")
        status.append(f"幅:{w:.2e}({zoom:.1f}x) Iter:{common_p.get('max_iterations',0)}")
        if fp_p: status.append(f"FP:[{', '.join([f'{k}:{v:.3f}' if isinstance(v,float) else f'{k}:{v}' for k,v in fp_p.items()])}]")
        if cp_p: status.append(f"CP:[{', '.join([f'{k}:{v:.3f}' if isinstance(v,float) else f'{k}:{v}' for k,v in cp_p.items()])}]")
        status.append(f"{self.fractal_engine.image_width_px}x{self.fractal_engine.image_height_px}px")
        if self.last_compute_time_ms > 0 : status.append(f"Calc:{self.last_compute_time_ms:.1f}ms")
        status.append(f"Color:{self.last_coloring_time_ms:.1f}ms")
        self.status_updated.emit(" | ".join(status))

    # --- Pan and Zoom (略 - 変更なし) ---
    def pan_fractal(self, dr, di):
        cp = self.get_current_engine_parameters(); nc_r=cp['center_real']-dr; nc_i=cp['center_imag']-di
        self.update_common_fractal_parameters(nc_r, nc_i, cp['width'], cp['max_iterations'])
        self.parameters_updated_externally.emit(); self.trigger_render(full_recompute=True)
    def zoom_fractal_to_point(self, fix_r, fix_i, mfx, mfy, new_w):
        if not self.fractal_engine or self.fractal_engine.image_width_px == 0: return
        asp = self.fractal_engine.image_height_px / self.fractal_engine.image_width_px; new_h = new_w*asp
        nc_r = fix_r-(mfx-0.5)*new_w; nc_i = fix_i+(mfy-0.5)*new_h
        self.update_common_fractal_parameters(nc_r, nc_i, new_w, self.fractal_engine.max_iterations)
        self.parameters_updated_externally.emit(); self.trigger_render(full_recompute=True)

    # --- 高解像度エクスポート ---
    def start_high_res_export(self, export_settings: dict):
        if self.current_exporter is not None:
            self.export_process_finished.emit(False, "既にエクスポート処理が実行中です。")
            return
        if not self.fractal_engine:
            self.export_process_finished.emit(False, "FractalEngineが初期化されていません。")
            return

        logger.log(f"高解像度エクスポートを開始します。設定: {export_settings}", level="INFO")
        exporter = ImageExporter(self.fractal_engine, export_settings)
        self.current_exporter = exporter

        exporter.signals.progress_updated.connect(self.export_progress_updated)
        exporter.signals.export_finished.connect(self._on_export_actually_finished)

        self.export_started.emit()
        self.thread_pool.start(exporter)

    @pyqtSlot(bool, str)
    def _on_export_actually_finished(self, success: bool, message: str):
        logger.log(f"エクスポート処理完了。成功: {success}, メッセージ: {message}", level="INFO")
        self.export_process_finished.emit(success, message)
        if self.current_exporter:
            try: # 切断を試み、既に切断されている場合（例：エクスポータ自体による切断）は無視します
                self.current_exporter.signals.progress_updated.disconnect(self.export_progress_updated)
                self.current_exporter.signals.export_finished.disconnect(self._on_export_actually_finished)
            except TypeError: pass # シグナルが接続されていない場合、または複数回接続されていていずれかの切断に失敗した場合に発生します
            self.current_exporter = None
        logger.log("エクスポータ参照クリア。", level="INFO")

    def cancel_current_export(self):
        if self.current_exporter:
            logger.log("現在のエクスポート処理のキャンセルを要求。", level="INFO")
            self.current_exporter.cancel()
        else:
            logger.log("キャンセル対象のエクスポート処理なし。", level="INFO")

    # Programmatic parameter changes (略 - 変更なし)
    def handle_programmatic_parameter_change(self, cr, ci, w, iters=None, plugin_params=None):
        if not self.fractal_engine: return
        current_iters = self.fractal_engine.max_iterations if iters is None else iters
        self.update_common_fractal_parameters(cr, ci, w, current_iters)
        if plugin_params and self.fractal_engine.get_active_fractal_plugin():
            for name, value in plugin_params.items(): self.set_fractal_plugin_parameter(name, value)
        self.parameters_updated_externally.emit()
        if plugin_params and self.fractal_engine.get_active_fractal_plugin():
             self.active_fractal_plugin_ui_needs_update.emit(self.fractal_engine.get_active_fractal_plugin().name)
        self.trigger_render(full_recompute=True)

if __name__ == '__main__':
    # ... (Mock classes and test code - 変更なし) ...
    class MockFractalEngine: # 簡潔にするためにさらに簡略化
        def __init__(self): self.width=3.0;self.center_real=-0.5;self.center_imag=0.0;self.max_iterations=50;self.escape_radius=2.0;self.image_width_px=100;self.image_height_px=75;self.height=2.625;self.last_fractal_data_cache=None;self.plugin_manager=type('MPM',(),{'get_fractal_plugin':lambda n:type('MFP',(),{'name':n,'get_parameters_definition':lambda:[],'get_default_view_parameters':lambda:{}})(), 'get_coloring_plugin':lambda n:type('MCP',(),{'name':n,'get_parameters_definition':lambda:[]})()})();self.current_fractal_plugin=self.plugin_manager.get_fractal_plugin("TestFP");self.current_coloring_plugin=self.plugin_manager.get_coloring_plugin("TestCP");self.current_fractal_plugin_parameters={};self.current_coloring_plugin_parameters={};self.current_color_pack_name="P1";self.current_color_map_name="M1";self.color_manager=type('MCM',(),{'get_color_map_data':lambda pn,mn:[(0,0,0)]})()
        def get_common_parameters(self): return {'width':self.width,'center_real':self.center_real,'center_imag':self.center_imag,'max_iterations':self.max_iterations,'height':self.height,'escape_radius':self.escape_radius}
        def set_common_parameters(self,cr,ci,w,mi,er=None): self.center_real=cr;self.center_imag=ci;self.width=w;self.max_iterations=mi;self.last_fractal_data_cache=None; self.update_aspect_ratio()
        def get_active_fractal_plugin(self): return self.current_fractal_plugin;
        def get_active_coloring_plugin(self): return self.current_coloring_plugin
        def get_fractal_plugin_parameters(self): return self.current_fractal_plugin_parameters;
        def get_coloring_plugin_parameters(self): return self.current_coloring_plugin_parameters
        def get_current_color_map_selection(self): return (self.current_color_pack_name,self.current_color_map_name)
        def update_image_size(self,w,h): self.image_width_px=w;self.image_height_px=h;self.update_aspect_ratio()
        def update_aspect_ratio(self): self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width
        def compute_current_fractal(self): import numpy as np; self.last_fractal_data_cache={'iterations':np.zeros((self.image_height_px,self.image_width_px))}; return self.last_fractal_data_cache
        def apply_coloring(self,fractal_data_override=None): import numpy as np; data=fractal_data_override or self.last_fractal_data_cache; return np.zeros((data['iterations'].shape[0],data['iterations'].shape[1],4),dtype=np.uint8) if data and 'iterations' in data else np.zeros((1,1,4),dtype=np.uint8)
        def set_active_fractal_plugin(self,name):fp=self.plugin_manager.get_fractal_plugin(name);self.current_fractal_plugin=fp if fp else self.current_fractal_plugin;self.last_fractal_data_cache=None;return True
        def set_active_coloring_plugin(self,name):cp=self.plugin_manager.get_coloring_plugin(name);self.current_coloring_plugin=cp if cp else self.current_coloring_plugin;return True
        def set_active_color_map(self,p,m):self.current_color_pack_name=p;self.current_color_map_name=m;return True
        def get_available_fractal_plugin_names(self):
            return ["TestFP"]
        def get_available_coloring_plugin_names(self):
            return ["TestCP"]
        def get_available_color_pack_names(self):
            return ["P1"]
        def get_available_color_map_names_in_pack(self, p):
            return ["M1"]
        def set_fractal_plugin_parameter(self,n,v): self.current_fractal_plugin_parameters[n]=v; self.last_fractal_data_cache=None
        def set_coloring_plugin_parameter(self,n,v): self.current_coloring_plugin_parameters[n]=v
        def generate_image_for_output(self, **kwargs): import numpy as np; return np.zeros((kwargs['output_height'],kwargs['output_width'],4),dtype=np.uint8)
    class MockMainWindow: render_area = type('MRA',(),{'width':lambda:100, 'height':lambda:100})()
    mock_engine = MockFractalEngine(); controller = FractalController(mock_engine); controller.set_main_window(MockMainWindow())
    logger.log("\nコントローラーテスト（フルモックエンジン使用）...", level="INFO"); controller.update_common_fractal_parameters(-0.7,0.3,2.0,150)
    controller.trigger_render(); controller.trigger_recolor()
    # logger.log(f"ステータス: {controller.last_status}") # controllerにlast_statusが保存されていない場合、printでのアクセスは難しいかもしれません
    controller.start_high_res_export({'width':200,'height':150,'iterations':300,'antialiasing_factor':2, 'antialiasing': '2x2 SSAA'}) # generate_image_for_output 用にアンチエイリアス文字列を追加
    logger.log("コントローラーテスト終了。", level="INFO")
