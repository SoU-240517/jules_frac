import unittest
import time
import inspect
import re
import io
import contextlib
from pathlib import Path
import sys
import json # JSONを扱うために追加

# Ensure the logger module can be found
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from logger.custom_logger import CustomLogger
from utils.settings_manager import SettingsManager # SettingsManagerをテストするために追加

# Helper function for testing log calls from a simple function
def helper_log_function(logger_instance, message, level="INFO"):
    # この関数の呼び出し元の行ではなく、この関数内のlog呼び出しの行番号が必要です。
    # inspect.currentframe().f_lineno はこの行の番号を返します。log呼び出しは次の行です。
    line_num = inspect.currentframe().f_lineno + 1
    logger_instance.log(message, level=level)
    return line_num

class HelperLogClass:
    def __init__(self, logger_instance):
        self.logger = logger_instance

    def log_method(self, message, level="INFO"):
        line_num = inspect.currentframe().f_lineno + 1
        self.logger.log(message, level=level)
        return line_num

    @staticmethod
    def static_log_method(logger_instance, message, level="INFO"):
        line_num = inspect.currentframe().f_lineno + 1
        logger_instance.log(message, level=level)
        return line_num

    @classmethod
    def class_log_method(cls, logger_instance, message, level="INFO"):
        line_num = inspect.currentframe().f_lineno + 1
        logger_instance.log(message, level=level)
        return line_num

