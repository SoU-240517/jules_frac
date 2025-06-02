import numpy as np
import time

from src.app.plugins.plugin_manager import PluginManager
from src.app.plugins.base_plugin import FractalPlugin
from src.app.plugins.base_coloring_plugin import ColoringAlgorithmPlugin
from src.app.coloring.color_manager import ColorManager
# from PIL import Image # If Pillow is used for resizing, not used in this version


class FractalEngine:
    def __init__(self, image_width_px=800, image_height_px=600,
                 fractal_plugin_folder="src/app/plugins/fractals",
                 coloring_plugin_folder="src/app/plugins/coloring",
                 color_pack_folder="assets/colorpacks"):

        self.max_iterations = 100
        self.center_real = -0.5
        self.center_imag = 0.0
        self.width = 3.0
        self.escape_radius = 2.0

        self.image_width_px = image_width_px if image_width_px > 0 else 800
        self.image_height_px = image_height_px if image_height_px > 0 else 600
        self.height = (self.width * self.image_height_px) / self.image_width_px if self.image_width_px > 0 else self.width

        self.plugin_manager = PluginManager(
            fractal_plugin_folder_path=fractal_plugin_folder,
            coloring_plugin_folder_path=coloring_plugin_folder
        )
        self.color_manager = ColorManager(color_packs_dir=color_pack_folder)

        self.current_fractal_plugin: FractalPlugin | None = None
        self.current_fractal_plugin_parameters: dict = {}
        self.current_coloring_plugin: ColoringAlgorithmPlugin | None = None
        self.current_coloring_plugin_parameters: dict = {}
        self.current_color_pack_name: str | None = None
        self.current_color_map_name: str | None = None
        self.last_fractal_data_cache: dict | None = None

        self._initialize_default_plugins_and_map()

    def _initialize_default_plugins_and_map(self):
        available_fractal_plugins = self.get_available_fractal_plugin_names()
        if available_fractal_plugins:
            default_fractal = "Mandelbrot"
            if default_fractal in available_fractal_plugins: self.set_active_fractal_plugin(default_fractal)
            else: self.set_active_fractal_plugin(available_fractal_plugins[0])
        else: print("FractalEngine Warning: No fractal plugins found.")

        available_coloring_plugins = self.get_available_coloring_plugin_names()
        if available_coloring_plugins:
            default_coloring = "グレースケール (標準)"
            if default_coloring in available_coloring_plugins: self.set_active_coloring_plugin(default_coloring)
            elif "スムーズカラー" in available_coloring_plugins: self.set_active_coloring_plugin("スムーズカラー")
            elif available_coloring_plugins: self.set_active_coloring_plugin(available_coloring_plugins[0])
        else: print("FractalEngine Warning: No coloring plugins found.")

        available_color_packs = self.get_available_color_pack_names()
        if available_color_packs:
            pack_to_try = "デフォルト"
            if pack_to_try not in available_color_packs: pack_to_try = available_color_packs[0]
            maps_in_pack = self.get_available_color_map_names_in_pack(pack_to_try)
            if maps_in_pack: self.set_active_color_map(pack_to_try, maps_in_pack[0])
        else: print("FractalEngine Warning: No color packs found.")

    def update_image_size(self, image_width_px, image_height_px):
        self.image_width_px = image_width_px if image_width_px > 0 else self.image_width_px
        self.image_height_px = image_height_px if image_height_px > 0 else self.image_height_px
        self.update_aspect_ratio()

    def update_aspect_ratio(self):
        if self.image_width_px > 0 and self.image_height_px > 0 :
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else: self.height = self.width

    def set_common_parameters(self, center_real, center_imag, width, max_iterations, escape_radius=None):
        self.center_real=center_real; self.center_imag=center_imag; self.width=width; self.max_iterations=max_iterations
        if escape_radius is not None: self.escape_radius = escape_radius
        self.update_aspect_ratio()
        self.last_fractal_data_cache = None # Invalidate cache

    def get_common_parameters(self) -> dict:
        return {'center_real': self.center_real, 'center_imag': self.center_imag,
                'width': self.width, 'height': self.height,
                'max_iterations': self.max_iterations, 'escape_radius': self.escape_radius}

    def set_active_fractal_plugin(self, plugin_name: str) -> bool:
        plugin = self.plugin_manager.get_fractal_plugin(plugin_name)
        if plugin:
            self.current_fractal_plugin = plugin
            defaults = plugin.get_default_view_parameters()
            self.center_real = defaults.get('center_real', self.center_real)
            self.center_imag = defaults.get('center_imag', self.center_imag)
            self.width = defaults.get('width', self.width)
            self.max_iterations = defaults.get('max_iterations', self.max_iterations)
            self.update_aspect_ratio()
            self.current_fractal_plugin_parameters.clear()
            for p_def in plugin.get_parameters_definition():
                self.current_fractal_plugin_parameters[p_def['name']] = p_def['default']
            self.last_fractal_data_cache = None
            return True
        return False

    def get_active_fractal_plugin(self) -> FractalPlugin | None: return self.current_fractal_plugin
    def get_available_fractal_plugin_names(self) -> list[str]: return [p.name for p in self.plugin_manager.get_available_fractal_plugins()]
    def get_current_fractal_plugin_parameter_definitions(self) -> list: return self.current_fractal_plugin.get_parameters_definition() if self.current_fractal_plugin else []
    def set_fractal_plugin_parameter(self, name: str, value: any):
        if self.current_fractal_plugin and name in self.current_fractal_plugin_parameters:
            self.current_fractal_plugin_parameters[name] = value
            self.last_fractal_data_cache = None
    def get_fractal_plugin_parameters(self) -> dict: return self.current_fractal_plugin_parameters.copy()

    def set_active_coloring_plugin(self, plugin_name: str) -> bool:
        plugin = self.plugin_manager.get_coloring_plugin(plugin_name)
        if plugin:
            self.current_coloring_plugin = plugin
            self.current_coloring_plugin_parameters.clear()
            for p_def in plugin.get_parameters_definition():
                self.current_coloring_plugin_parameters[p_def['name']] = p_def['default']
            return True
        return False

    def get_active_coloring_plugin(self) -> ColoringAlgorithmPlugin | None: return self.current_coloring_plugin
    def get_available_coloring_plugin_names(self) -> list[str]: return [p.name for p in self.plugin_manager.get_available_coloring_plugins()]
    def get_current_coloring_plugin_parameter_definitions(self) -> list: return self.current_coloring_plugin.get_parameters_definition() if self.current_coloring_plugin else []
    def set_coloring_plugin_parameter(self, name: str, value: any):
        if self.current_coloring_plugin and name in self.current_coloring_plugin_parameters:
            self.current_coloring_plugin_parameters[name] = value
    def get_coloring_plugin_parameters(self) -> dict: return self.current_coloring_plugin_parameters.copy()

    def set_active_color_map(self, pack_name: str, map_name: str) -> bool:
        map_data = self.color_manager.get_color_map_data(pack_name, map_name)
        if map_data:
            self.current_color_pack_name = pack_name
            self.current_color_map_name = map_name
            return True
        return False
    def get_available_color_pack_names(self) -> list[str]: return self.color_manager.get_available_color_pack_names()
    def get_available_color_map_names_in_pack(self, pack: str) -> list[str]: return self.color_manager.get_color_maps_in_pack(pack)
    def get_current_color_map_selection(self) -> tuple[str | None, str | None]: return self.current_color_pack_name, self.current_color_map_name

    def compute_current_fractal(self) -> dict | None:
        if not self.current_fractal_plugin: return None
        common_params = self.get_common_parameters()
        try:
            self.last_fractal_data_cache = self.current_fractal_plugin.compute_fractal(
                common_params, self.current_fractal_plugin_parameters,
                self.image_width_px, self.image_height_px
            )
            return self.last_fractal_data_cache
        except Exception as e:
            print(f"FractalEngine Error during computation: {e}")
            self.last_fractal_data_cache = None
            return None

    def apply_coloring(self, fractal_data_override: dict | None = None) -> np.ndarray | None:
        data_to_color = fractal_data_override if fractal_data_override is not None else self.last_fractal_data_cache
        if not self.current_coloring_plugin or data_to_color is None: return None
        color_map_list = []
        if self.current_color_pack_name and self.current_color_map_name:
            color_map_list = self.color_manager.get_color_map_data(self.current_color_pack_name, self.current_color_map_name)
        if not color_map_list : color_map_list = [(i,i,i) for i in range(0,256,16)] # Simple fallback grayscale

        common_fp = self.get_common_parameters()
        common_fp['image_width_px'] = data_to_color.get('iterations', np.empty((0,0))).shape[1]
        common_fp['image_height_px'] = data_to_color.get('iterations', np.empty((0,0))).shape[0]
        try:
            return self.current_coloring_plugin.apply_coloring(
                data_to_color, common_fp, self.current_coloring_plugin_parameters, color_map_list
            )
        except Exception as e:
            h = common_fp['image_height_px']; w = common_fp['image_width_px']
            err_img = np.full((h if h>0 else 1, w if w>0 else 1, 4), [255,0,0,255], dtype=np.uint8)
            return err_img

    def _get_antialiasing_factor(self, antialiasing_level_str: str) -> int:
        if antialiasing_level_str == "2x2 SSAA": return 2
        if antialiasing_level_str == "3x3 SSAA": return 3
        if antialiasing_level_str == "4x4 SSAA": return 4
        return 1

    def generate_image_for_output(self, output_width: int, output_height: int,
                                  common_params_override: dict,
                                  fractal_plugin_name_override: str | None = None, # Changed to name
                                  fractal_plugin_params_override: dict | None = None,
                                  coloring_algo_name_override: str | None = None,
                                  coloring_algo_params_override: dict | None = None,
                                  color_pack_name_override: str | None = None,
                                  color_map_name_override: str | None = None,
                                  antialiasing_level: str = "なし"
                                  ) -> np.ndarray | None:

        print(f"FractalEngine: Starting high-resolution output - Target: {output_width}x{output_height}, AA: {antialiasing_level}")

        # 1. Parameter Preparation
        final_common_params = self.get_common_parameters()
        final_common_params.update(common_params_override) # Override with dialog settings

        # Determine Fractal Plugin and its parameters
        active_fractal_plugin = self.plugin_manager.get_fractal_plugin(fractal_plugin_name_override) if fractal_plugin_name_override else self.current_fractal_plugin
        if not active_fractal_plugin: print("Error: Output failed, fractal plugin not resolved."); return None

        final_fractal_plugin_params = {} # Start with empty or plugin defaults
        base_plugin_param_defs = active_fractal_plugin.get_parameters_definition()
        for p_def in base_plugin_param_defs: final_fractal_plugin_params[p_def['name']] = p_def['default']
        if self.current_fractal_plugin and active_fractal_plugin.name == self.current_fractal_plugin.name: # If same as current
            final_fractal_plugin_params.update(self.current_fractal_plugin_parameters) # Use current settings as base
        if fractal_plugin_params_override: final_fractal_plugin_params.update(fractal_plugin_params_override)

        # Determine Coloring Plugin and its parameters
        active_coloring_plugin = self.plugin_manager.get_coloring_plugin(coloring_algo_name_override) if coloring_algo_name_override else self.current_coloring_plugin
        if not active_coloring_plugin: print("Error: Output failed, coloring plugin not resolved."); return None

        final_coloring_algo_params = {}
        base_coloring_param_defs = active_coloring_plugin.get_parameters_definition()
        for p_def in base_coloring_param_defs: final_coloring_algo_params[p_def['name']] = p_def['default']
        if self.current_coloring_plugin and active_coloring_plugin.name == self.current_coloring_plugin.name:
             final_coloring_algo_params.update(self.current_coloring_plugin_parameters)
        if coloring_algo_params_override: final_coloring_algo_params.update(coloring_algo_params_override)

        # Determine Color Map
        pack_name = color_pack_name_override if color_pack_name_override else self.current_color_pack_name
        map_name = color_map_name_override if color_map_name_override else self.current_color_map_name
        final_color_map_data = self.color_manager.get_color_map_data(pack_name, map_name) if pack_name and map_name else []
        if not final_color_map_data: final_color_map_data = [(i,i,i) for i in range(0,256,16)] # Fallback

        # 2. Supersampling Resolution
        aa_factor = self._get_antialiasing_factor(antialiasing_level)
        ss_width = output_width * aa_factor
        ss_height = output_height * aa_factor

        # 3. Adjust common_params.height for supersampled aspect ratio
        # This is critical: the 'height' in common_params is complex plane height.
        # It must match the aspect ratio of the pixel grid being computed.
        original_engine_complex_height = final_common_params['height'] # To restore later if engine state is modified directly
        final_common_params['height'] = (final_common_params['width'] * ss_height) / ss_width if ss_width > 0 else final_common_params['width']

        print(f"  - Supersampling at: {ss_width}x{ss_height} (AA Factor: {aa_factor})")
        print(f"  - Fractal Plugin: {active_fractal_plugin.name}, Params: {final_fractal_plugin_params}")
        print(f"  - Coloring Plugin: {active_coloring_plugin.name}, Params: {final_coloring_algo_params}")
        print(f"  - Color Map: {pack_name}/{map_name}")
        print(f"  - Common Params for compute: Center=({final_common_params['center_real']:.4f},{final_common_params['center_imag']:.4f}), Width={final_common_params['width']:.3e}, Height(complex)={final_common_params['height']:.3e}, Iter={final_common_params['max_iterations']}")

        # 4. Fractal Computation (at supersampled resolution)
        fractal_data_ss = active_fractal_plugin.compute_fractal(
            final_common_params, final_fractal_plugin_params, ss_width, ss_height
        )
        if fractal_data_ss is None: print("Error: Supersampled fractal computation failed."); return None

        # Add image dimensions to common_params for coloring plugin, as it might need it
        final_common_params_for_coloring = final_common_params.copy()
        final_common_params_for_coloring['image_width_px'] = ss_width
        final_common_params_for_coloring['image_height_px'] = ss_height

        # 5. Coloring (at supersampled resolution)
        colored_image_ss_rgba = active_coloring_plugin.apply_coloring(
            fractal_data_ss, final_common_params_for_coloring, final_coloring_algo_params, final_color_map_data
        )
        if colored_image_ss_rgba is None: print("Error: Supersampled coloring failed."); return None

        # 6. Downsampling (if AA is enabled)
        if aa_factor > 1:
            print(f"  - Downsampling from {ss_width}x{ss_height} to {output_width}x{output_height}...")
            try:
                # Ensure RGBA (4 channels) for reshaping
                if colored_image_ss_rgba.shape[2] != 4: # Should always be 4 from coloring plugins
                    print(f"Error: Expected 4 channels from coloring, got {colored_image_ss_rgba.shape[2]}"); return None

                reshaped = colored_image_ss_rgba.reshape(output_height, aa_factor, output_width, aa_factor, 4)
                downsampled_image_rgba = reshaped.mean(axis=(1, 3)).astype(np.uint8)
            except ValueError as e:
                print(f"Error during downsampling reshape: {e}. Input: {colored_image_ss_rgba.shape}, Target: {output_height}x{output_width}, AA: {aa_factor}"); return None
        else:
            downsampled_image_rgba = colored_image_ss_rgba

        print(f"FractalEngine: High-resolution image generated successfully ({output_width}x{output_height}).")
        return downsampled_image_rgba


