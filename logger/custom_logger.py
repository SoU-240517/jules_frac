import time
import inspect
from pathlib import Path
import sys # exc_infoフォールバック用に追加
import traceback # exc_info用に追加

class CustomLogger:
    """
    カスタムロガーシングルトンクラス。
    経過時間、呼び出し元情報、設定可能なログレベル、有効/無効スイッチを含むフォーマットされたログメッセージを出力します。
    設定は SettingsManager から読み込まれます。
    """
    _instance = None
    _start_time = None # ロガーの最初のインスタンス化からの開始時刻
    _initializing = False # 初期化中の循環呼び出しを防ぐためのフラグ

    LOG_LEVELS = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }
    LOG_COLORS = {
        "DEBUG": "\033[94m",  # 青
        "INFO": "\033[92m",  # 緑
        "WARNING": "\033[93m",  # 黄
        "ERROR": "\033[91m",  # 赤
        "CRITICAL": "\033[91m\033[1m",  # 太字赤 (例)
        "DIM_GRAY": "\033[90m", # 暗いグレー (明るい黒)
    }
    RESET_COLOR = "\033[0m"
    _current_level_int: int
    _is_enabled: bool
    _log_file_path: Path | None = None
    _project_root_path: Path | None = None # プロジェクトルートパスを保持するクラス変数

    def __new__(cls, *args, **kwargs) -> 'CustomLogger':
        """シングルトンインスタンスを作成または返します。初回作成時に初期化を行います。"""
        if not cls._instance:
            cls._initializing = True # 初期化開始のフラグを設定

            instance = super(CustomLogger, cls).__new__(cls)

            # _start_time は最初のインスタンス作成時に一度だけ設定
            if cls._start_time is None:
                cls._start_time = time.time()

            # SettingsManagerに自身を登録する
            # これにより、SettingsManagerがロガーを必要としたときに、
            # 既に初期化中のCustomLoggerインスタンスを利用できるようになる。
            # 循環インポートを避けるため、ここでインポートする
            from utils.settings_manager import SettingsManager
            SettingsManager._logger_instance = instance # 自身をSettingsManagerに登録

            # クラス属性として基本的なデフォルト値を設定。
            # これらは設定ファイルから読み込めない場合の最終フォールバック。
            # SettingsManagerの初期化中にロギングが発生しても、基本的なロギング状態が保証される。
            cls._current_level_int = cls.LOG_LEVELS.get("INFO", 20)
            cls._is_enabled = True
            cls._log_file_path = Path("/tmp/app.log") # デフォルトのログファイルパス

            instance._configure_from_settings() # 設定ファイルからの読み込みと適用

            cls._instance = instance
            cls._initializing = False # 初期化終了のフラグを解除
        return cls._instance

    def __init__(self) -> None:
        # シングルトンなので、__new__ で全ての初期化を完結させるため、__init__ では何もしない。
        pass

    def _configure_from_settings(self) -> None:
        """
        SettingsManagerから設定を読み込み、シングルトンのクラス属性に適用します。
        このメソッドは __new__ から一度だけ、最初のインスタンス作成時に呼び出されます。
        """
        # SettingsManager は既に __new__ でインポートされ、CustomLogger が登録されているため、
        # ここで再度インポートしても循環は発生しない。
        from utils.settings_manager import SettingsManager
        try:
            # SettingsManager のインスタンス化時にロギングが発生する可能性があるため、
            # _initializing フラグが CustomLogger.log() でチェックされることが重要です。
            settings_manager = SettingsManager(settings_filename="settings.jsonc", _is_for_logger_init=True) # SettingsManager は自身のロガーを使用する可能性があります

            # SettingsManagerから "logging" 設定を取得するためのデフォルト値を定義
            # このデフォルト値は、settings_manager.get_setting の第2引数として使用される。
            # 新しい設定構造 "application.logging" に対応。
            default_config_for_sm = {
                "level": "INFO",
                "enabled": True,
                "file": str(CustomLogger._log_file_path) # 初期デフォルトのファイルパス
            }
            # settings_manager.get_setting を使用して "logging" セクションを取得
            logging_config = settings_manager.get_setting("application.logging", default_config_for_sm)

            # logging_config (辞書) から各値を取得。存在しない場合はフォールバック値を使用。
            level_to_set_str = logging_config.get("level", "INFO").upper()
            enabled_setting = logging_config.get("enabled", True)

            # enabled 設定の型をboolに正規化 (JSONでは文字列で "true"/"false" が来る可能性も考慮)
            if isinstance(enabled_setting, str):
                current_enabled_bool = enabled_setting.lower() == "true"
            elif isinstance(enabled_setting, bool):
                current_enabled_bool = enabled_setting
            else: # 不明な型やNoneの場合はデフォルト True
                current_enabled_bool = True

            log_file_from_settings = logging_config.get("file") # 設定ファイル内のキーを "file" と想定

            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS.get(level_to_set_str, CustomLogger.LOG_LEVELS["INFO"])
            CustomLogger._is_enabled = current_enabled_bool

            if log_file_from_settings:
                CustomLogger._log_file_path = Path(log_file_from_settings)

            # ログファイルパスがNoneでなく、親ディレクトリが存在しない場合に作成
            if CustomLogger._log_file_path and CustomLogger._log_file_path.parent:
                 CustomLogger._log_file_path.parent.mkdir(parents=True, exist_ok=True)

            # ログが有効であれば、設定適用完了をログに出力
            if CustomLogger._is_enabled:
                self.log(f"CustomLogger: 設定ファイルからロガー設定を適用しました。レベル: {level_to_set_str}, 有効: {enabled_setting}, ファイル: {CustomLogger._log_file_path}", level="INFO")

        except Exception as e:
            # 初期化中にエラーが発生した場合のフォールバック (標準エラーに出力)
            # SettingsManager._logger_instance は既に設定されているため、log() メソッドを呼び出すことも可能。
            # ここでは、エラー発生時のロギングがさらにエラーを招かないよう、printを維持する。
            print(f"[CRITICAL] CustomLogger: 設定からのロガー初期化に失敗しました: {e}. デフォルト設定 (INFO, Enabled, /tmp/app.log) を使用します。", flush=True)
            # エラーが発生しても、デフォルト値は __new__ で既に設定されているため、ここでは再設定不要。
            # ただし、ログファイルディレクトリの作成は再度試みる。
            if CustomLogger._log_file_path and CustomLogger._log_file_path.parent:
                 CustomLogger._log_file_path.parent.mkdir(parents=True, exist_ok=True)


    def set_level(self, level_name_or_int: str | int) -> None:
        """ロガーの現在のログレベルを設定します。"""
        if isinstance(level_name_or_int, str):
            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS.get(level_name_or_int.upper(), CustomLogger.LOG_LEVELS["INFO"])
        elif isinstance(level_name_or_int, int):
            CustomLogger._current_level_int = level_name_or_int
        else:
            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS["INFO"]

    def set_enabled(self, enabled: bool) -> None:
        """ロガーの有効/無効状態を設定します。"""
        CustomLogger._is_enabled = enabled

    @classmethod
    def set_project_root(cls, project_root: Path) -> None:
        """プロジェクトのルートパスを設定します。ログ出力時のパス表示に使用されます。"""
        cls._project_root_path = project_root.resolve() if project_root else None

    def log(self, message: str, level: str = "INFO", exc_info: object = None) -> None: # 新しいシグネチャ
        """指定されたレベルでログメッセージを記録します。"""
        # 初期化中のロギング呼び出しをチェック (循環依存を避けるため)
        if hasattr(CustomLogger, '_initializing') and CustomLogger._initializing:
            return

        # _is_enabled と _current_level_int が初期化されていることを保証
        # 通常、__new__ で行われるが、万が一の場合のフォールバック
        if not hasattr(CustomLogger, '_is_enabled'): CustomLogger._is_enabled = True
        if not hasattr(CustomLogger, '_current_level_int'): CustomLogger._current_level_int = CustomLogger.LOG_LEVELS["INFO"]
        if not hasattr(CustomLogger, '_log_file_path'): CustomLogger._log_file_path = Path("/tmp/app.log")


        if not CustomLogger._is_enabled:
            return

        message_level_str = level.upper()
        message_level_int = CustomLogger.LOG_LEVELS.get(message_level_str, CustomLogger.LOG_LEVELS["INFO"])

        if message_level_int < CustomLogger._current_level_int:
            return

        frame = inspect.currentframe().f_back
        filepath_abs = Path(frame.f_code.co_filename).resolve()
        lineno = frame.f_lineno

        # コンソール表示用のパス文字列を決定
        display_path_str = str(filepath_abs) # デフォルトは絶対パス
        if CustomLogger._project_root_path:
            try:
                # Python 3.9+ の場合: Path.is_relative_to を使用
                if hasattr(Path, "is_relative_to"):
                    if filepath_abs.is_relative_to(CustomLogger._project_root_path):
                        display_path_str = str(filepath_abs.relative_to(CustomLogger._project_root_path))
                # Python < 3.9 の場合: Path.relative_to を試し、ValueError をキャッチ
                else:
                    try:
                        # filepath_abs が _project_root_path の子孫でない場合 ValueError
                        possible_relative_path = filepath_abs.relative_to(CustomLogger._project_root_path)
                        display_path_str = str(possible_relative_path)
                    except ValueError:
                        # _project_root_path の下にない場合は、絶対パスのまま
                        pass
            except Exception:
                # 予期せぬエラーが発生した場合も安全のため絶対パスを使用
                pass # display_path_str は絶対パスのまま


        func_name = frame.f_code.co_name
        qualname_parts = []
        if 'self' in frame.f_locals:
            qualname_parts.append(frame.f_locals['self'].__class__.__name__)
        elif 'cls' in frame.f_locals:
            qualname_parts.append(frame.f_locals['cls'].__name__)
        qualname_parts.append(func_name)
        log_context = ".".join(qualname_parts)

        # _start_time が None でないことを確認 (通常は __new__ で設定される)
        current_time = time.time()
        start_time = CustomLogger._start_time if CustomLogger._start_time is not None else current_time
        elapsed_time_ms = int((current_time - start_time) * 1000)

        # 経過時間を右寄せ5桁でフォーマット
        formatted_elapsed_time_ms = f"{elapsed_time_ms:>5}"
        # ログレベル文字列の最大長を考慮してフォーマット (例: CRITICAL は 8 文字)
        # 左寄せで8文字の幅を確保
        formatted_level_str = f"{message_level_str:<8}"
        clickable_path = f"{display_path_str}:{lineno}" # 表示用パスを使用

        level_color_code = CustomLogger.LOG_COLORS.get(message_level_str, "") # ログレベルの色
        dim_color_code = CustomLogger.LOG_COLORS.get("DIM_GRAY", "")      # 暗い色のコード

        log_message_console = (f"{dim_color_code}{formatted_elapsed_time_ms}ms:{CustomLogger.RESET_COLOR} "
                               f"{level_color_code}{formatted_level_str}{CustomLogger.RESET_COLOR} "
                               f"{message} "
                               f"{dim_color_code}[{clickable_path}:{log_context}]{CustomLogger.RESET_COLOR}")
        print(log_message_console, flush=True)

        if CustomLogger._log_file_path:
            # ファイル用のログメッセージ (色なし)
            log_message_file = (f"{formatted_elapsed_time_ms}ms: "
                                f"{formatted_level_str} "
                                f"{message} "
                                f"[{filepath_abs}:{lineno}:{log_context}]") # ファイルログは絶対パス
            try:
                with open(CustomLogger._log_file_path, "a", encoding="utf-8") as f:
                    f.write(log_message_file + "\n")
                    if exc_info:
                        # exc_infoがTrueの場合、format_exc()は現在の例外を取得します。
                        # exc_infoが例外タプルの場合、format_exception(*exc_info)を使用する必要があります。
                        # 一般的なロギングの使用方法を簡潔にするため、ここではexc_info=Trueが主な使用例であると仮定します。
                        if exc_info is True:
                            traceback_str = traceback.format_exc()
                            if traceback_str and traceback_str != "None\n": # format_exc は例外がない場合 "None\n" を返します
                                f.write(traceback_str)
                        elif isinstance(exc_info, tuple):
                            traceback_str = "".join(traceback.format_exception(*exc_info))
                            if traceback_str:
                                f.write(traceback_str)
                        # else: exc_infoは例外インスタンスである可能性があり、必要であればそれもフォーマットできます。
            except Exception as e:
                # ファイル書き込みエラーはコンソールに出力 (無限ループを避けるため、ここではlog()を呼び出さない)
                print(f"ログファイルへの書き込みに失敗しました: {CustomLogger._log_file_path}, Error: {e}", flush=True)

        # exc_infoのコンソール出力（メインメッセージの後、ファイルロギングと同様）
        if exc_info:
            # exc_infoがTrueまたは例外タプルの場合、これはデフォルトでstderrに出力されます。
            if exc_info is True:
                traceback.print_exc() # sys.stderrに出力します
            elif isinstance(exc_info, tuple):
                 traceback.print_exception(*exc_info) # sys.stderrに出力します
            # else: 必要であれば例外インスタンスを直接処理できます


