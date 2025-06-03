import os
import importlib.util
import sys
import inspect
from pathlib import Path

# アプリケーションの構造に基づいた絶対インポートを使用します。
# main.py で _project_root (jules_frac ディレクトリ) が sys.path に追加されるため、
# src.app.plugins.base_plugin のように参照可能です。
from src.app.plugins.base_plugin import FractalPlugin
from src.app.plugins.base_coloring_plugin import ColoringAlgorithmPlugin

class PluginManager:
    """
    Manages the dynamic loading of fractal and coloring algorithm plugins.
    """
    def __init__(self,
                 project_root_path: Path,
                 fractal_plugin_folder_path: str = "src/app/plugins/fractals",
                 coloring_plugin_folder_path: str = "src/app/plugins/coloring"):
        """
        Initializes the PluginManager.
        `fractal_plugin_folder_path` and `coloring_plugin_folder_path` are relative to `project_root_path`.
        """
        self.project_root = project_root_path
        self.fractal_plugin_folder = (self.project_root / fractal_plugin_folder_path).resolve()
        self.fractal_plugins: dict[str, FractalPlugin] = {}

        self.coloring_plugin_folder = (self.project_root / coloring_plugin_folder_path).resolve()
        self.coloring_plugins: dict[str, ColoringAlgorithmPlugin] = {}

        self.load_all_plugins()

    def load_all_plugins(self):
        """Loads all types of plugins."""
        print("PluginManager: Loading all plugins...")
        self._load_plugins_from_folder(
            self.fractal_plugin_folder,
            self.fractal_plugins,
            FractalPlugin,
            "Fractal"
        )
        self._load_plugins_from_folder(
            self.coloring_plugin_folder,
            self.coloring_plugins,
            ColoringAlgorithmPlugin,
            "Coloring Algorithm"
        )

    def _load_plugins_from_folder(self, folder_path: Path, target_dict: dict, base_class: type, plugin_type_name: str):
        """
        Loads plugins of a specific base_class from the given folder_path into target_dict.
        """
        target_dict.clear()

        print(f"PluginManager: Loading {plugin_type_name} plugins from '{folder_path}'...")

        if not folder_path.is_dir():
            print(f"PluginManager Error: {plugin_type_name} plugin folder not found: {folder_path}")
            return

        # sys.path modification is no longer needed as plugins will use absolute imports from 'src.'
        for file_path in folder_path.glob("*.py"):
                module_name = file_path.stem

                if module_name.startswith("__") or module_name in ["base_plugin", "base_coloring_plugin"]:
                    continue

                try:
                    spec = importlib.util.spec_from_file_location(module_name, str(file_path.resolve()))
                    if spec is None or spec.loader is None:
                        print(f"PluginManager Warning: Could not create module spec for {file_path.name}")
                        continue

                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for member_name, cls in inspect.getmembers(module, inspect.isclass):
                        # ---- ここからデバッグ用コード ----
                        # print(f"PluginManager DEBUG: Checking class '{cls.__module__}.{cls.__name__}' (id: {id(cls)})")
                        # print(f"PluginManager DEBUG: Against base_class '{base_class.__module__}.{base_class.__name__}' (id: {id(base_class)})")
                        # is_sub = False
                        # try:
                        #     is_sub = issubclass(cls, base_class)
                        # except TypeError as te:
                        #     print(f"PluginManager DEBUG: issubclass check failed with TypeError: {te}")
                        # print(f"PluginManager DEBUG: issubclass(cls, base_class) -> {is_sub}")
                        # print(f"PluginManager DEBUG: cls is base_class -> {cls is base_class}")
                        # print(f"PluginManager DEBUG: inspect.isabstract(cls) -> {inspect.isabstract(cls)}")
                        # ---- ここまでデバッグ用コード ----
                        if issubclass(cls, base_class) and cls is not base_class and not inspect.isabstract(cls):
                            try:
                                plugin_instance = cls()
                                if plugin_instance.name in target_dict:
                                    print(f"PluginManager Warning: Duplicate {plugin_type_name} plugin name '{plugin_instance.name}'. "
                                          f"Ignoring {file_path.name}, using existing.")
                                else:
                                    target_dict[plugin_instance.name] = plugin_instance
                                    print(f"PluginManager: Loaded {plugin_type_name} plugin '{plugin_instance.name}' from {file_path.name}.")
                            except Exception as e:
                                print(f"PluginManager Error: Failed to instantiate {plugin_type_name} plugin '{member_name}' "
                                      f"from {file_path.name}: {e}")
                except Exception as e:
                    print(f"PluginManager Error: Failed to load {plugin_type_name} plugin file '{file_path.name}': {e}")

        if not target_dict:
            print(f"PluginManager: No valid {plugin_type_name} plugins found in '{folder_path}'.")

    # Fractal Plugin specific methods
    def get_available_fractal_plugins(self) -> list[FractalPlugin]:
        return list(self.fractal_plugins.values())

    def get_fractal_plugin(self, name: str) -> FractalPlugin | None:
        return self.fractal_plugins.get(name)

    # Coloring Algorithm Plugin specific methods
    def get_available_coloring_plugins(self) -> list[ColoringAlgorithmPlugin]:
        return list(self.coloring_plugins.values())

    def get_coloring_plugin(self, name: str) -> ColoringAlgorithmPlugin | None:
        return self.coloring_plugins.get(name)

    def reload_all_plugins(self):
        print("PluginManager: Reloading all plugins...")
        self.load_all_plugins()

