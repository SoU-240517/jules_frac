from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, QThreadPool
import time
import numpy as np
from PIL import Image # Import Pillow

# For type hinting the fractal_engine_ref
# from src.app.models.fractal_engine import FractalEngine

class ExporterSignals(QObject):
    progress_updated = pyqtSignal(int)
    export_finished = pyqtSignal(bool, str)

class ImageExporter(QRunnable):
    def __init__(self, fractal_engine_ref, export_settings: dict):
        super().__init__()
        self.fractal_engine = fractal_engine_ref
        self.export_settings = export_settings
        self.signals = ExporterSignals()
        self._is_cancelled = False

    def run(self):
        filepath = self.export_settings.get('filepath', 'fractal_export.png') # Initialize for use in except block
        try:
            self.signals.progress_updated.emit(0)
            if self._is_cancelled:
                self.signals.export_finished.emit(False, "エクスポートがキャンセルされました。")
                return

            # Expand other settings from export_settings dict
            output_width = self.export_settings.get('width', 1920)
            output_height = self.export_settings.get('height', 1080)
            common_params_override = {
                'max_iterations': self.export_settings.get('iterations', self.fractal_engine.max_iterations if self.fractal_engine else 100)
            }
            fractal_plugin_name_override = self.export_settings.get('fractal_plugin_name')
            fractal_plugin_params_override = self.export_settings.get('fractal_plugin_params')
            coloring_algo_name_override = self.export_settings.get('coloring_algorithm_name') # Corrected key from dialog example
            coloring_algo_params_override = self.export_settings.get('coloring_algorithm_params')
            color_pack_name_override = self.export_settings.get('color_pack_name')
            color_map_name_override = self.export_settings.get('color_map_name')

            # Antialiasing: dialog passes factor, engine expects string
            aa_factor = self.export_settings.get('antialiasing_factor', 1)
            antialiasing_level_str = f"{aa_factor}x{aa_factor} SSAA" if aa_factor > 1 else "なし"


            print(f"ImageExporter: Export process starting for {filepath} ({output_width}x{output_height}), AA: {antialiasing_level_str}")
            self.signals.progress_updated.emit(5)

            if self._is_cancelled:
                self.signals.export_finished.emit(False, "計算開始前にキャンセルされました。")
                return

            image_data_np = self.fractal_engine.generate_image_for_output(
                output_width=output_width,
                output_height=output_height,
                common_params_override=common_params_override,
                fractal_plugin_name_override=fractal_plugin_name_override,
                fractal_plugin_params_override=fractal_plugin_params_override,
                coloring_algo_name_override=coloring_algo_name_override,
                coloring_algo_params_override=coloring_algo_params_override,
                color_pack_name_override=color_pack_name_override,
                color_map_name_override=color_map_name_override,
                antialiasing_level=antialiasing_level_str
            )

            self.signals.progress_updated.emit(80)

            if self._is_cancelled:
                self.signals.export_finished.emit(False, "ファイル保存前にキャンセルされました。")
                return

            if image_data_np is None:
                self.signals.export_finished.emit(False, "画像データの生成に失敗しました (エンジンがNoneを返しました)。")
                return

            # --- Pillow based file saving ---
            print(f"ImageExporter: Image data generated ({image_data_np.shape}). Starting file save: {filepath}")

            pil_image = Image.fromarray(image_data_np, 'RGBA')
            format_str = self.export_settings.get('format', 'PNG').upper()
            save_options = {}

            image_to_save = pil_image # Default to original RGBA

            if format_str == 'PNG':
                save_options['optimize'] = True
                # PNG supports RGBA directly. png_transparent option from dialog might mean
                # "ensure alpha is used" or "make background transparent if it wasn't already".
                # Assuming RGBA data from engine already has correct alpha.
                # If 'png_transparent' is False and image HAS alpha, we might want to convert to RGB
                # by blending with a white background, but usually, users expect alpha if present.
                # For simplicity, save as RGBA if it has alpha, or RGB if it doesn't.
                # Since we create RGBA in engine, it will be saved as RGBA.
                # If png_transparent is False, one might convert to RGB:
                # if not self.export_settings.get('png_transparent', True) and pil_image.mode == 'RGBA':
                #    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                #    background.paste(pil_image, mask=pil_image.split()[3])
                #    image_to_save = background
                pass # Default is to save RGBA as is for PNG

            elif format_str == 'JPEG':
                save_options['quality'] = self.export_settings.get('jpeg_quality', 90)
                save_options['optimize'] = True
                # save_options['progressive'] = True # Optional
                if pil_image.mode == 'RGBA':
                    # Blend with white background before converting to RGB for JPEG
                    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                    # Use the alpha channel of the original image as a mask
                    try:
                        alpha_channel = pil_image.split()[3]
                        background.paste(pil_image, mask=alpha_channel)
                        image_to_save = background
                    except IndexError: # In case image is not RGBA (e.g. LA)
                        image_to_save = pil_image.convert('RGB')
                else: # If not RGBA, ensure it's RGB
                    image_to_save = pil_image.convert('RGB')

            elif format_str == 'TIFF':
                save_options['compression'] = 'tiff_lzw' # Common lossless compression
                # TIFF can handle RGBA

            elif format_str == 'BMP':
                # BMP typically does not support alpha well, convert to RGB
                if pil_image.mode == 'RGBA':
                    image_to_save = pil_image.convert('RGB')
            else:
                self.signals.export_finished.emit(False, f"未対応のファイル形式です: {format_str}")
                return

            if self._is_cancelled:
                self.signals.export_finished.emit(False, "エクスポートがキャンセルされました (保存直前)。")
                return

            print(f"ImageExporter: Saving to '{filepath}' as '{format_str}' with options {save_options}...")
            image_to_save.save(filepath, format=format_str, **save_options)

            self.signals.progress_updated.emit(100)
            self.signals.export_finished.emit(True, filepath)
            print(f"ImageExporter: Save complete.")

        except FileNotFoundError:
            error_msg = f"指定されたパスのディレクトリが見つかりません: {Path(filepath).parent}"
            print(f"ImageExporter: Error - {error_msg}")
            self.signals.export_finished.emit(False, error_msg)
        except IOError as e:
            error_msg = f"ファイルの書き込みに失敗しました ({filepath}): {e}"
            print(f"ImageExporter: Error - {error_msg}")
            self.signals.export_finished.emit(False, error_msg)
        except Exception as e:
            import traceback
            error_msg = f"予期せぬエクスポートエラー: {e}"
            print(f"ImageExporter: Unexpected error during export: {e}\n{traceback.format_exc()}")
            self.signals.export_finished.emit(False, error_msg)

    def cancel(self):
        print("ImageExporter: Cancellation requested.")
        self._is_cancelled = True

