import time
import inspect

class CustomLogger:
    _instance = None
    _start_time = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CustomLogger, cls).__new__(cls)
            cls._start_time = time.time()
        return cls._instance

    def log(self, message, level="INFO"):
        # 呼び出し元のフレームを取得
        frame = inspect.currentframe().f_back
        filepath = frame.f_code.co_filename
        lineno = frame.f_lineno

        # クラス名とメソッド名の取得を試みる
        class_name = ""
        method_name = frame.f_code.co_name

        if 'self' in frame.f_locals:
            class_name = frame.f_locals['self'].__class__.__name__
        elif 'cls' in frame.f_locals:
            class_name = frame.f_locals['cls'].__name__

        if class_name:
            log_context = f"{class_name}.{method_name}"
        else:
            log_context = method_name

        elapsed_time_ms = int((time.time() - self._start_time) * 1000)

        # 多くのターミナル/IDEでクリック可能なリンクのためのフォーマット
        clickable_path = f"{filepath}:{lineno}"

        log_message = f"[{elapsed_time_ms}ms] [{clickable_path}] [{log_context}] [{level.upper()}] {message}"
        print(log_message)

if __name__ == '__main__':
    logger1 = CustomLogger()

    def example_function():
        logger1.log("This is a test log from a function.")

    class ExampleClass:
        def __init__(self):
            self.logger = CustomLogger() # 同じインスタンスを使用

        def test_method(self):
            self.logger.log("This is a test log from a method.", level="DEBUG")
            example_function()

        @classmethod
        def test_class_method(cls):
            logger1.log("This is a test log from a class method.", level="WARNING")


    logger1.log("Logger initialized.")
    time.sleep(0.1)
    example_function()
    time.sleep(0.2)
    ex_instance = ExampleClass()
    ex_instance.test_method()
    time.sleep(0.3)
    ExampleClass.test_class_method()

    logger2 = CustomLogger() # これは logger1 と同じインスタンスになります
    logger2.log("This is from logger2, should have continued elapsed time and be same instance.")

    # クラス/関数の外部でのテスト
    logger1.log("Another top-level log.", level="ERROR")