if __name__ == '__main__':
    print("PluginManager Standalone Test")
    # This test assumes a specific directory structure relative to where this script is run,
    # or that the default paths "src/app/plugins/fractals" and "src/app/plugins/coloring" exist
    # and contain valid plugins and their base classes.

    # For a more robust test, create temporary plugin directories and files.
    # This script should be run from the project root for default paths to work as intended.

    current_dir = Path.cwd()
    print(f"  Current working directory: {current_dir}")

    # Create dummy base files if they don't exist (for standalone test from non-project root)
    temp_base_dir = Path("temp_plugin_bases_delete_me")
    temp_base_dir.mkdir(exist_ok=True)

    base_plugin_content = """
from abc import ABC, abstractmethod
import numpy as np
class FractalPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    @abstractmethod
    def get_parameters_definition(self) -> list: pass
    @abstractmethod
    def compute_fractal(self,c,p,w,h) -> dict: return {'iterations': np.zeros((h,w),dtype=np.int32)}
    @abstractmethod
    def get_default_view_parameters(self) -> dict: pass
"""
    with open(temp_base_dir / "base_plugin.py", "w", encoding="utf-8") as f:
        f.write(base_plugin_content)

    base_coloring_content = """
from abc import ABC, abstractmethod
import numpy as np
class ColoringAlgorithmPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    @abstractmethod
    def get_parameters_definition(self) -> list: pass
    @abstractmethod
    def apply_coloring(self,fd,cfp,ap,cm) -> np.ndarray: return np.zeros((fd['iterations'].shape[0],fd['iterations'].shape[1],4),dtype=np.uint8)
"""
    with open(temp_base_dir / "base_coloring_plugin.py", "w", encoding="utf-8") as f:
        f.write(base_coloring_content)

    # Add temp_base_dir to sys.path to allow PluginManager to import base classes via fallback
    import sys
    sys.path.insert(0, str(temp_base_dir.resolve()))


    # Create dummy plugin directories and plugins for testing
    test_fractal_dir = Path("temp_fractal_plugins_delete_me")
    test_fractal_dir.mkdir(exist_ok=True)
    dummy_mandel_content = f"""
from {temp_base_dir.name}.base_plugin import FractalPlugin # Adjusted import for temp structure
import numpy as np
class TestMandel(FractalPlugin):
    @property
    def name(self): return "TestMandelbrot"
    def get_parameters_definition(self): return []
    def compute_fractal(self,c,p,w,h): return {{'iterations': np.zeros((h,w),dtype=np.int32), 'last_z_modulus_sq': np.zeros((h,w),dtype=np.float64)}}
    def get_default_view_parameters(self): return {{}}
"""
    with open(test_fractal_dir / "test_mandel_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_mandel_content)

    test_coloring_dir = Path("temp_coloring_plugins_delete_me")
    test_coloring_dir.mkdir(exist_ok=True)
    dummy_gray_content = f"""
from {temp_base_dir.name}.base_coloring_plugin import ColoringAlgorithmPlugin # Adjusted import
import numpy as np
class TestGray(ColoringAlgorithmPlugin):
    @property
    def name(self): return "TestGrayscale"
    def get_parameters_definition(self): return []
    def apply_coloring(self,fd,cfp,ap,cm): return np.zeros((fd['iterations'].shape[0],fd['iterations'].shape[1],4),dtype=np.uint8)
"""
    with open(test_coloring_dir / "test_gray_plugin.py", "w", encoding="utf-8") as f:
        f.write(dummy_gray_content)

    print(f"  Created temp plugin dirs: {test_fractal_dir.resolve()}, {test_coloring_dir.resolve()}")

    # For the standalone test, the project_root is the current directory,
    # and plugin folder paths are relative to this.
    manager = PluginManager(
        project_root_path=Path.cwd(), # Test assumes CWD is where temp dirs are created
        fractal_plugin_folder_path=test_fractal_dir.name, # Pass as relative path string from CWD
        coloring_plugin_folder_path=test_coloring_dir.name # Pass as relative path string from CWD
    )

    print("\nAvailable Fractal Plugins:")
    for p in manager.get_available_fractal_plugins(): print(f"  - {p.name}")
    assert manager.get_fractal_plugin("TestMandelbrot") is not None, "TestMandelbrot not loaded"

    print("\nAvailable Coloring Plugins:")
    for p in manager.get_available_coloring_plugins(): print(f"  - {p.name}")
    assert manager.get_coloring_plugin("TestGrayscale") is not None, "TestGrayscale not loaded"

    print("\nReloading plugins test...")
    manager.reload_all_plugins()
    assert manager.get_fractal_plugin("TestMandelbrot") is not None, "TestMandelbrot not loaded after reload"
    assert manager.get_coloring_plugin("TestGrayscale") is not None, "TestGrayscale not loaded after reload"
    print("Plugins successfully reloaded.")

    # Clean up temporary directories and files
    import shutil
    try:
        shutil.rmtree(test_fractal_dir)
        shutil.rmtree(test_coloring_dir)
        shutil.rmtree(temp_base_dir)
        # sys.path.pop(0) # Remove temp_base_dir from sys.path
        print("\nCleaned up temporary test directories and files.")
    except Exception as e:
        print(f"\nError during cleanup: {e}")

    print("\nPluginManager test finished.")
