import json
from pathlib import Path
import os

class SettingsManager:
    def __init__(self, settings_filename: str = "base_settings.json"):
        # Consider using a standard application data directory
        # For simplicity, using current working directory or a specified path
        # If settings_filename is just a name, it's created in CWD.
        # If it's a path, it's used as is.
        self.filepath = Path(settings_filename)
        if not self.filepath.is_absolute():
            # If a relative path is given, make it relative to CWD or a defined app data dir.
            # For this example, CWD is used if just a filename is provided.
            # A more robust solution would use QStandardPaths or appdirs.
            try:
                # Try to place it in user's home directory for persistence across runs from different locations
                home_dir = Path.home()
                app_data_dir = home_dir / ".fractalapp" # Example hidden folder
                app_data_dir.mkdir(parents=True, exist_ok=True)
                self.filepath = app_data_dir / settings_filename
            except Exception as e:
                print(f"SettingsManager Warning: Could not create settings directory in home. Using CWD. Error: {e}")
                self.filepath = Path.cwd() / settings_filename


        self.settings: dict = {}
        self.load_settings()

    def load_settings(self):
        if self.filepath.exists() and self.filepath.is_file():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                print(f"SettingsManager: Settings loaded from {self.filepath}")
            except (json.JSONDecodeError, IOError, Exception) as e: # Catch more general exceptions too
                print(f"SettingsManager Error: Failed to load settings file '{self.filepath}': {e}. Using default settings.")
                self.settings = {}
        else:
            print(f"SettingsManager: Settings file not found ('{self.filepath}'). Using default settings.")
            self.settings = {}

    def save_settings(self):
        try:
            # Ensure parent directory exists
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            print(f"SettingsManager: Settings saved to {self.filepath}")
        except (IOError, Exception) as e: # Catch more general exceptions
            print(f"SettingsManager Error: Failed to save settings file '{self.filepath}': {e}")

    def get_setting(self, key_path: str, default_value: any = None) -> any:
        keys = key_path.split('.')
        value_ptr = self.settings
        try:
            for key in keys:
                if not isinstance(value_ptr, dict): # If a path segment is not a dict
                    return default_value
                value_ptr = value_ptr[key]
            return value_ptr
        except KeyError:
            return default_value
        except TypeError: # Handle cases where value_ptr becomes None or non-dict unexpectedly
             return default_value


    def set_setting(self, key_path: str, value: any, auto_save: bool = True):
        keys = key_path.split('.')
        current_level = self.settings

        for i, key in enumerate(keys[:-1]): # Iterate to the second to last key
            if key not in current_level or not isinstance(current_level[key], dict):
                current_level[key] = {} # Create intermediate dictionaries if they don't exist
            current_level = current_level[key]

        current_level[keys[-1]] = value
        if auto_save:
            self.save_settings()

    # Convenience methods for sections if needed (not strictly used by dialog in this plan)
    def get_section(self, section_name: str) -> dict:
        return self.settings.get(section_name, {}).copy() # Return a copy

    def set_section(self, section_name: str, section_data: dict, auto_save: bool = True):
        self.settings[section_name] = section_data
        if auto_save:
            self.save_settings()

if __name__ == '__main__':
    print("Testing SettingsManager...")
    # Use a temporary filename for testing to avoid overwriting real settings
    test_settings_file = "test_app_settings.json"
    manager = SettingsManager(settings_filename=test_settings_file)

    # Test 1: Default value for non-existent key
    print(f"Initial 'test.value1': {manager.get_setting('test.value1', 'default_val')}")
    assert manager.get_setting('test.value1', 'default_val') == 'default_val'

    # Test 2: Set and get a value
    manager.set_setting('test.value1', 123)
    print(f"Set 'test.value1' to 123. Retrieved: {manager.get_setting('test.value1')}")
    assert manager.get_setting('test.value1') == 123

    # Test 3: Set and get a nested value
    manager.set_setting('test.subsection.value2', "hello")
    print(f"Set 'test.subsection.value2' to 'hello'. Retrieved: {manager.get_setting('test.subsection.value2')}")
    assert manager.get_setting('test.subsection.value2') == "hello"

    # Test 4: Overwrite an existing value
    manager.set_setting('test.value1', 456)
    print(f"Overwrote 'test.value1' to 456. Retrieved: {manager.get_setting('test.value1')}")
    assert manager.get_setting('test.value1') == 456

    # Test 5: Load settings from file (requires settings to be saved first)
    print("Simulating app restart: creating new SettingsManager instance for the same file...")
    manager_reloaded = SettingsManager(settings_filename=test_settings_file)
    print(f"Reloaded 'test.value1': {manager_reloaded.get_setting('test.value1')}")
    assert manager_reloaded.get_setting('test.value1') == 456
    print(f"Reloaded 'test.subsection.value2': {manager_reloaded.get_setting('test.subsection.value2')}")
    assert manager_reloaded.get_setting('test.subsection.value2') == "hello"

    # Test 6: Section operations (optional, but good to have)
    manager.set_section("section1", {"a":1, "b":2})
    print(f"Section 'section1' data: {manager.get_section('section1')}")
    assert manager.get_section("section1") == {"a":1, "b":2}

    manager_reloaded_2 = SettingsManager(settings_filename=test_settings_file)
    assert manager_reloaded_2.get_section("section1") == {"a":1, "b":2}


    # Clean up the test settings file
    try:
        if Path(test_settings_file).exists(): Path(test_settings_file).unlink()
        # If using the .fractalapp directory, clean that up too for a clean test run next time
        app_data_dir_for_test = Path.home() / ".fractalapp"
        test_file_in_app_data = app_data_dir_for_test / test_settings_file
        if test_file_in_app_data.exists(): test_file_in_app_data.unlink()

        # Check if the directory is empty, then remove it
        # Be careful with this in a real scenario if other files might be there.
        # For testing, if we created it and it should only contain our test file, it's okay.
        # if app_data_dir_for_test.exists() and not any(app_data_dir_for_test.iterdir()):
        #     app_data_dir_for_test.rmdir()

        print(f"Test settings file '{test_settings_file}' (and potentially its app_data copy) cleaned up.")
    except Exception as e:
        print(f"Error cleaning up test settings file: {e}")

    print("SettingsManager test finished.")
