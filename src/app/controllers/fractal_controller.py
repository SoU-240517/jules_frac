import time
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, pyqtSlot
# Assuming FractalEngine is correctly typed if imported, but not strictly necessary for this file if only passed.
# from src.app.models.fractal_engine import FractalEngine
from src.app.export.image_exporter import ImageExporter # ExporterSignals is used by ImageExporter internally

class FractalController(QObject):
    image_rendered = pyqtSignal(object)
    status_updated = pyqtSignal(str)
    parameters_updated_externally = pyqtSignal()
    active_fractal_plugin_ui_needs_update = pyqtSignal(str)
    active_coloring_plugin_ui_needs_update = pyqtSignal(str)
    active_color_map_changed_externally = pyqtSignal(str, str)

    # Signals for high-resolution export process
    export_started = pyqtSignal()
    export_progress_updated = pyqtSignal(int)
    export_process_finished = pyqtSignal(bool, str) # bool: success, str: message (filepath or error)

    def __init__(self, fractal_engine):
        super().__init__()
        self.fractal_engine = fractal_engine
        self.main_window = None
        self.last_compute_time_ms = 0.0
        self.last_coloring_time_ms = 0.0
        self.initial_width = self.fractal_engine.width if self.fractal_engine else 3.0

        self.current_exporter: ImageExporter | None = None
        self.thread_pool = QThreadPool.globalInstance()
        # Optional: Limit concurrent exports if desired, e.g., self.thread_pool.setMaxThreadCount(1)

    def set_main_window(self, main_window):
        self.main_window = main_window
        self.update_status_display()

    # --- Common Fractal Parameter Handling ---
    def update_common_fractal_parameters(self, center_real, center_imag, width, max_iterations, escape_radius=None):
        if self.fractal_engine:
            self.fractal_engine.set_common_parameters(center_real, center_imag, width, max_iterations, escape_radius)
            self.fractal_engine.last_fractal_data_cache = None
        self.update_status_display()

    def get_current_common_parameters(self):
        return self.fractal_engine.get_common_parameters() if self.fractal_engine else {}

    def get_current_engine_parameters(self):
        return self.fractal_engine.get_common_parameters() if self.fractal_engine else {}

    # --- Fractal Plugin Management ---
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

    # --- Rendering ---
    def trigger_render(self, image_width_px=None, image_height_px=None, full_recompute:bool = True):
        if not self.fractal_engine: self.status_updated.emit("エラー: フラクタルエンジン未設定"); return
        active_fp_name = self.get_active_fractal_plugin_name_from_engine() or "N/A"
        active_cp_name = self.get_active_coloring_plugin_name_from_engine() or "N/A"
        self.status_updated.emit(f"処理中 ({active_fp_name} / {active_cp_name})...")
        if image_width_px is not None: self.fractal_engine.image_width_px = image_width_px
        if image_height_px is not None: self.fractal_engine.image_height_px = image_height_px
        if image_width_px is not None or image_height_px is not None : self.fractal_engine.update_aspect_ratio()
        if self.fractal_engine.image_width_px <= 0 or self.fractal_engine.image_height_px <= 0:
            self.status_updated.emit("エラー: 画像サイズ不正"); return
        fractal_data = None
        if full_recompute:
            start_t = time.perf_counter()
            fractal_data = self.fractal_engine.compute_current_fractal()
            self.last_compute_time_ms = (time.perf_counter() - start_t) * 1000
            if fractal_data is None: self.status_updated.emit("エラー: 計算失敗"); return
        else:
            fractal_data = self.fractal_engine.last_fractal_data_cache
            if fractal_data is None: self.status_updated.emit("エラー: キャッシュデータなし"); self.trigger_render(full_recompute=True); return # No cache, do full render
            self.last_compute_time_ms = 0.0
        start_t = time.perf_counter()
        colored_image = self.fractal_engine.apply_coloring(fractal_data_override=fractal_data)
        self.last_coloring_time_ms = (time.perf_counter() - start_t) * 1000
        if colored_image is None: self.status_updated.emit("エラー: カラーリング失敗"); return
        self.image_rendered.emit(colored_image); self.update_status_display()

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

    # --- High-Resolution Export ---
    def start_high_res_export(self, export_settings: dict):
        if self.current_exporter is not None:
            self.export_process_finished.emit(False, "既にエクスポート処理が実行中です。")
            return
        if not self.fractal_engine:
            self.export_process_finished.emit(False, "FractalEngineが初期化されていません。")
            return

        print(f"FractalController: 高解像度エクスポートを開始します。設定: {export_settings}")
        exporter = ImageExporter(self.fractal_engine, export_settings)
        self.current_exporter = exporter

        exporter.signals.progress_updated.connect(self.export_progress_updated)
        exporter.signals.export_finished.connect(self._on_export_actually_finished)

        self.export_started.emit()
        self.thread_pool.start(exporter)

    @pyqtSlot(bool, str)
    def _on_export_actually_finished(self, success: bool, message: str):
        print(f"FractalController: エクスポート処理完了。成功: {success}, メッセージ: {message}")
        self.export_process_finished.emit(success, message)
        if self.current_exporter:
            try: # Attempt to disconnect, ignore if already disconnected (e.g. by exporter itself)
                self.current_exporter.signals.progress_updated.disconnect(self.export_progress_updated)
                self.current_exporter.signals.export_finished.disconnect(self._on_export_actually_finished)
            except TypeError: pass # Raised if a signal is not connected, or connected multiple times and one disconnect fails
            self.current_exporter = None
        print("FractalController: エクスポータ参照クリア。")

    def cancel_current_export(self):
        if self.current_exporter:
            print("FractalController: 現在のエクスポート処理のキャンセルを要求。")
            self.current_exporter.cancel()
        else:
            print("FractalController: キャンセル対象のエクスポート処理なし。")

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
    class MockFractalEngine: # Simplified further for brevity
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
    print("\nController test with full mock engine..."); controller.update_common_fractal_parameters(-0.7,0.3,2.0,150)
    controller.trigger_render(); controller.trigger_recolor()
    # print(f"Status: {controller.last_status}") # Accessing last_status for print might be tricky if not stored on controller
    controller.start_high_res_export({'width':200,'height':150,'iterations':300,'antialiasing_factor':2, 'antialiasing': '2x2 SSAA'}) # Added antialiasing string for generate_image_for_output
    print("Controller test finished.")
