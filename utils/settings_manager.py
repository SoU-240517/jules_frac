import json
from pathlib import Path
import os
# from logger.custom_logger import CustomLogger # logger がプロジェクトルート/loggerにあると仮定
# logger = CustomLogger() # DEFERRED to break circular import

class SettingsManager:
    _logger_instance = None # Class variable for the logger instance

    def _get_logger(self):
        """ロガーインスタンスを遅延初期化で取得します。"""
        if SettingsManager._logger_instance is None:
            from logger.custom_logger import CustomLogger # Import here to break cycle
            SettingsManager._logger_instance = CustomLogger()
        return SettingsManager._logger_instance

    def __init__(self, settings_filename: str = "base_settings.json", _is_for_logger_init: bool = False):
        """
        SettingsManager を初期化します。

        Args:
            settings_filename (str): 設定ファイルの名前またはパス。
            _is_for_logger_init (bool): CustomLoggerの初期化中に呼び出されたかどうかを示す内部フラグ。
                                       Trueの場合、ファイルパス解決とロギングの複雑なロジックをバイパスします。
        """
        if _is_for_logger_init:
            # CustomLogger初期化中の呼び出し: CWDのシンプルなパスを使用し、ファイルI/Oを避けます。
            # CustomLoggerはデフォルト値で初期化され、その後、アプリケーションのメインの
            # SettingsManagerインスタンスによって設定が更新されることを意図しています。
            self.filepath = Path.cwd() / settings_filename # Minimal path resolution
            self.settings = {} # 設定をロードせず、空の辞書を使用
            # print(f"DEBUG: SettingsManager (for logger init) - filepath: {self.filepath}, settings empty, skipping load.")
        else:
            # 通常の初期化パス
            self.filepath = Path(settings_filename)
            if not self.filepath.is_absolute():
                try:
                    home_dir = Path.home()
                    app_data_dir = home_dir / ".fractalapp"
                    app_data_dir.mkdir(parents=True, exist_ok=True)
                    self.filepath = app_data_dir / settings_filename
                except Exception as e:
                    self._get_logger().log(f"ホームに設定ディレクトリを作成できませんでした。CWD を使用します。エラー: {e}", level="WARNING")
                    self.filepath = Path.cwd() / settings_filename

            self.settings: dict = {}
            self.load_settings() # 通常のインスタンスのみ設定をロード

    def load_settings(self):
        if self.filepath.exists() and self.filepath.is_file():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                self._get_logger().log(f"設定を {self.filepath} から読み込みました", level="INFO")
            except (json.JSONDecodeError, IOError, Exception) as e: # より一般的な例外もキャッチします
                self._get_logger().log(f"設定ファイル '{self.filepath}' の読み込みに失敗しました: {e}。デフォルト設定を使用します。", level="ERROR")
                self.settings = {}
        else:
            self._get_logger().log(f"設定ファイル ('{self.filepath}') が見つかりません。デフォルト設定を使用します。", level="INFO")
            self.settings = {}

    def save_settings(self):
        try:
            # 親ディレクトリが存在することを確認します
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            self._get_logger().log(f"設定を {self.filepath} に保存しました", level="INFO")
        except (IOError, Exception) as e: # より一般的な例外もキャッチします
            self._get_logger().log(f"設定ファイル '{self.filepath}' の保存に失敗しました: {e}", level="ERROR")

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
        except TypeError: # value_ptrが予期せずNoneまたは非辞書になった場合のケースを処理
             return default_value


    def set_setting(self, key_path: str, value: any, auto_save: bool = True):
        keys = key_path.split('.')
        current_level = self.settings

        for i, key in enumerate(keys[:-1]): # 最後から2番目のキーまで反復
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

    def get_logging_settings(self) -> dict:
        """
        ログ設定を取得します。存在しない場合はデフォルト値を返します。

        Returns:
            dict: logging.level (str) と logging.enabled (bool) を含む辞書。
        """
        default_settings = {"level": "INFO", "enabled": True}
        if not self.settings: # settingsが空の場合 (ファイルが存在しないか、読み込みに失敗した場合)
            return default_settings

        logging_section = self.settings.get("logging", default_settings)

        # loggingセクションが存在するが、キーが不足している場合に備えて、各キーのデフォルト値を確認します
        return {
            "level": logging_section.get("level", default_settings["level"]),
            "enabled": logging_section.get("enabled", default_settings["enabled"])
        }

