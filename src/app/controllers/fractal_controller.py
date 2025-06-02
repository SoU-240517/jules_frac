from PyQt6.QtCore import QObject, pyqtSignal
# Import for type hinting, will be commented out if it causes issues in this environment
# from src.app.models.fractal_engine import FractalEngine
# from src.app.views.main_window import MainWindow


class FractalController(QObject):
    image_rendered = pyqtSignal(object)  # For the raw escape time data (NumPy array)
    # colored_image_rendered = pyqtSignal(object) # For QImage or Pixmap after coloring
    status_updated = pyqtSignal(str) # For status bar display

    def __init__(self, fractal_engine): # fractal_engine: FractalEngine
        super().__init__()
        self.fractal_engine = fractal_engine
        self.main_window = None # main_window: MainWindow

    def set_main_window(self, main_window): # main_window: MainWindow
        self.main_window = main_window
        # Connect signals from UI components to controller slots here if necessary
        # e.g., self.main_window.parameter_panel.parameters_changed.connect(self.update_fractal_parameters)
        self.update_status_display() # Initial status update

    def update_fractal_parameters(self, center_real, center_imag, width, max_iterations):
        """Called from UI when fractal parameters change."""
        print(f"Controller: Updating fractal parameters to (real={center_real}, imag={center_imag}), width={width}, iter={max_iterations}")
        self.fractal_engine.set_parameters(center_real, center_imag, width, max_iterations)
        self.update_status_display()
        # Optionally, trigger a re-render immediately after parameter changes
        # self.trigger_render() # This might be too aggressive for some parameters.

    def trigger_render(self, image_width_px=None, image_height_px=None):
        """Initiates the fractal computation and emits the result via image_rendered signal."""
        if self.fractal_engine is None:
            self.status_updated.emit("Error: Fractal Engine not initialized.")
            return

        if image_width_px is not None and image_height_px is not None:
             self.fractal_engine.update_image_size(image_width_px, image_height_px)

        # Ensure image dimensions are set if not provided (e.g., from RenderArea size)
        if self.fractal_engine.image_width_px <= 0 or self.fractal_engine.image_height_px <= 0:
            if self.main_window and hasattr(self.main_window, 'render_area'):
                # Fallback to RenderArea's current size if available
                current_render_area_width = self.main_window.render_area.width()
                current_render_area_height = self.main_window.render_area.height()
                if current_render_area_width > 0 and current_render_area_height > 0:
                    self.fractal_engine.update_image_size(current_render_area_width, current_render_area_height)
                else:
                    self.status_updated.emit("Error: Invalid image dimensions for rendering.")
                    return
            else: # Default if no main_window or render_area info
                self.fractal_engine.update_image_size(800, 600) # Default size
                self.status_updated.emit("Warning: Rendering with default image size (800x600).")


        print(f"Controller: Triggering render for {self.fractal_engine.image_width_px}x{self.fractal_engine.image_height_px}...")
        self.status_updated.emit("Rendering...")

        # Actual computation
        escape_time_data = self.fractal_engine.compute_mandelbrot()

        # Emit the raw escape time data. Coloring will be handled by another component or RenderArea.
        self.image_rendered.emit(escape_time_data)
        print("Controller: Render complete. image_rendered signal emitted with escape time data.")
        self.status_updated.emit("Render complete.") # Or provide more detailed status
        self.update_status_display() # Show current fractal parameters

    def update_status_display(self):
        """Updates the status bar text with current fractal parameters."""
        if self.fractal_engine:
            status_text = (
                f"Center: ({self.fractal_engine.center_real:.4f}, {self.fractal_engine.center_imag:.4f}), "
                f"Width: {self.fractal_engine.width:.4e}, "
                f"Height: {self.fractal_engine.height:.4e}, "
                f"Iterations: {self.fractal_engine.max_iterations}, "
                f"View: {self.fractal_engine.image_width_px}x{self.fractal_engine.image_height_px}px"
            )
            self.status_updated.emit(status_text)

    def get_current_parameters(self):
        """Returns a dictionary of the current fractal parameters from the engine."""
        if self.fractal_engine:
            return {
                "center_real": self.fractal_engine.center_real,
                "center_imag": self.fractal_engine.center_imag,
                "width": self.fractal_engine.width,
                "max_iterations": self.fractal_engine.max_iterations,
                "image_width_px": self.fractal_engine.image_width_px,
                "image_height_px": self.fractal_engine.image_height_px
            }
        return {}

