import json
from pathlib import Path
import os

class SettingsManager:
    def __init__(self, settings_filename: str = "base_settings.json"):
        # 標準的なアプリケーションデータディレクトリの使用を検討してください
        # 簡単のため、現在の作業ディレクトリまたは指定されたパスを使用します
        # settings_filename が単なる名前の場合、CWD に作成されます。
        # パスの場合、そのまま使用されます。
        self.filepath = Path(settings_filename)
        if not self.filepath.is_absolute():
            # 相対パスが指定された場合、CWD または定義されたアプリデータディレクトリからの相対パスにします。
            # この例では、ファイル名のみが指定された場合、CWD が使用されます。
            # より堅牢な解決策は、QStandardPaths または appdirs を使用することです。
            try:
                # 異なる場所からの実行間で永続性を保つために、ユーザーのホームディレクトリに配置しようとします
                home_dir = Path.home()
                app_data_dir = home_dir / ".fractalapp" # 隠しフォルダの例
                app_data_dir.mkdir(parents=True, exist_ok=True)
                self.filepath = app_data_dir / settings_filename
            except Exception as e:
                print(f"SettingsManager 警告: ホームに設定ディレクトリを作成できませんでした。CWD を使用します。エラー: {e}")
                self.filepath = Path.cwd() / settings_filename


        self.settings: dict = {}
        self.load_settings()

    def load_settings(self):
        if self.filepath.exists() and self.filepath.is_file():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                print(f"SettingsManager: 設定を {self.filepath} から読み込みました")
            except (json.JSONDecodeError, IOError, Exception) as e: # より一般的な例外もキャッチします
                print(f"SettingsManager エラー: 設定ファイル '{self.filepath}' の読み込みに失敗しました: {e}。デフォルト設定を使用します。")
                self.settings = {}
        else:
            print(f"SettingsManager: 設定ファイル ('{self.filepath}') が見つかりません。デフォルト設定を使用します。")
            self.settings = {}

    def save_settings(self):
        try:
            # 親ディレクトリが存在することを確認します
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            print(f"SettingsManager: 設定を {self.filepath} に保存しました")
        except (IOError, Exception) as e: # より一般的な例外もキャッチします
            print(f"SettingsManager エラー: 設定ファイル '{self.filepath}' の保存に失敗しました: {e}")

    def get_setting(self, key_path: str, default_value: any = None) -> any:
        keys = key_path.split('.')
        value_ptr = self.settings
        try:
            for key in keys:
                if not isinstance(value_ptr, dict): # パスセグメントが辞書でない場合
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
                current_level[key] = {} # 存在しない場合は中間辞書を作成します
            current_level = current_level[key]

        current_level[keys[-1]] = value
        if auto_save:
            self.save_settings()

    # 必要に応じてセクション用の便利なメソッド (この計画ではダイアログでは厳密には使用されません)
    def get_section(self, section_name: str) -> dict:
        return self.settings.get(section_name, {}).copy() # コピーを返します

    def set_section(self, section_name: str, section_data: dict, auto_save: bool = True):
        self.settings[section_name] = section_data
        if auto_save:
            self.save_settings()

if __name__ == '__main__':
    print("SettingsManager のテスト中...")
    # 実際の設定を上書きしないように、テスト用に一時的なファイル名を使用します
    test_settings_file = "test_app_settings.json"
    manager = SettingsManager(settings_filename=test_settings_file)

    # テスト 1: 存在しないキーのデフォルト値
    print(f"初期 'test.value1': {manager.get_setting('test.value1', 'default_val')}")
    assert manager.get_setting('test.value1', 'default_val') == 'default_val'

    # テスト 2: 値の設定と取得
    manager.set_setting('test.value1', 123)
    print(f"'test.value1' を 123 に設定。取得値: {manager.get_setting('test.value1')}")
    assert manager.get_setting('test.value1') == 123

    # テスト 3: ネストされた値の設定と取得
    manager.set_setting('test.subsection.value2', "hello")
    print(f"'test.subsection.value2' を 'hello' に設定。取得値: {manager.get_setting('test.subsection.value2')}")
    assert manager.get_setting('test.subsection.value2') == "hello"

    # テスト 4: 既存の値の上書き
    manager.set_setting('test.value1', 456)
    print(f"'test.value1' を 456 に上書き。取得値: {manager.get_setting('test.value1')}")
    assert manager.get_setting('test.value1') == 456

    # テスト 5: ファイルから設定を読み込み (最初に設定を保存する必要があります)
    print("アプリの再起動をシミュレート: 同じファイルに対して新しい SettingsManager インスタンスを作成中...")
    manager_reloaded = SettingsManager(settings_filename=test_settings_file)
    print(f"再読み込みされた 'test.value1': {manager_reloaded.get_setting('test.value1')}")
    assert manager_reloaded.get_setting('test.value1') == 456
    print(f"再読み込みされた 'test.subsection.value2': {manager_reloaded.get_setting('test.subsection.value2')}")
    assert manager_reloaded.get_setting('test.subsection.value2') == "hello"

    # テスト 6: セクション操作 (オプションですが、あると便利です)
    manager.set_section("section1", {"a":1, "b":2})
    print(f"セクション 'section1' のデータ: {manager.get_section('section1')}")
    assert manager.get_section("section1") == {"a":1, "b":2}

    manager_reloaded_2 = SettingsManager(settings_filename=test_settings_file)
    assert manager_reloaded_2.get_section("section1") == {"a":1, "b":2}


    # Clean up the test settings file
    # テスト設定ファイルをクリーンアップします
    try:
        if Path(test_settings_file).exists(): Path(test_settings_file).unlink()
        # .fractalapp ディレクトリを使用している場合は、次回のクリーンなテスト実行のためにそれもクリーンアップします
        app_data_dir_for_test = Path.home() / ".fractalapp"
        test_file_in_app_data = app_data_dir_for_test / test_settings_file
        if test_file_in_app_data.exists(): test_file_in_app_data.unlink()

        # ディレクトリが空かどうかを確認し、空であれば削除します
        # 他のファイルが存在する可能性がある実際のシナリオでは注意してください。
        # テストの場合、作成し、テストファイルのみが含まれるべきであれば問題ありません。
        # if app_data_dir_for_test.exists() and not any(app_data_dir_for_test.iterdir()):
        #     app_data_dir_for_test.rmdir()

        print(f"テスト設定ファイル '{test_settings_file}' (および潜在的な app_data コピー) をクリーンアップしました。")
    except Exception as e:
        print(f"テスト設定ファイルのクリーンアップ中にエラーが発生しました: {e}")

    print("SettingsManager のテストが完了しました。")