if __name__ == '__main__':
    # __main__ のテストでは、SettingsManager が自身のロガーをインスタンス化できるように、
    # CustomLogger が利用可能であると仮定します。
    # これは、CustomLogger が SettingsManager を使用する本番シナリオとは逆です。
    # このテストブロックは、SettingsManager のコア機能のテストに焦点を当てています。
    _main_logger = SettingsManager()._get_logger() # テスト用のロガーを取得

    _main_logger.log("SettingsManager のテスト中...", level="INFO")
    # 実際の設定を上書きしないように、テスト用に一時的なファイル名を使用します
    test_settings_file = "test_app_settings.json"
    manager = SettingsManager(settings_filename=test_settings_file)

    # テスト 1: 存在しないキーのデフォルト値
    _main_logger.log(f"初期 'test.value1': {manager.get_setting('test.value1', 'default_val')}", level="DEBUG")
    assert manager.get_setting('test.value1', 'default_val') == 'default_val'

    # テスト 2: 値の設定と取得
    manager.set_setting('test.value1', 123)
    _main_logger.log(f"'test.value1' を 123 に設定。取得値: {manager.get_setting('test.value1')}", level="DEBUG")
    assert manager.get_setting('test.value1') == 123

    # テスト 3: ネストされた値の設定と取得
    manager.set_setting('test.subsection.value2', "hello")
    _main_logger.log(f"'test.subsection.value2' を 'hello' に設定。取得値: {manager.get_setting('test.subsection.value2')}", level="DEBUG")
    assert manager.get_setting('test.subsection.value2') == "hello"

    # テスト 4: 既存の値の上書き
    manager.set_setting('test.value1', 456)
    _main_logger.log(f"'test.value1' を 456 に上書き。取得値: {manager.get_setting('test.value1')}", level="DEBUG")
    assert manager.get_setting('test.value1') == 456

    # テスト 5: ファイルから設定を読み込み (最初に設定を保存する必要があります)
    _main_logger.log("アプリの再起動をシミュレート: 同じファイルに対して新しい SettingsManager インスタンスを作成中...", level="INFO")
    manager_reloaded = SettingsManager(settings_filename=test_settings_file)
    _main_logger.log(f"再読み込みされた 'test.value1': {manager_reloaded.get_setting('test.value1')}", level="DEBUG")
    assert manager_reloaded.get_setting('test.value1') == 456
    _main_logger.log(f"再読み込みされた 'test.subsection.value2': {manager_reloaded.get_setting('test.subsection.value2')}", level="DEBUG")
    assert manager_reloaded.get_setting('test.subsection.value2') == "hello"

    # テスト 6: セクション操作 (オプションですが、あると便利です)
    manager.set_section("section1", {"a":1, "b":2})
    _main_logger.log(f"セクション 'section1' のデータ: {manager.get_section('section1')}", level="DEBUG")
    assert manager.get_section("section1") == {"a":1, "b":2}

    manager_reloaded_2 = SettingsManager(settings_filename=test_settings_file)
    assert manager_reloaded_2.get_section("section1") == {"a":1, "b":2}


    # テスト設定ファイルをクリーンアップ
    # テスト設定ファイルをクリーンアップします
    try:
        if Path(test_settings_file).exists(): Path(test_settings_file).unlink()
        # .fractalapp ディレクトリを使用している場合は、次回のクリーンなテスト実行のためにそれもクリーンアップします
        app_data_dir_for_test = Path.home() / ".fractalapp"
        # SettingsManagerの初期化ロジックは、settings_filenameが単純な名前の場合、
        # このテストファイル (test_app_settings.json) を app_data_dir に作成する可能性があるため、
        # その場所で確認して削除します。
        test_file_in_app_data = app_data_dir_for_test / test_settings_file
        if test_file_in_app_data.exists(): test_file_in_app_data.unlink()

        # ディレクトリが空かどうかを確認し、空であれば削除します
        # 他のファイルが存在する可能性がある実際のシナリオでは注意してください。
        # テストの場合、作成し、テストファイルのみが含まれるべきであれば問題ありません。
        # if app_data_dir_for_test.exists() and not any(app_data_dir_for_test.iterdir()):
        #     app_data_dir_for_test.rmdir()

        _main_logger.log(f"テスト設定ファイル '{test_settings_file}' (および潜在的な app_data コピー) をクリーンアップしました。", level="INFO")
    except Exception as e:
        _main_logger.log(f"テスト設定ファイルのクリーンアップ中にエラーが発生しました: {e}", level="ERROR")

    _main_logger.log("SettingsManager のテストが完了しました。", level="INFO")