if __name__ == '__main__':
    # Mock classes for testing
    class MockFractalEngine:
        def __init__(self):
            self.max_iterations = 50
            self.center_real = -0.6
            self.center_imag = 0.0
            self.width = 3.5
            self.image_width_px = 100 # Default small size for test
            self.image_height_px = 75  # Default small size for test
            self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width
            print(f"MockEngine initialized: {self.image_width_px}x{self.image_height_px}, height={self.height}")


        def set_parameters(self, cr, ci, w, mi=None):
            self.center_real, self.center_imag, self.width = cr, ci, w
            if mi is not None: self.max_iterations = mi
            if self.image_width_px > 0:
                self.height = (self.width * self.image_height_px) / self.image_width_px
            print(f"MockEngine: Params set - CR={cr}, CI={ci}, W={w}, MI={self.max_iterations}, H={self.height}")

        def compute_mandelbrot(self):
            print(f"MockEngine: compute_mandelbrot called for {self.image_width_px}x{self.image_height_px}")
            import numpy
            return numpy.zeros((self.image_height_px, self.image_width_px), dtype=numpy.int32)

        def update_image_size(self, w_px, h_px):
            self.image_width_px = w_px
            self.image_height_px = h_px
            if self.image_width_px > 0:
                self.height = (self.width * self.image_height_px) / self.image_width_px
            print(f"MockEngine: Image size updated to {w_px}x{h_px}, new height {self.height}")

    class MockMainWindow:
        def __init__(self):
            # Mock RenderArea with a size
            class MockRenderArea:
                def width(self): return 600
                def height(self): return 400
            self.render_area = MockRenderArea()
            print("MockMainWindow initialized with MockRenderArea (600x400)")

    # Test setup
    mock_engine = MockFractalEngine()
    controller = FractalController(mock_engine)
    mock_main_win = MockMainWindow()
    controller.set_main_window(mock_main_win) # Set mock main window

    rendered_data_shape = None
    last_status = ""

    def handle_image_rendered(data):
        nonlocal rendered_data_shape
        rendered_data_shape = data.shape
        print(f"Test: Image rendered signal received, data shape: {rendered_data_shape}")

    def handle_status_update(status):
        nonlocal last_status
        last_status = status
        print(f"Test: Status update: {last_status}")

    controller.image_rendered.connect(handle_image_rendered)
    controller.status_updated.connect(handle_status_update)

    print("\nTesting parameter update...")
    controller.update_fractal_parameters(-0.7, 0.3, 2.0, 150)
    assert controller.get_current_parameters()["width"] == 2.0
    assert "Width: 2.0000e+00" in last_status

    print("\nTesting render trigger with specific size...")
    controller.trigger_render(image_width_px=200, image_height_px=150)
    assert rendered_data_shape == (150, 200)
    assert mock_engine.image_width_px == 200 and mock_engine.image_height_px == 150

    print("\nTesting render trigger without specific size (should use RenderArea size from MockMainWindow)...")
    # Reset engine's size to ensure it's updated from mock_main_win.render_area
    mock_engine.update_image_size(10,10)
    controller.trigger_render()
    assert rendered_data_shape == (mock_main_win.render_area.height(), mock_main_win.render_area.width()) # (400,600)
    assert "View: 600x400px" in last_status

    current_params = controller.get_current_parameters()
    print(f"\nTest: Current params from controller: {current_params}")
    assert current_params["max_iterations"] == 150

    print("\nAll basic controller tests passed.")