if __name__ == '__main__':
    # Test requires plugins and color packs in default locations relative to CWD
    # e.g., CWD = project root, then paths like "src/app/plugins/fractals" are valid.
    print("FractalEngine (with generate_image_for_output) Standalone Test")
    engine = FractalEngine(image_width_px=80, image_height_px=60) # Small default for screen

    if not engine.get_active_fractal_plugin() or not engine.get_active_coloring_plugin():
        print("Default plugins not loaded. Check paths or plugin availability. Test cannot proceed fully.")
    else:
        print(f"Active Fractal Plugin: {engine.get_active_fractal_plugin().name}")
        print(f"Active Coloring Plugin: {engine.get_active_coloring_plugin().name}")
        cp, cm = engine.get_current_color_map_selection()
        print(f"Active Color Map: {cp} - {cm}")

        output_params = {
            'max_iterations': 200, # Override iterations for output
            # Other common params will use engine's current state unless overridden
        }

        # Test high-res output (e.g. Mandelbrot with Grayscale)
        print("\nGenerating 160x120 image with 2x2 SSAA...")
        output_image = engine.generate_image_for_output(
            output_width=160, output_height=120,
            common_params_override=output_params,
            # Using current plugins and their params, and current color map
            antialiasing_level="2x2 SSAA"
        )
        if output_image is not None:
            print(f"  Output image generated. Shape: {output_image.shape}, Dtype: {output_image.dtype}")
            assert output_image.shape == (120, 160, 4)
            # import matplotlib.pyplot as plt # For visual check if needed
            # plt.imshow(output_image); plt.show()
        else:
            print("  High-resolution image generation failed.")

    print("\nFractalEngine test finished.")
