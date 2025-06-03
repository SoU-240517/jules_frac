import time
import inspect
# SettingsManagerのインポートは _initialize_singleton_attrs メソッド内で行い、循環インポートを避けます。

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
    _current_level_int: int
    _is_enabled: bool

    def __new__(cls, *args, **kwargs):
        """シングルトンインスタンスを作成または返します。初回作成時に初期化を行います。"""
        if not cls._instance:
            # print("DEBUG: CustomLogger __new__ - Creating new instance")
            cls._initializing = True # 初期化開始のフラグを設定
            instance = super(CustomLogger, cls).__new__(cls)

            # _start_time は最初のインスタンス作成時に一度だけ設定
            if cls._start_time is None:
                cls._start_time = time.time()

            # _initialize_singleton_attrs はインスタンスメソッドとして定義されているが、
            # クラス属性 (_current_level_int, _is_enabled) を設定する。
            # これは、設定をシングルトン全体で共有するため。
            instance._initialize_singleton_attrs()

            cls._instance = instance
            cls._initializing = False # 初期化終了のフラグを解除
            # print(f"DEBUG: CustomLogger __new__ - Instance created. Level: {cls._current_level_int}, Enabled: {cls._is_enabled}")
        return cls._instance

    def _initialize_singleton_attrs(self):
        """
        シングルトンの状態に関連する属性を初期化します。
        SettingsManagerから設定を読み込み、適用します。
        このメソッドは __new__ から一度だけ、最初のインスタンス作成時に呼び出されます。
        """
        # print("DEBUG: CustomLogger _initialize_singleton_attrs called")
        # SettingsManager をここでインポートして、モジュールレベルでの循環インポートのリスクを軽減します。
        from utils.settings_manager import SettingsManager

        # デフォルト値を設定してから、設定ファイルからの値で上書きを試みます。
        # これにより、SettingsManagerの初期化中にロギングが発生しても、基本的なロギング状態が保証されます。
        CustomLogger._current_level_int = CustomLogger.LOG_LEVELS.get("INFO", 20)
        CustomLogger._is_enabled = True

        try:
            # SettingsManager のインスタンス化時にロギングが発生する可能性があるため、
            # _initializing フラグが CustomLogger.log() でチェックされることが重要です。
            settings_manager = SettingsManager(settings_filename="base_settings.json", _is_for_logger_init=True) # SettingsManager は自身のロガーを使用する可能性があります
            logging_config = settings_manager.get_logging_settings()

            level_to_set_str = logging_config.get("level", "INFO").upper()
            enabled_bool = logging_config.get("enabled", True)

            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS.get(level_to_set_str, CustomLogger.LOG_LEVELS["INFO"])
            CustomLogger._is_enabled = enabled_bool
            # print(f"DEBUG: CustomLogger _initialize_singleton_attrs - Settings loaded: Level={level_to_set_str}({CustomLogger._current_level_int}), Enabled={enabled_bool}")
        except Exception as e:
            # 初期化中にエラーが発生した場合のフォールバック (標準エラーに出力検討)
            # この段階ではカスタムロガーが完全には利用できない可能性があるため、printを使用します。
            print(f"[CRITICAL] CustomLogger: 設定からのロガー初期化に失敗しました: {e}. デフォルト設定 (INFO, Enabled) を使用します。", flush=True)
            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS.get("INFO", 20)
            CustomLogger._is_enabled = True


    def set_level(self, level_name_or_int):
        """ロガーの現在のログレベルを設定します。"""
        # print(f"DEBUG: CustomLogger set_level called with: {level_name_or_int}")
        if isinstance(level_name_or_int, str):
            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS.get(level_name_or_int.upper(), CustomLogger.LOG_LEVELS["INFO"])
        elif isinstance(level_name_or_int, int):
            CustomLogger._current_level_int = level_name_or_int
        else:
            CustomLogger._current_level_int = CustomLogger.LOG_LEVELS["INFO"]
        # print(f"DEBUG: Log level set to: {CustomLogger._current_level_int}")

    def set_enabled(self, enabled: bool):
        """ロガーの有効/無効状態を設定します。"""
        # print(f"DEBUG: CustomLogger set_enabled called with: {enabled}")
        CustomLogger._is_enabled = enabled
        # print(f"DEBUG: Logger enabled state set to: {CustomLogger._is_enabled}")

    def log(self, message, level="INFO"):
        """指定されたレベルでログメッセージを記録します。"""
        # 初期化中のロギング呼び出しをチェック (循環依存を避けるため)
        if hasattr(CustomLogger, '_initializing') and CustomLogger._initializing:
            return

        # _is_enabled と _current_level_int が初期化されていることを保証
        # 通常、__new__ で行われるが、万が一の場合のフォールバック
        if not hasattr(CustomLogger, '_is_enabled'): CustomLogger._is_enabled = True
        if not hasattr(CustomLogger, '_current_level_int'): CustomLogger._current_level_int = CustomLogger.LOG_LEVELS["INFO"]


        if not CustomLogger._is_enabled:
            return

        message_level_str = level.upper()
        message_level_int = CustomLogger.LOG_LEVELS.get(message_level_str, CustomLogger.LOG_LEVELS["INFO"])

        if message_level_int < CustomLogger._current_level_int:
            return

        frame = inspect.currentframe().f_back
        filepath = frame.f_code.co_filename
        lineno = frame.f_lineno

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

        clickable_path = f"{filepath}:{lineno}"
        log_message = f"[{elapsed_time_ms}ms] [{clickable_path}] [{log_context}] [{message_level_str}] {message}"
        print(log_message, flush=True) # flush=True を追加して、出力が即座に行われるようにします

if __name__ == '__main__':
    print("--- CustomLogger __main__ テスト開始 ---", flush=True)

    # 1. SettingsManagerがデフォルト設定を使用する場合のロガーの初期化をテスト
    # (base_settings.jsonが存在しないか、loggingセクションがない場合)
    print("\nステージ1: デフォルト設定でのロガー初期化テスト", flush=True)
    logger1 = CustomLogger()
    print(f"初期ログレベル (logger1): {CustomLogger._current_level_int} (期待値: INFO=20)", flush=True)
    print(f"初期有効状態 (logger1): {CustomLogger._is_enabled} (期待値: True)", flush=True)
    logger1.log("デフォルトINFOレベルで表示されるはずのメッセージ (logger1)", level="INFO")
    logger1.log("デフォルトDEBUGレベルで表示されないはずのメッセージ (logger1)", level="DEBUG")

    # 2. SettingsManagerが特定のファイル設定を読み込むように準備
    print("\nステージ2: base_settings.jsonを使用したロガー設定テストの準備", flush=True)
    from utils.settings_manager import SettingsManager
    # テスト用の設定ファイルを作成
    settings_content = {
        "logging": {
            "level": "DEBUG",
            "enabled": True
        },
        "other_setting": "value"
    }
    # SettingsManagerは通常 ~/.fractalapp/base_settings.json を使用します
    # CustomLogger内でインスタンス化されるSettingsManagerがこのファイルを見つけるようにします
    settings_dir = Path.home() / ".fractalapp"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file_path = settings_dir / "base_settings.json"

    with open(settings_file_path, 'w', encoding='utf-8') as f:
        import json
        json.dump(settings_content, f, indent=4)
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
        "logging": {
            "level": "INVALID_LEVEL_STRING", # 無効なレベル文字列
            "enabled": "not_a_boolean"      # 無効なenabled値
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
