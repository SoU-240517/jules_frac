import json
from pathlib import Path
import os
import re # 追加: 正規表現モジュールをインポート

from typing import Any, Dict, Optional

class SettingsManager:
    """
    アプリケーションの設定をJSONファイルで管理するクラス。

    設定の読み込み、保存、個別の設定値の取得・設定機能を提供します。
    ロガー(CustomLogger)との循環依存を避けるための特別な初期化パスも持ちます。
    """
    _logger_instance = None # ロガーインスタンスのクラス変数

    @staticmethod
    def _to_relpath(path):
        try:
            from logger.custom_logger import CustomLogger
            prj = getattr(CustomLogger, '_project_root_path', None)
            if prj and Path(path).is_absolute():
                return str(Path(path).relative_to(prj))
        except Exception:
            pass
        return str(path)

    def _get_logger(self) -> object:
        """ロガーインスタンスを遅延初期化で取得します。"""
        # SettingsManager._logger_instance は CustomLogger が自身を初期化する際に設定されることを想定しています。
        # ここで CustomLogger を直接インスタンス化すると循環参照が発生します。
        if SettingsManager._logger_instance is None:
            # ロガーがまだ設定されていない場合、フォールバックロガーを使用します。
            # これは、CustomLogger がまだ初期化されていないか、利用できない場合に発生します。
            class FallbackLogger:
                def log(self, message: str, level: str = "INFO"):
                    print(f"[{level}] {message}") # シンプルなprintで出力
                def set_level(self, level: str): pass
                def set_enabled(self, enabled: bool): pass
                def set_project_root(self, path: Path): pass
            SettingsManager._logger_instance = FallbackLogger()
        return SettingsManager._logger_instance

    def __init__(self, settings_filename: str = "settings.jsonc", _is_for_logger_init: bool = False) -> None:
        """
        SettingsManagerを初期化します。

        :param settings_filename: 設定ファイルの名前またはパス。相対パスの場合、ユーザーのホームディレクトリ下の
                                  `.fractalapp` フォルダ内にファイルパスを解決しようとします。
                                  解決に失敗した場合はカレントワーキングディレクトリ(CWD)を使用します。
        :param _is_for_logger_init: CustomLoggerの初期化中に呼び出されたかどうかを示す内部フラグ。
                                    Trueの場合、ファイルI/Oや複雑なパス解決を避け、
                                    ロガーの循環依存を防ぐための最小限の初期化を行います。
        """
        logger = self._get_logger()
        logger.log(f"SettingsManagerの初期化開始: settings_filename='{SettingsManager._to_relpath(settings_filename)}', _is_for_logger_init={_is_for_logger_init}", level="DEBUG")

        if _is_for_logger_init:
            # CustomLogger初期化中の呼び出し: CWDのシンプルなパスを使用し、ファイルI/Oを避けます。
            # CustomLoggerはデフォルト値で初期化され、その後、アプリケーションのメインの
            # SettingsManagerインスタンスによって設定が更新されることを意図しています。
            self.filepath = Path.cwd() / settings_filename # 最小パス解像度
            self.settings: Dict[str, Any] = {} # 設定をロードせず、空の辞書を使用
            logger.log("ロガー初期化モードでSettingsManagerを初期化しました。", level="DEBUG")
        else:
            # 通常の初期化パス
            initial_filepath = Path(settings_filename)
            # ログ用にパスを相対パスへ変換
            logger.log(f"設定ファイルの初期パス: '{SettingsManager._to_relpath(initial_filepath)}'", level="DEBUG")

            if not initial_filepath.is_absolute():
                try:
                    home_dir = Path.home()
                    app_data_dir = home_dir / ".fractalapp"
                    app_data_dir.mkdir(parents=True, exist_ok=True)
                    self.filepath = app_data_dir / settings_filename
                    logger.log(f"設定ファイルをユーザーデータディレクトリに解決しました: '{SettingsManager._to_relpath(self.filepath)}'", level="DEBUG")
                except Exception as e:
                    self._get_logger().log(f"ホームに設定ディレクトリを作成できませんでした。CWD を使用します。エラー: {e}", level="WARNING")
                    self.filepath = Path.cwd() / settings_filename
            else:
                self.filepath = initial_filepath
                logger.log(f"設定ファイルは絶対パスで指定されました: '{SettingsManager._to_relpath(self.filepath)}'", level="DEBUG")

            self.settings: Dict[str, Any] = {}
            self.load_settings() # 通常のインスタンスのみ設定をロード

    def load_settings(self) -> None:
        """
        設定ファイルから設定を読み込みます。
        ファイルが存在しない、または読み込みに失敗した場合は、空の設定を使用します。
        """
        logger = self._get_logger()
        if self.filepath.exists() and self.filepath.is_file():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # JSONCコメントを削除 (行コメントのみ対応)
                content_without_comments = re.sub(r"//.*", "", content)
                self.settings = json.loads(content_without_comments)
                logger.log(f"設定ファイル '{SettingsManager._to_relpath(self.filepath)}' の読み込み完了。", level="INFO")
            except json.JSONDecodeError as e:
                logger.log(f"設定ファイル '{SettingsManager._to_relpath(self.filepath)}' のJSON形式が不正です: {e}。デフォルト設定を使用します。", level="ERROR")
                self.settings = {}
            except IOError as e:
                logger.log(f"設定ファイル '{SettingsManager._to_relpath(self.filepath)}' の読み込み中にI/Oエラーが発生しました: {e}。デフォルト設定を使用します。", level="ERROR")
                self.settings = {}
            except Exception as e: # その他の予期せぬエラー
                logger.log(f"設定ファイル '{SettingsManager._to_relpath(self.filepath)}' の読み込み中に予期せぬエラーが発生しました: {e}。デフォルト設定を使用します。", level="ERROR")
                self.settings = {}
        else:
            logger.log(f"設定ファイル '{SettingsManager._to_relpath(self.filepath)}' が見つかりません。デフォルト設定を使用します。", level="INFO")
            self.settings = {}

    def save_settings(self) -> None:
        """
        現在の設定をファイルに保存します。
        保存先のディレクトリが存在しない場合は作成します。
        """
        logger = self._get_logger()
        try:
            # self.settings 全体を保存（engine_settings, presets も含む）
            settings_to_save = self.settings.copy()
            # 親ディレクトリが存在することを確認します
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
            logger.log(f"設定を '{SettingsManager._to_relpath(self.filepath)}' に保存しました。", level="INFO")
        except (IOError, Exception) as e: # より一般的な例外もキャッチします
            logger.log(f"設定ファイル '{SettingsManager._to_relpath(self.filepath)}' の保存に失敗しました: {e}", level="ERROR")

    def get_all_settings(self) -> Dict[str, Any]:
        """
        現在のすべての設定を辞書として取得します。

        返される辞書は元の設定のコピーです。

        Returns:
            Dict[str, Any]: すべての設定データ。
        """
        return self.settings.copy()

    def get_setting(self, key_path: str, default_value: Any = None) -> Any:
        """
        指定されたキーパスに対応する設定値を取得します。

        キーパスはドット区切りでネストされたキーを指定します (例: "window.width")。
        キーが存在しない場合や、パスの途中で非辞書型の値に遭遇した場合は、
        `default_value` を返します。

        Args:
            key_path (str): 取得したい設定のキーパス。
            default_value (Any, optional): キーが存在しない場合に返すデフォルト値。デフォルトは None。
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


    def set_setting(self, key_path: str, value: Any, auto_save: bool = True) -> None:
        """
        指定されたキーパスに設定値を設定します。

        キーパスはドット区切りでネストされたキーを指定します (例: "window.width")。
        途中のキーが存在しない場合は、新しい辞書が作成されます。

        :param key_path: 設定したい値のキーパス。
        :param value: 設定する値。
        :param auto_save: Trueの場合、設定後に自動的に `save_settings` を呼び出します。デフォルトは True。
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

    def get_section(self, section_name: str) -> Dict[str, Any]:
        """
        指定されたセクション名（トップレベルキー）の設定を辞書として取得します。

        セクションが存在しない場合は空の辞書を返します。
        返される辞書は元の設定のコピーです。

        :param section_name: 取得したいセクションの名前。

        Returns:
            dict: セクションの設定データ、または空の辞書。
        """
        return self.settings.get(section_name, {}).copy() # コピーを返します

    def set_section(self, section_name: str, section_data: Dict[str, Any], auto_save: bool = True) -> None:
        """
        指定されたセクション名（トップレベルキー）に新しい設定データを設定します。

        :param section_name: 設定したいセクションの名前。
        :param section_data: 設定するデータ。
        :param auto_save: Trueの場合、設定後に自動的に `save_settings` を呼び出します。デフォルトは True。
        """
        self.settings[section_name] = section_data
        if auto_save:
            self.save_settings()

    def export_presets_to_file(self, filepath: Path) -> None:
        """
        現在のすべてのプリセットを指定されたファイルにJSON形式でエクスポートします。
        :param filepath: エクスポート先のファイルパス。
        :raises Exception: ファイル操作中にエラーが発生した場合。
        """
        logger = self._get_logger()
        presets_data = self.get_presets()
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(presets_data, f, indent=4, ensure_ascii=False)
            logger.log(f"プリセットを '{SettingsManager._to_relpath(filepath)}' にエクスポートしました。", "INFO")
        except Exception as e:
            logger.log(f"プリセットのエクスポート中にエラーが発生しました: {e}", level="ERROR")
            raise # コントローラーでキャッチするために再スロー

    def import_presets_from_file(self, filepath: Path, overwrite: bool = False) -> list[str]:
        """
        指定されたJSONファイルからプリセットを読み込み、現在の設定にマージします。
        :param filepath: インポートするJSONファイルのパス。
        :param overwrite: 既存の同名プリセットを上書きするかどうか。
        :return: インポートされたプリセットの名前のリスト。
        :raises Exception: ファイルの読み込み、解析、またはマージ中にエラーが発生した場合。
        """
        logger = self._get_logger()
        if not filepath.exists():
            logger.log(f"インポートファイル '{SettingsManager._to_relpath(filepath)}' が見つかりません。", level="WARNING")
            return []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_data = json.load(f) # type: ignore
            if not isinstance(imported_data, dict):
                raise ValueError("インポートファイルの内容が有効なJSONオブジェクトではありません。")

            current_presets = self.get_presets()
            imported_names = []
            for name, config in imported_data.items():
                if overwrite or name not in current_presets:
                    current_presets[name] = config
                    imported_names.append(name)

            self.set_setting("presets", current_presets) # 変更を保存
            logger.log(f"{len(imported_names)} 個のプリセットをインポートしました。", level="INFO")
            return imported_names
        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.log(f"プリセットのインポート中にエラーが発生しました: {e}", level="ERROR")
            raise # コントローラーでキャッチするために再スロー
        except Exception as e:
            logger.log(f"プリセットのインポート中に予期せぬエラーが発生しました: {e}", level="ERROR")
            raise # コントローラーでキャッチするために再スロー


    def get_presets(self) -> Dict[str, Any]:
        """保存されているすべてのプリセットを取得します。"""
        return self.get_setting("presets", {})

    def save_preset(self, name: str, config: Dict[str, Any]) -> None:
        """指定された名前でプリセットを保存します。"""
        presets = self.get_presets()
        presets[name] = config
        self.set_setting("presets", presets)

    def delete_preset(self, name: str) -> None:
        """指定された名前のプリセットを削除します。"""
        logger = self._get_logger()
        presets = self.get_presets()
        if name in presets:
            del presets[name]
            self.set_setting("presets", presets) # auto_save=True なので自動保存される
            logger.log(f"プリセット '{name}' を設定から削除しました。", level="DEBUG")
        else:
            logger.log(f"プリセット '{name}' が見つかりませんでした。削除はスキップされました。", level="WARNING")

