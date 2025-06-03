import unittest
import time
import inspect
import re
import io
import contextlib
from pathlib import Path
import sys

# Ensure the logger module can be found
# Assuming this test file is in 'tests/' and logger is in 'logger/' at the project root
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from logger.custom_logger import CustomLogger

# Helper function for testing log calls from a simple function
def helper_log_function(logger_instance, message, level="INFO"):
    line_num = inspect.currentframe().f_lineno + 1 # Line number of the log call below
    logger_instance.log(message, level=level)
    return line_num

class HelperLogClass:
    def __init__(self, logger_instance):
        self.logger = logger_instance

    def log_method(self, message, level="INFO"):
        line_num = inspect.currentframe().f_lineno + 1 # Line number of the log call below
        self.logger.log(message, level=level)
        return line_num

    @staticmethod
    def static_log_method(logger_instance, message, level="INFO"):
        line_num = inspect.currentframe().f_lineno + 1 # Line number of the log call below
        logger_instance.log(message, level=level)
        return line_num

    @classmethod
    def class_log_method(cls, logger_instance, message, level="INFO"):
        line_num = inspect.currentframe().f_lineno + 1 # Line number of the log call below
        logger_instance.log(message, level=level)
        return line_num

class TestCustomLogger(unittest.TestCase):

    def setUp(self):
        # Reset the logger's start time for each test to ensure predictable elapsed times
        # This relies on the logger being a singleton and _start_time being accessible for testing
        CustomLogger._instance = None
        CustomLogger._start_time = None
        self.logger = CustomLogger()
        # Allow a very small initial time to pass so elapsed time is not zero
        # This helps in differentiating initial logs from subsequent ones if needed
        # and ensures _start_time is definitely set before any log calls.
        time.sleep(0.001)


    def capture_log_output(self, log_call_func, *args, **kwargs):
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            log_call_func(*args, **kwargs)
        return stdout_capture.getvalue().strip()

    def test_logger_instantiation_and_singleton(self):
        logger1 = CustomLogger()
        logger2 = CustomLogger()
        self.assertIsInstance(logger1, CustomLogger)
        self.assertIs(logger1, logger2, "CustomLogger should be a singleton.")
        self.assertIsNotNone(logger1._start_time, "Start time should be initialized.")

    def test_log_output_type(self):
        log_output = self.capture_log_output(self.logger.log, "Test message")
        self.assertIsInstance(log_output, str)

    def test_elapsed_time(self):
        log_output1 = self.capture_log_output(self.logger.log, "First message")
        time.sleep(0.05) # 50ms delay
        log_output2 = self.capture_log_output(self.logger.log, "Second message")

        match1 = re.match(r"\[(\d+)ms\]", log_output1)
        match2 = re.match(r"\[(\d+)ms\]", log_output2)

        self.assertIsNotNone(match1, "Could not parse elapsed time from first log.")
        self.assertIsNotNone(match2, "Could not parse elapsed time from second log.")

        elapsed1 = int(match1.group(1))
        elapsed2 = int(match2.group(1))

        self.assertGreater(elapsed2, elapsed1, "Elapsed time should increase.")
        self.assertGreaterEqual(elapsed2 - elapsed1, 45, "Elapsed time difference not as expected (should be ~50ms).") # allow some leeway

    def test_log_levels(self):
        test_cases = ["INFO", "WARNING", "ERROR", "DEBUG", "custom_level"]
        for level in test_cases:
            log_output = self.capture_log_output(self.logger.log, f"Message with level {level}", level=level)
            self.assertIn(f"[{level.upper()}]", log_output, f"Log level '{level.upper()}' not found in output.")

    def common_log_format_and_caller_info_test(self, log_fn_caller, expected_class_name, expected_method_name,
                                               message="Test message", level="TESTLEVEL",
                                               is_within_class_method=False, is_static_method=False):
        """
        Helper to test log format and caller info from various contexts.
        `log_fn_caller` is a function that, when called, executes the logger.log() and returns the line number of the call.
        """
        current_file_abs = Path(__file__).resolve()

        # Call the function that makes the log call and get the line number
        # This needs to be done carefully to get the correct frame for inspect
        # The line number for the log call itself is returned by the helper

        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            # The helper function (e.g. helper_log_function or a lambda calling the method)
            # executes the log and returns the line number where logger.log was called.
            actual_log_call_line = log_fn_caller()
        log_output = stdout_capture.getvalue().strip()

        # Regex to parse the log message
        # Example: [123ms] [tests/test_custom_logger.py:50] [TestCustomLogger.test_method] [INFO] Test
        log_pattern = re.compile(
            r"\[(\d+)ms\] "                                # Elapsed time
            r"\[([^:]+):(\d+)\] "                         # Filepath and line number
            r"\[([A-Za-z0-9_.]+)\] "                      # Class.method or function
            r"\[([A-Z_]+)\] "                             # Log level
            r"(.*)"                                       # Message
        )
        match = log_pattern.match(log_output)

        self.assertIsNotNone(match, f"Log message did not match expected format: '{log_output}'")

        # file_path_from_log = Path(match.group(2)).resolve() # Make absolute for comparison
        # self.assertEqual(file_path_from_log, current_file_abs, "Logged file path is incorrect.")
        # Making the file path check more robust if relative paths are used by logger
        self.assertTrue(match.group(2).endswith("test_custom_logger.py"), "Logged file path is incorrect.")

        self.assertEqual(int(match.group(3)), actual_log_call_line, "Logged line number is incorrect.")

        logged_context = match.group(4)
        if expected_class_name:
            if is_within_class_method or is_static_method : # cls or no self
                 self.assertEqual(logged_context, f"{expected_class_name}.{expected_method_name}", "Logged class.method context is incorrect.")
            else: # Instance method
                 self.assertEqual(logged_context, f"{expected_class_name}.{expected_method_name}", "Logged class.method context is incorrect.")
        else:
            self.assertEqual(logged_context, expected_method_name, "Logged function context is incorrect.")

        self.assertEqual(match.group(5), level.upper(), "Logged level is incorrect.")
        self.assertEqual(match.group(6), message, "Logged message is incorrect.")

    def test_log_from_test_method_itself(self):
        # We need to capture the line number *of the log call itself*
        # This is tricky because the log call and the line number check are in the same frame
        # So, we get the line number just before the call.
        message = "Log from test_log_from_test_method_itself"
        level = "INFO"

        # This lambda structure helps pass the line number determination into the common tester
        # but for a direct call, the line number is obtained *inside* the common tester logic
        # if we were to call self.logger.log directly.
        # For simplicity, we'll make a direct call and adjust expectations.

        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            line_num = inspect.currentframe().f_lineno + 1 # Line of self.logger.log
            self.logger.log(message, level=level)
        log_output = stdout_capture.getvalue().strip()

        log_pattern = re.compile(r"\[(\d+)ms\] \[([^:]+):(\d+)\] \[(.*?)\] \[(.*?)\] (.*)")
        match = log_pattern.match(log_output)
        self.assertIsNotNone(match, f"Log message did not match expected format: '{log_output}'")

        self.assertTrue(match.group(2).endswith("test_custom_logger.py"))
        self.assertEqual(int(match.group(3)), line_num)
        self.assertEqual(match.group(4), "TestCustomLogger.test_log_from_test_method_itself") # inspect will get this method
        self.assertEqual(match.group(5), level.upper())
        self.assertEqual(match.group(6), message)


    def test_log_from_helper_function(self):
        message = "Log from helper_log_function"
        level = "FUNCINFO"
        # The helper_log_function itself returns the line number of its internal log call
        self.common_log_format_and_caller_info_test(
            lambda: helper_log_function(self.logger, message, level),
            expected_class_name="",  # No class for a standalone function
            expected_method_name="helper_log_function",
            message=message,
            level=level
        )

    def test_log_from_helper_class_method(self):
        helper_instance = HelperLogClass(self.logger)
        message = "Log from HelperLogClass.log_method"
        level = "METHODDEBUG"
        self.common_log_format_and_caller_info_test(
            lambda: helper_instance.log_method(message, level),
            expected_class_name="HelperLogClass",
            expected_method_name="log_method",
            message=message,
            level=level
        )

    def test_log_from_helper_static_method(self):
        message = "Log from HelperLogClass.static_log_method"
        level = "STATICWARN"
        self.common_log_format_and_caller_info_test(
            lambda: HelperLogClass.static_log_method(self.logger, message, level),
            expected_class_name="", # Current logger behavior: class name is not captured for static methods
            expected_method_name="static_log_method",
            message=message,
            level=level,
            is_static_method=True
        )

    def test_log_from_helper_class_method_type(self):
        message = "Log from HelperLogClass.class_log_method"
        level = "CLASSMETH"
        self.common_log_format_and_caller_info_test(
            lambda: HelperLogClass.class_log_method(self.logger, message, level),
            expected_class_name="HelperLogClass", # For class methods, logger might see the class
            expected_method_name="class_log_method",
            message=message,
            level=level,
            is_within_class_method=True
        )


if __name__ == '__main__':
    unittest.main()