class TestCustomLogger(unittest.TestCase):
    DUMMY_SETTINGS_FILE = Path("dummy_test_settings.json").resolve()

    def setUp(self):
        """各テストの前にロガーの状態をリセットします。"""
        CustomLogger._instance = None
        self.logger = CustomLogger()
        time.sleep(0.0001)
        # Ensure dummy settings file does not exist before a test that might create it
        if self.DUMMY_SETTINGS_FILE.exists():
            self.DUMMY_SETTINGS_FILE.unlink()


    def tearDown(self):
        """テスト後にデフォルトの状態にリセットし、ダミーファイルをクリーンアップします。"""
        self.logger.set_level("INFO")
        self.logger.set_enabled(True)
        if self.DUMMY_SETTINGS_FILE.exists():
            try:
                self.DUMMY_SETTINGS_FILE.unlink()
            except OSError:
                pass # CI/並列実行で問題が発生する可能性があるため、失敗しても許容

    def capture_log_output(self, log_call_func, *args, **kwargs):
        """指定された関数呼び出しからのstdoutをキャプチャします。"""
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            result = log_call_func(*args, **kwargs)
        return stdout_capture.getvalue().strip(), result


    def test_logger_instantiation_and_singleton(self):
        """ロガーがシングルトンであり、正しくインスタンス化されることをテストします。"""
        logger1 = self.logger
        logger2 = CustomLogger()
        self.assertIsInstance(logger1, CustomLogger)
        self.assertIs(logger1, logger2, "CustomLoggerはシングルトンであるべきです。")
        self.assertIsNotNone(CustomLogger._start_time, "開始時刻が初期化されるべきです。")
        # CustomLoggerはSettingsManager(is_for_logger_init=True)を使用するため、デフォルトで初期化されます
        self.assertEqual(CustomLogger._current_level_int, CustomLogger.LOG_LEVELS["INFO"])
        self.assertTrue(CustomLogger._is_enabled)

    def test_log_output_type(self):
        """ログ出力が文字列であることをテストします。"""
        log_output, _ = self.capture_log_output(self.logger.log, "Test message")
        self.assertIsInstance(log_output, str)

    def test_elapsed_time(self):
        """経過時間が正しく増加することをテストします。"""
        log_output1, _ = self.capture_log_output(self.logger.log, "First message")
        time.sleep(0.05)
        log_output2, _ = self.capture_log_output(self.logger.log, "Second message")

        match1 = re.match(r"\[(\d+)ms\]", log_output1)
        match2 = re.match(r"\[(\d+)ms\]", log_output2)

        self.assertIsNotNone(match1, "最初のログから経過時間を解析できませんでした。")
        self.assertIsNotNone(match2, "2番目のログから経過時間を解析できませんでした。")

        elapsed1 = int(match1.group(1))
        elapsed2 = int(match2.group(1))

        self.assertGreater(elapsed2, elapsed1, "経過時間は増加するべきです。")
        self.assertGreaterEqual(elapsed2 - elapsed1, 40, "経過時間の差が期待通りではありません（約50msであるべき）。")


    def common_log_format_and_caller_info_test(self, log_fn_caller_wrapper, expected_qualname,
                                               message="Test message", level_str="TESTLEVEL"):
        """
        様々なコンテキストからのログ形式と呼び出し元情報をテストするためのヘルパー。
        log_fn_caller_wrapper は、ロガー呼び出しを実行し、その呼び出しの行番号を返す関数です。
        expected_qualname は、ログコンテキストで期待される修飾名です (例: Class.method または function)。
        """
        log_output, actual_log_call_line = self.capture_log_output(log_fn_caller_wrapper)

        log_pattern = re.compile(
            r"\[(\d+)ms\] "
            r"\[([^:]+):(\d+)\] "
            r"\[([A-Za-z0-9_.]+)\] "
            r"\[([A-Z_]+)\] "
            r"(.*)"
        )
        match = log_pattern.match(log_output)

        self.assertIsNotNone(match, f"ログメッセージが期待される形式と一致しませんでした: '{log_output}'")

        self.assertTrue(match.group(2).endswith("test_custom_logger.py"), f"ログ記録されたファイルパスが不正です: {match.group(2)}")
        self.assertEqual(int(match.group(3)), actual_log_call_line, f"ログ記録された行番号が不正です。期待: {actual_log_call_line}, 実際: {match.group(3)}")
        self.assertEqual(match.group(4), expected_qualname, f"ログ記録されたコンテキストが不正です。期待: {expected_qualname}, 実際: {match.group(4)}")
        self.assertEqual(match.group(5), level_str.upper(), f"ログ記録されたレベルが不正です。期待: {level_str.upper()}, 実際: {match.group(5)}")
        self.assertEqual(match.group(6), message, f"ログ記録されたメッセージが不正です。期待: '{message}', 実際: '{match.group(6)}'")

    def test_log_from_test_method_itself(self):
        """テストメソッド自体からのロギングをテストします。"""
        message = "Log from test_log_from_test_method_itself"
        level = "INFO"
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            line_num = inspect.currentframe().f_lineno + 1
            self.logger.log(message, level=level)
        log_output = stdout_capture.getvalue().strip()

        log_pattern = re.compile(r"\[(\d+)ms\] \[([^:]+):(\d+)\] \[(.*?)\] \[(.*?)\] (.*)")
        match = log_pattern.match(log_output)
        self.assertIsNotNone(match, f"ログメッセージが期待される形式と一致しませんでした: '{log_output}'")

        self.assertTrue(match.group(2).endswith("test_custom_logger.py"))
        self.assertEqual(int(match.group(3)), line_num)
        self.assertEqual(match.group(4), "TestCustomLogger.test_log_from_test_method_itself")
        self.assertEqual(match.group(5), level.upper())
        self.assertEqual(match.group(6), message)

    def test_log_from_helper_function(self):
        """ヘルパー関数からのロギングをテストします。"""
        message = "Log from helper_log_function"
        level = "FUNCINFO"
        self.common_log_format_and_caller_info_test(
            lambda: helper_log_function(self.logger, message, level),
            expected_qualname="helper_log_function",
            message=message,
            level_str=level
        )

    def test_log_from_helper_class_method(self):
        """ヘルパークラスのインスタンスメソッドからのロギングをテストします。"""
        helper_instance = HelperLogClass(self.logger)
        message = "Log from HelperLogClass.log_method"
        level = "METHODDEBUG"
        self.common_log_format_and_caller_info_test(
            lambda: helper_instance.log_method(message, level),
            expected_qualname="HelperLogClass.log_method",
            message=message,
            level_str=level
        )

    def test_log_from_helper_static_method(self):
        """ヘルパークラスの静的メソッドからのロギングをテストします。"""
        message = "Log from HelperLogClass.static_log_method"
        level = "STATICWARN"
        self.common_log_format_and_caller_info_test(
            lambda: HelperLogClass.static_log_method(self.logger, message, level),
            expected_qualname="static_log_method",
            message=message,
            level_str=level
        )

    def test_log_from_helper_class_method_type(self):
        """ヘルパークラスのクラスメソッドからのロギングをテストします。"""
        message = "Log from HelperLogClass.class_log_method"
        level = "CLASSMETH"
        self.common_log_format_and_caller_info_test(
            lambda: HelperLogClass.class_log_method(self.logger, message, level),
            expected_qualname="HelperLogClass.class_log_method",
            message=message,
            level_str=level
        )

    def test_set_level_string(self):
        """set_levelが文字列引数で正しく動作することをテストします。"""
        self.logger.set_level("WARNING")
        self.assertEqual(CustomLogger._current_level_int, CustomLogger.LOG_LEVELS["WARNING"])
        log_output_info, _ = self.capture_log_output(self.logger.log, "Info after WARNING", level="INFO")
        self.assertEqual(log_output_info, "", "INFOレベルのログはWARNINGレベルでは表示されないはずです。")
        log_output_warning, _ = self.capture_log_output(self.logger.log, "Warning after WARNING", level="WARNING")
        self.assertIn("[WARNING] Warning after WARNING", log_output_warning)

        self.logger.set_level("DEBUG")
        self.assertEqual(CustomLogger._current_level_int, CustomLogger.LOG_LEVELS["DEBUG"])
        log_output_debug, _ = self.capture_log_output(self.logger.log, "Debug after DEBUG", level="DEBUG")
        self.assertIn("[DEBUG] Debug after DEBUG", log_output_debug)

        self.logger.set_level("INVALID_LEVEL")
        self.assertEqual(CustomLogger._current_level_int, CustomLogger.LOG_LEVELS["INFO"], "無効なレベル文字列はINFOにフォールバックするべきです。")

    def test_set_level_int(self):
        """set_levelが整数引数で正しく動作することをテストします。"""
        self.logger.set_level(CustomLogger.LOG_LEVELS["ERROR"])
        self.assertEqual(CustomLogger._current_level_int, CustomLogger.LOG_LEVELS["ERROR"])
        log_output_warn, _ = self.capture_log_output(self.logger.log, "Warning after ERROR", level="WARNING")
        self.assertEqual(log_output_warn, "", "WARNINGレベルのログはERRORレベルでは表示されないはずです。")
        log_output_error, _ = self.capture_log_output(self.logger.log, "Error after ERROR", level="ERROR")
        self.assertIn("[ERROR] Error after ERROR", log_output_error)

        self.logger.set_level(15)
        self.assertEqual(CustomLogger._current_level_int, 15)
        log_output_debug, _ = self.capture_log_output(self.logger.log, "Debug message", level="DEBUG")
        self.assertEqual(log_output_debug, "")
        log_output_info, _ = self.capture_log_output(self.logger.log, "Info message", level="INFO")
        self.assertIn("[INFO] Info message", log_output_info)

    def test_set_enabled(self):
        """set_enabledがロガーを正しく有効/無効にすることをテストします。"""
        self.logger.set_enabled(False)
        self.assertFalse(CustomLogger._is_enabled)
        log_output_disabled, _ = self.capture_log_output(self.logger.log, "Should not appear", level="ERROR")
        self.assertEqual(log_output_disabled, "", "ロガーが無効な場合、ログは表示されないはずです。")

        self.logger.set_enabled(True)
        self.assertTrue(CustomLogger._is_enabled)
        log_output_enabled, _ = self.capture_log_output(self.logger.log, "Should appear", level="ERROR")
        self.assertIn("[ERROR] Should appear", log_output_enabled, "ロガーが有効な場合、ログは表示されるはずです。")

    def test_log_filtering_by_level(self):
        """設定されたログレベルに基づいてログがフィルタリングされることをテストします。"""
        self.logger.set_level("WARNING")

        log_debug, _ = self.capture_log_output(self.logger.log, "Debug msg", level="DEBUG")
        self.assertEqual(log_debug, "")
        log_info, _ = self.capture_log_output(self.logger.log, "Info msg", level="INFO")
        self.assertEqual(log_info, "")

        log_warning, _ = self.capture_log_output(self.logger.log, "Warning msg", level="WARNING")
        self.assertIn("[WARNING] Warning msg", log_warning)
        log_error, _ = self.capture_log_output(self.logger.log, "Error msg", level="ERROR")
        self.assertIn("[ERROR] Error msg", log_error)
        log_critical, _ = self.capture_log_output(self.logger.log, "Critical msg", level="CRITICAL")
        self.assertIn("[CRITICAL] Critical msg", log_critical)

    def test_unknown_log_level_string_in_log_call(self):
        """logメソッドに渡された未知のログレベル文字列の処理をテストします。"""
        self.logger.set_level("DEBUG")

        log_output, _ = self.capture_log_output(self.logger.log, "Unknown level test", level="MYSTRANGELEVEL")
        self.assertIn("[MYSTRANGELEVEL] Unknown level test", log_output)

        self.logger.set_level("WARNING")
        log_output_filtered, _ = self.capture_log_output(self.logger.log, "Filtered unknown level", level="MYNEWSTRANGELEVEL")
        self.assertEqual(log_output_filtered, "", "未知のレベル(INFOとして扱われる)はWARNINGレベルでは表示されないはずです。")

    def _create_dummy_settings_file(self, content: dict):
        with open(self.DUMMY_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2)

    def test_configuration_from_simulated_main_enabled_warning(self):
        """main.pyからの設定適用をシミュレートします (レベルWARNING、有効)。"""
        settings_content = {"logging": {"level": "WARNING", "enabled": True}}
        self._create_dummy_settings_file(settings_content)

        # SettingsManagerはCWDのファイルを使用するようにします (setUp/tearDownで処理)
        # _is_for_logger_init=False を使用して、ファイルからロードするようにします
        settings_manager = SettingsManager(settings_filename=str(self.DUMMY_SETTINGS_FILE), _is_for_logger_init=False)
        log_config = settings_manager.get_logging_settings()

        self.logger.set_level(log_config.get("level", "INFO"))
        self.logger.set_enabled(log_config.get("enabled", True))

        # 検証
        self.assertEqual(CustomLogger._current_level_int, CustomLogger.LOG_LEVELS["WARNING"])
        self.assertTrue(CustomLogger._is_enabled)

        log_debug, _ = self.capture_log_output(self.logger.log, "Debug", level="DEBUG")
        self.assertEqual(log_debug, "")
        log_info, _ = self.capture_log_output(self.logger.log, "Info", level="INFO")
        self.assertEqual(log_info, "")
        log_warning, _ = self.capture_log_output(self.logger.log, "Warning", level="WARNING")
        self.assertIn("[WARNING] Warning", log_warning)
        log_error, _ = self.capture_log_output(self.logger.log, "Error", level="ERROR")
        self.assertIn("[ERROR] Error", log_error)

    def test_configuration_from_simulated_main_disabled(self):
        """main.pyからの設定適用をシミュレートします (無効)。"""
        settings_content = {"logging": {"level": "DEBUG", "enabled": False}}
        self._create_dummy_settings_file(settings_content)

        settings_manager = SettingsManager(settings_filename=str(self.DUMMY_SETTINGS_FILE), _is_for_logger_init=False)
        log_config = settings_manager.get_logging_settings()

        self.logger.set_level(log_config.get("level", "INFO"))
        self.logger.set_enabled(log_config.get("enabled", True))

        self.assertFalse(CustomLogger._is_enabled)
        log_debug, _ = self.capture_log_output(self.logger.log, "Debug", level="DEBUG")
        self.assertEqual(log_debug, "")
        log_error, _ = self.capture_log_output(self.logger.log, "Error", level="ERROR")
        self.assertEqual(log_error, "")

    # --- SettingsManager.get_logging_settings() のテスト ---
    # これらは理想的には test_settings_manager.py に配置されますが、ここではサブタスクの指示に従います。

    def test_settings_manager_get_logging_settings_defaults_when_empty_or_no_file(self):
        """SettingsManagerが空の設定またはファイルなしの場合にデフォルトのログ設定を返すことをテストします。"""
        # _is_for_logger_init=True は settings={} を強制し、ファイル読み込みをスキップします
        sm_for_empty = SettingsManager(_is_for_logger_init=True)
        settings = sm_for_empty.get_logging_settings()
        self.assertEqual(settings, {"level": "INFO", "enabled": True})

        # 存在しないファイルを指定してSettingsManagerをインスタンス化 (通常パス)
        sm_no_file = SettingsManager(settings_filename="non_existent_temp_file_xyz123.json", _is_for_logger_init=False)
        settings_no_file = sm_no_file.get_logging_settings()
        self.assertEqual(settings_no_file, {"level": "INFO", "enabled": True})


    def test_settings_manager_get_logging_settings_partial_config(self):
        """SettingsManagerが部分的なログ設定の場合にデフォルトをマージすることをテストします。"""
        settings_content_level_only = {"logging": {"level": "DEBUG"}} # "enabled" がありません
        self._create_dummy_settings_file(settings_content_level_only)
        sm_partial1 = SettingsManager(settings_filename=str(self.DUMMY_SETTINGS_FILE), _is_for_logger_init=False)
        settings1 = sm_partial1.get_logging_settings()
        self.assertEqual(settings1, {"level": "DEBUG", "enabled": True}) # enabledはデフォルト

        settings_content_enabled_only = {"logging": {"enabled": False}} # "level" がありません
        self._create_dummy_settings_file(settings_content_enabled_only)
        sm_partial2 = SettingsManager(settings_filename=str(self.DUMMY_SETTINGS_FILE), _is_for_logger_init=False)
        settings2 = sm_partial2.get_logging_settings()
        self.assertEqual(settings2, {"level": "INFO", "enabled": False}) # levelはデフォルト

        settings_content_no_logging_section = {"other_data": "value"} # "logging" セクションがありません
        self._create_dummy_settings_file(settings_content_no_logging_section)
        sm_partial3 = SettingsManager(settings_filename=str(self.DUMMY_SETTINGS_FILE), _is_for_logger_init=False)
        settings3 = sm_partial3.get_logging_settings()
        self.assertEqual(settings3, {"level": "INFO", "enabled": True}) # 両方デフォルト


    def test_settings_manager_get_logging_settings_from_file(self):
        """SettingsManagerがファイルから特定のログ設定を読み込むことをテストします。"""
        expected_settings = {"level": "ERROR", "enabled": False}
        settings_content = {"logging": expected_settings}
        self._create_dummy_settings_file(settings_content)

        sm = SettingsManager(settings_filename=str(self.DUMMY_SETTINGS_FILE), _is_for_logger_init=False)
        settings = sm.get_logging_settings()
        self.assertEqual(settings, expected_settings)

if __name__ == '__main__':
    unittest.main()
