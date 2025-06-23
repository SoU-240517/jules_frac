import json
from pathlib import Path
import os

class SettingsManager:
    """
    アプリケーションの設定をJSONファイルで管理するクラス。

    設定の読み込み、保存、個別の設定値の取得・設定機能を提供します。
    ロガー(CustomLogger)との循環依存を避けるための特別な初期化パスも持ちます。
    """
    _logger_instance = None # ロガーインスタンスのクラス変数

    def _get_logger(self):
        """ロガーインスタンスを遅延初期化で取得します。"""
        if SettingsManager._logger_instance is None:
            from logger.custom_logger import CustomLogger # サイクルを断ち切るためにここにインポートする
            SettingsManager._logger_instance = CustomLogger()
        return SettingsManager._logger_instance

    def __init__(self, settings_filename: str = "settings.jsonc", _is_for_logger_init: bool = False):
        """
        SettingsManagerを初期化します。

        Args:
            settings_filename (str): 設定ファイルの名前またはパス。
                                     相対パスで指定された場合、ユーザーのホームディレクトリ下の
                                     `.fractalapp` フォルダ内にファイルパスを解決しようとします。
                                     解決に失敗した場合はカレントワーキングディレクトリ(CWD)を使用します。
            _is_for_logger_init (bool): CustomLoggerの初期化中に呼び出されたかどうかを示す内部フラグ。
                                        Trueの場合、ファイルI/Oや複雑なパス解決を避け、
                                        ロガーの循環依存を防ぐための最小限の初期化を行います。
        """
        print(f"SettingsManagerの初期化: settings_filename={settings_filename}, _is_for_logger_init={_is_for_logger_init}")
        if _is_for_logger_init:
            # CustomLogger初期化中の呼び出し: CWDのシンプルなパスを使用し、ファイルI/Oを避けます。
            # CustomLoggerはデフォルト値で初期化され、その後、アプリケーションのメインの
            # SettingsManagerインスタンスによって設定が更新されることを意図しています。
            self.filepath = Path.cwd() / settings_filename # 最小パス解像度
            self.settings = {} # 設定をロードせず、空の辞書を使用
        else:
            # 通常の初期化パス
            self.filepath = Path(settings_filename)
            print(f"設定ファイルの絶対パスの判定: {self.filepath.is_absolute()}")
            if not self.filepath.is_absolute():
                try:
                    home_dir = Path.home()
                    app_data_dir = home_dir / ".fractalapp"
                    app_data_dir.mkdir(parents=True, exist_ok=True)
                    print(f"ホームディレクトリ: {home_dir}, アプリデータディレクトリ: {app_data_dir}")
                    self.filepath = app_data_dir / settings_filename
                except Exception as e:
                    self._get_logger().log(f"ホームに設定ディレクトリを作成できませんでした。CWD を使用します。エラー: {e}", level="WARNING")
                    self.filepath = Path.cwd() / settings_filename

            self.settings: dict = {}
            self.load_settings() # 通常のインスタンスのみ設定をロード

    def load_settings(self):
        """
        設定ファイルから設定を読み込みます。
        ファイルが存在しない、または読み込みに失敗した場合は、空の設定を使用します。
        """
        if self.filepath.exists() and self.filepath.is_file():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                self._get_logger().log("設定ファイル読込完了", level="INFO")
            except (json.JSONDecodeError, IOError, Exception) as e: # より一般的な例外もキャッチします
                self._get_logger().log(f"設定ファイルの読込失敗: {e}。デフォルト設定を使用します。", level="ERROR")
                self.settings = {}
        else:
            self._get_logger().log("設定ファイルが見つかりません。デフォルト設定を使用します。", level="INFO")
            self.settings = {}

    def save_settings(self):
        """
        現在の設定をファイルに保存します。
        保存先のディレクトリが存在しない場合は作成します。
        """
        try:
            # 親ディレクトリが存在することを確認します
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            self._get_logger().log(f"設定を {self.filepath} に保存しました", level="INFO")
        except (IOError, Exception) as e: # より一般的な例外もキャッチします
            self._get_logger().log(f"設定ファイル '{self.filepath}' の保存に失敗しました: {e}", level="ERROR")

    def get_setting(self, key_path: str, default_value: any = None) -> any:
        """
        指定されたキーパスに対応する設定値を取得します。

        キーパスはドット区切りでネストされたキーを指定します (例: "window.width")。
        キーが存在しない場合や、パスの途中で非辞書型の値に遭遇した場合は、
        `default_value` を返します。

        Args:
            key_path (str): 取得したい設定のキーパス。
            default_value (any, optional): キーが存在しない場合に返すデフォルト値。Defaults to None.
        """
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
        """
        指定されたキーパスに設定値を設定します。

        キーパスはドット区切りでネストされたキーを指定します (例: "window.width")。
        途中のキーが存在しない場合は、新しい辞書が作成されます。

        Args:
            key_path (str): 設定したい値のキーパス。
            value (any): 設定する値。
            auto_save (bool, optional): Trueの場合、設定後に自動的に `save_settings` を呼び出します。Defaults to True.
        """
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
        """
        指定されたセクション名（トップレベルキー）の設定を辞書として取得します。

        セクションが存在しない場合は空の辞書を返します。
        返される辞書は元の設定のコピーです。

        Args:
            section_name (str): 取得したいセクションの名前。

        Returns:
            dict: セクションの設定データ、または空の辞書。
        """
        return self.settings.get(section_name, {}).copy() # コピーを返します

    def set_section(self, section_name: str, section_data: dict, auto_save: bool = True):
        """
        指定されたセクション名（トップレベルキー）に新しい設定データを設定します。

        Args:
            section_name (str): 設定したいセクションの名前。
            section_data (dict): 設定するデータ。
            auto_save (bool, optional): Trueの場合、設定後に自動的に `save_settings` を呼び出します。Defaults to True.
        """
        self.settings[section_name] = section_data
        if auto_save:
            self.save_settings()

    def get_presets(self) -> dict:
        """保存されているすべてのプリセットを取得します。"""
        return self.get_setting("presets", {})

    def save_preset(self, name: str, config: dict):
        """指定された名前でプリセットを保存します。"""
        presets = self.get_presets()
        presets[name] = config
        self.set_setting("presets", presets)

    def delete_preset(self, name: str):
        """指定された名前のプリセットを削除します。"""
        presets = self.get_presets()
        if name in presets:
            del presets[name]
            self.set_setting("presets", presets)
            self._get_logger().log(f"プリセット '{name}' を設定から削除しました。", "DEBUG")

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