if __name__ == '__main__':
    # __main__ のテストでは、SettingsManager が自身のロガーをインスタンス化できるように、
    # CustomLogger が利用可能であると仮定します。
    # このテストブロックは、SettingsManager のコア機能のテストに焦点を当てています。
    from logger.custom_logger import CustomLogger
    _main_logger = CustomLogger()
    _main_logger.set_level("DEBUG") # テスト中は詳細なログを出力

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

    # テスト 7: 新しい構造のキーパスのテスト
    _main_logger.log("新しい構造のキーパスのテスト...", level="INFO")
    manager.set_setting("application.logging.level", "WARNING")
    assert manager.get_setting("application.logging.level") == "WARNING"
    manager.set_setting("ui.window.width", 1920)
    assert manager.get_setting("ui.window.width") == 1920
    manager.set_setting("workspace.common_parameters.max_iterations", 200)
    assert manager.get_setting("workspace.common_parameters.max_iterations") == 200
    manager.set_setting("application.save_workspace_on_exit", True)
    assert manager.get_setting("application.save_workspace_on_exit") == True

    # テスト 8: プリセットの保存と取得
    _main_logger.log("プリセットのテスト...", level="INFO")
    test_preset_config = {
        "common_parameters": {"center_real": 0.1, "max_iterations": 1000},
        "fractal_plugin_name": "Julia"
    }
    manager.save_preset("MyTestPreset", test_preset_config)
    retrieved_preset = manager.get_setting("presets.MyTestPreset")
    _main_logger.log(f"保存されたプリセット 'MyTestPreset': {retrieved_preset}", level="DEBUG")
    assert retrieved_preset == test_preset_config

    # テスト 9: プリセットの削除
    manager.delete_preset("MyTestPreset")
    assert manager.get_setting("presets.MyTestPreset") is None
    _main_logger.log("プリセット 'MyTestPreset' を削除しました。", level="DEBUG")

    # テスト 10: プリセットのエクスポートとインポート
    _main_logger.log("プリセットのエクスポート/インポートテスト...", level="INFO")
    manager.save_preset("ExportTest1", {"val": 1})
    manager.save_preset("ExportTest2", {"val": 2})
    export_file = Path("exported_presets.json")
    manager.export_presets_to_file(export_file)
    _main_logger.log(f"プリセットを '{SettingsManager._to_relpath(export_file)}' にエクスポートしました。", level="INFO")

    # 新しいマネージャーでインポートをシミュレート
    manager_import = SettingsManager(settings_filename=test_settings_file)
    imported_names = manager_import.import_presets_from_file(export_file)
    _main_logger.log(f"インポートされたプリセット: {imported_names}", level="INFO")
    assert "ExportTest1" in manager_import.get_presets()
    assert "ExportTest2" in manager_import.get_presets()
    assert len(imported_names) == 2

    # 上書きテスト
    manager_import.save_preset("ExportTest1", {"val": 100}) # 既存の値を変更
    imported_names_overwrite = manager_import.import_presets_from_file(export_file, overwrite=True)
    assert manager_import.get_setting("presets.ExportTest1.val") == 1 # 上書きされたことを確認
    _main_logger.log(f"上書きインポートされたプリセット: {imported_names_overwrite}", level="INFO")

    # テスト設定ファイルをクリーンアップ
    try:
        if Path(test_settings_file).exists(): Path(test_settings_file).unlink()
        app_data_dir_for_test = Path.home() / ".fractalapp"
        test_file_in_app_data = app_data_dir_for_test / test_settings_file
        if test_file_in_app_data.exists(): test_file_in_app_data.unlink()
        if export_file.exists(): export_file.unlink()

        _main_logger.log(f"テスト設定ファイル '{test_settings_file}' および '{export_file}' (および潜在的な app_data コピー) をクリーンアップしました。", level="INFO")
    except Exception as e:
        _main_logger.log(f"テスト設定ファイルのクリーンアップ中にエラーが発生しました: {e}", level="ERROR")

    _main_logger.log("SettingsManager のテストが完了しました。", level="INFO")