if __name__ == '__main__':
    print("ImageExporter Standalone Test (simulated execution)")
    # ... (MockFractalEngine and test setup from previous step, potentially simplified)
    class MockFractalEngine:
        def generate_image_for_output(self, output_width, output_height, **kwargs):
            print(f"  MockEngine: generate_image_for_output for {output_width}x{output_height}, AA: {kwargs.get('antialiasing_level')}")
            time.sleep(0.1) # Simulate generation time
            if exporter_for_test._is_cancelled: return None # Use a more direct reference for test
            return np.random.randint(0, 256, size=(output_height, output_width, 4), dtype=np.uint8)

    mock_engine_instance = MockFractalEngine()
    test_settings_png = {
        'filepath': 'test_export_run.png', 'format': 'PNG', 'width': 100, 'height': 80,
        'iterations': 150, 'antialiasing_factor': 1, 'antialiasing': "なし",
        'png_transparent': True
    }
    test_settings_jpg = {
        'filepath': 'test_export_run.jpg', 'format': 'JPEG', 'width': 120, 'height': 90,
        'iterations': 100, 'antialiasing_factor': 1, 'antialiasing': "なし",
        'jpeg_quality': 85
    }

    exporter_for_test = None # To be assigned for mock engine access

    def handle_progress(p): print(f"  Test Progress: {p}%")
    def handle_finished(success, msg_or_path):
        status = "SUCCESS" if success else "FAILURE"
        print(f"  Test Finished {status}: {msg_or_path}")

    print("\n--- Test 1: PNG export ---")
    exporter_png = ImageExporter(mock_engine_instance, test_settings_png)
    exporter_for_test = exporter_png # For mock engine to check cancel flag
    exporter_png.signals.progress_updated.connect(handle_progress)
    exporter_png.signals.export_finished.connect(handle_finished)
    exporter_png.run()
    if Path(test_settings_png['filepath']).exists(): Path(test_settings_png['filepath']).unlink() # Clean up

    print("\n--- Test 2: JPEG export ---")
    exporter_jpg = ImageExporter(mock_engine_instance, test_settings_jpg)
    exporter_for_test = exporter_jpg
    exporter_jpg.signals.progress_updated.connect(handle_progress)
    exporter_jpg.signals.export_finished.connect(handle_finished)
    exporter_jpg.run()
    if Path(test_settings_jpg['filepath']).exists(): Path(test_settings_jpg['filepath']).unlink()

    print("\n--- Test 3: Cancellation during generation (simulated) ---")
    exporter_cancel = ImageExporter(mock_engine_instance, test_settings_png)
    exporter_for_test = exporter_cancel # Mock engine needs access to this instance's flag
    exporter_cancel.signals.progress_updated.connect(handle_progress)
    exporter_cancel.signals.export_finished.connect(handle_finished)
    exporter_cancel.cancel() # Request cancel before run, generate_image_for_output should see it
    exporter_cancel.run()

    print("\nImageExporter standalone test finished.")