if __name__ == '__main__':
    print("--- CustomLogger __main__ テスト開始 ---", flush=True)

    # 1. SettingsManagerがデフォルト設定を使用する場合のロガーの初期化をテスト
    # (設定ファイルが存在しないか、loggingセクションがない場合)
    print("\nステージ1: デフォルト設定でのロガー初期化テスト", flush=True)
    logger1 = CustomLogger()
    print(f"初期ログレベル (logger1): {CustomLogger._current_level_int} (期待値: INFO=20)", flush=True)
    print(f"初期有効状態 (logger1): {CustomLogger._is_enabled} (期待値: True)", flush=True)
    logger1.log("デフォルトINFOレベルで表示されるはずのメッセージ (logger1)", level="INFO")
    logger1.log("デフォルトDEBUGレベルで表示されないはずのメッセージ (logger1)", level="DEBUG")

    # 2. SettingsManagerが特定のファイル設定を読み込むように準備
    print("\nステージ2: 設定ファイルを使用したロガー設定テストの準備", flush=True)
    from utils.settings_manager import SettingsManager
    # テスト用の設定ファイルを作成
    settings_content = {
        "logging": {
            "level": "DEBUG", # 古い構造
            "enabled": True
        },
        "other_setting": "value"
    }
    # SettingsManagerは通常 ~/.fractalapp/settings.jsonc を使用します
    # CustomLogger内でインスタンス化されるSettingsManagerがこのファイルを見つけるようにします
    settings_dir = Path.home() / ".fractalapp"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file_path = settings_dir / "settings.jsonc"

    # 新しい設定構造に合わせてテスト設定を更新
    settings_content_new_structure = {
        "application": {
            "logging": {
                "level": "DEBUG",
                "enabled": True
            }
        }
    }
    with open(settings_file_path, 'w', encoding='utf-8') as f:
        import json # jsonモジュールが既にインポートされているが、念のため
        json.dump(settings_content_new_structure, f, indent=4)
    print(f"テスト用設定ファイルを '{settings_file_path}' に作成しました。", flush=True)

    # 3. CustomLoggerをリセットして再インスタンス化し、新しい設定を読み込ませる
    print("\nステージ3: 設定ファイルを使用してのロガー再初期化テスト", flush=True)
    CustomLogger._instance = None # シングルトンをリセット
    CustomLogger._start_time = None # 開始時間もリセット (新しいセッションのように)
                                    # _initializing フラグは __new__ で処理されます

    logger_from_settings = CustomLogger() # これでSettingsManager経由で設定が読み込まれるはずです

    print(f"設定ファイルからのログレベル: {CustomLogger._current_level_int} (期待値: DEBUG=10)", flush=True)
    print(f"設定ファイルからの有効状態: {CustomLogger._is_enabled} (期待値: True)", flush=True)

    logger_from_settings.log("DEBUGレベルで表示されるはずのメッセージ (設定ファイル)", level="DEBUG")
    logger_from_settings.log("INFOレベルで表示されるはずのメッセージ (設定ファイル)", level="INFO")

    # 4. set_level と set_enabled のテスト (設定ファイル読み込み後)
    print("\nステージ4: 設定読み込み後のset_level/set_enabledテスト", flush=True)
    logger_from_settings.set_level("WARNING")
    print(f"ログレベルをWARNINGに設定後: {CustomLogger._current_level_int}", flush=True)
    logger_from_settings.log("INFOメッセージ (表示されないはず)", level="INFO")
    logger_from_settings.log("WARNINGメッセージ (表示されるはず)", level="WARNING")

    logger_from_settings.set_enabled(False)
    print(f"ロガーを無効に設定後: {CustomLogger._is_enabled}", flush=True)
    logger_from_settings.log("ERRORメッセージ (表示されないはず)", level="ERROR")

    logger_from_settings.set_enabled(True)
    print(f"ロガーを有効に設定後: {CustomLogger._is_enabled}", flush=True)
    logger_from_settings.log("ERRORメッセージ (再度表示されるはず)", level="ERROR")

    # 5. 無効な設定値のテスト
    print("\nステージ5: 無効なログ設定値のテスト", flush=True)
    settings_content_invalid = {
        "application": { # 新しい構造に対応
            "logging": {
                "level": "INVALID_LEVEL_STRING", # 無効なレベル文字列
                "enabled": "not_a_boolean"      # 無効なenabled値
            }
        }
    }
    with open(settings_file_path, 'w', encoding='utf-8') as f:
        json.dump(settings_content_invalid, f, indent=4)
    print(f"無効な設定で '{settings_file_path}' を上書きしました。", flush=True)

    CustomLogger._instance = None
    CustomLogger._start_time = None
    logger_invalid_settings = CustomLogger()

    print(f"無効な設定後のログレベル: {CustomLogger._current_level_int} (期待値: INFO=20)", flush=True)
    print(f"無効な設定後の有効状態: {CustomLogger._is_enabled} (期待値: True)", flush=True)
    logger_invalid_settings.log("INFOメッセージ (無効設定後、表示されるはず)", level="INFO")
    logger_invalid_settings.log("DEBUGメッセージ (無効設定後、表示されないはず)", level="DEBUG")


    # クリーンアップ: テスト設定ファイルを削除
    try:
        settings_file_path.unlink()
        print(f"テスト設定ファイル '{settings_file_path}' を削除しました。", flush=True)
    except OSError as e:
        print(f"テスト設定ファイルの削除に失敗しました: {e}", flush=True)

    print("-" * 30 + " ロガーテスト終了 " + "-" * 30, flush=True)
