from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, QThreadPool
import time
import numpy as np
from PIL import Image # Import Pillow
from pathlib import Path
# Pillowをインポート
# fractal_engine_refの型ヒント用
# from src.app.models.fractal_engine import FractalEngine
from logger.custom_logger import CustomLogger

logger = CustomLogger()

class ExporterSignals(QObject):
    progress_updated = pyqtSignal(int)
    export_finished = pyqtSignal(bool, str)

class ImageExporter(QRunnable):
    def __init__(self, fractal_engine_ref, export_settings: dict):
        super().__init__()
        self.fractal_engine = fractal_engine_ref
        self.export_settings = export_settings
        self.signals = ExporterSignals()
        self._is_cancelled = False

    def run(self):
        filepath = self.export_settings.get('filepath', 'fractal_export.png') # exceptブロックで使用するために初期化
        try: # exceptブロックで使用するために初期化
            self.signals.progress_updated.emit(0)
            if self._is_cancelled:
                self.signals.export_finished.emit(False, "エクスポートがキャンセルされました。")
                return

            # export_settings辞書から他の設定を展開
            output_width = self.export_settings.get('width', 1920)
            output_height = self.export_settings.get('height', 1080)
            common_params_override = {
                'max_iterations': self.export_settings.get('iterations', self.fractal_engine.max_iterations if self.fractal_engine else 100)
            }
            fractal_plugin_name_override = self.export_settings.get('fractal_plugin_name')
            fractal_plugin_params_override = self.export_settings.get('fractal_plugin_params')
            coloring_algo_name_override = self.export_settings.get('coloring_algorithm_name') # Corrected key from dialog example
            coloring_algo_params_override = self.export_settings.get('coloring_algorithm_params') # ダイアログの例からキーを修正
            color_pack_name_override = self.export_settings.get('color_pack_name')
            color_map_name_override = self.export_settings.get('color_map_name')

            # アンチエイリアシング: ダイアログは係数を渡し、エンジンは文字列を期待
            aa_factor = self.export_settings.get('antialiasing_factor', 1)
            antialiasing_level_str = f"{aa_factor}x{aa_factor} SSAA" if aa_factor > 1 else "なし"

            logger.log(f"エクスポート処理開始: {filepath} ({output_width}x{output_height}), AA: {antialiasing_level_str}", level="INFO")
            self.signals.progress_updated.emit(5)

            if self._is_cancelled:
                self.signals.export_finished.emit(False, "計算開始前にキャンセルされました。")
                return

            image_data_np = self.fractal_engine.generate_image_for_output(
                output_width=output_width,
                output_height=output_height,
                common_params_override=common_params_override,
                fractal_plugin_name_override=fractal_plugin_name_override,
                fractal_plugin_params_override=fractal_plugin_params_override,
                coloring_algo_name_override=coloring_algo_name_override,
                coloring_algo_params_override=coloring_algo_params_override,
                color_pack_name_override=color_pack_name_override,
                color_map_name_override=color_map_name_override,
                antialiasing_level=antialiasing_level_str
            )

            self.signals.progress_updated.emit(80)

            if self._is_cancelled:
                self.signals.export_finished.emit(False, "ファイル保存前にキャンセルされました。")
                return

            if image_data_np is None:
                self.signals.export_finished.emit(False, "画像データの生成に失敗しました (エンジンがNoneを返しました)。")
                return

            # --- Pillowを使用したファイル保存 ---
            logger.log(f"画像データ生成完了 ({image_data_np.shape})。ファイル保存開始: {filepath}", level="INFO")

            pil_image = Image.fromarray(image_data_np, 'RGBA')
            format_str = self.export_settings.get('format', 'PNG').upper()
            save_options = {}

            image_to_save = pil_image # デフォルトでは元のRGBAを使用

            if format_str == 'PNG':
                save_options['optimize'] = True
                # PNGはRGBAを直接サポート。ダイアログのpng_transparentオプションは、
                # 「アルファが使用されていることを確認する」または「背景がまだ透明でない場合は透明にする」
                # ことを意味する可能性がある。エンジンからのRGBAデータには既に正しいアルファがあると仮定。
                # 'png_transparent'がFalseで画像にアルファがある場合、白い背景とブレンドしてRGBに変換
                # することも考えられるが、通常ユーザーはアルファが存在する場合はそれを期待する。
                # 簡単のため、アルファがあればRGBAとして保存し、なければRGBとして保存する。
                # エンジンでRGBAを作成するため、RGBAとして保存される。
                # png_transparentがFalseの場合、RGBに変換することもできる:
                # if not self.export_settings.get('png_transparent', True) and pil_image.mode == 'RGBA':
                #    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                #    background.paste(pil_image, mask=pil_image.split()[3])
                #    image_to_save = background
                pass # デフォルトではPNG用にRGBAをそのまま保存

            elif format_str == 'JPEG':
                save_options['quality'] = self.export_settings.get('jpeg_quality', 90)
                save_options['optimize'] = True
                # save_options['progressive'] = True # オプション
                if pil_image.mode == 'RGBA':
                    # JPEG用にRGBに変換する前に白い背景とブレンド
                    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                    # 元の画像のアルファチャンネルをマスクとして使用
                    try:
                        alpha_channel = pil_image.split()[3]
                        background.paste(pil_image, mask=alpha_channel)
                        image_to_save = background
                    except IndexError: # 画像がRGBAでない場合 (例: LA)
                        image_to_save = pil_image.convert('RGB')
                else: # RGBAでない場合は、RGBであることを確認
                    image_to_save = pil_image.convert('RGB')

            elif format_str == 'TIFF':
                save_options['compression'] = 'tiff_lzw' # 一般的な可逆圧縮
                # TIFFはRGBAを処理可能

            elif format_str == 'BMP':
                # BMPは通常アルファをうまくサポートしないため、RGBに変換
                if pil_image.mode == 'RGBA':
                    image_to_save = pil_image.convert('RGB')
            else:
                self.signals.export_finished.emit(False, f"未対応のファイル形式です: {format_str}")
                return

            if self._is_cancelled:
                self.signals.export_finished.emit(False, "エクスポートがキャンセルされました (保存直前)。")
                return

            logger.log(f"'{filepath}' に '{format_str}' として保存中 (オプション: {save_options})...", level="INFO")
            image_to_save.save(filepath, format=format_str, **save_options)

            self.signals.progress_updated.emit(100)
            self.signals.export_finished.emit(True, filepath)
            logger.log("保存完了。", level="INFO")

        except FileNotFoundError:
            error_msg = f"指定されたパスのディレクトリが見つかりません: {Path(filepath).parent}"
            logger.log(f"エラー - {error_msg}", level="ERROR")
            self.signals.export_finished.emit(False, error_msg)
        except IOError as e:
            error_msg = f"ファイルの書き込みに失敗しました ({filepath}): {e}"
            logger.log(f"エラー - {error_msg}", level="ERROR")
            self.signals.export_finished.emit(False, error_msg)
        except Exception as e:
            import traceback
            error_msg = f"予期せぬエクスポートエラー: {e}"
            logger.log(f"エクスポート中に予期せぬエラーが発生: {e}\n{traceback.format_exc()}", level="ERROR")
            self.signals.export_finished.emit(False, error_msg)

    def cancel(self):
        logger.log("キャンセル要求を受け付けました。", level="INFO")
        self._is_cancelled = True

if __name__ == '__main__':
    logger.log("ImageExporter スタンドアロンテスト (シミュレート実行)", level="INFO")
    # ... (前のステップからのMockFractalEngineとテストセットアップ、簡略化されている可能性あり)
    class MockFractalEngine:
        def generate_image_for_output(self, output_width, output_height, **kwargs):
            logger.log(f"  モックエンジン: generate_image_for_output ({output_width}x{output_height}), AA: {kwargs.get('antialiasing_level')}", level="DEBUG")
            time.sleep(0.1) # 生成時間をシミュレート
            if exporter_for_test._is_cancelled: return None # テスト用に直接参照を使用
            return np.random.randint(0, 256, size=(output_height, output_width, 4), dtype=np.uint8)

    mock_engine_instance = MockFractalEngine()
    test_settings_png = {
        'filepath': 'test_export_run.png', 'format': 'PNG', 'width': 100, 'height': 80,
        'iterations': 150, 'antialiasing_factor': 1, 'antialiasing': "なし",
        'png_transparent': True
    }
    test_settings_jpg = {
        'filepath': 'test_export_run.jpg', 'format': 'JPEG', 'width': 120, 'height': 90,
        'iterations': 100, 'antialiasing_factor': 1, 'antialiasing': "なし",
        'jpeg_quality': 85
    }

    exporter_for_test = None # モックエンジンアクセス用に割り当てられる

    def handle_progress(p): logger.log(f"  テスト進捗: {p}%", level="INFO")
    def handle_finished(success, msg_or_path):
        status = "成功" if success else "失敗"
        logger.log(f"  テスト終了 {status}: {msg_or_path}", level="INFO")

    logger.log("\n--- テスト1: PNGエクスポート ---", level="INFO")
    exporter_png = ImageExporter(mock_engine_instance, test_settings_png)
    exporter_for_test = exporter_png # モックエンジンがキャンセルフラグを確認するため
    exporter_png.signals.progress_updated.connect(handle_progress)
    exporter_png.signals.export_finished.connect(handle_finished)
    exporter_png.run()
    if Path(test_settings_png['filepath']).exists(): Path(test_settings_png['filepath']).unlink() # クリーンアップ

    logger.log("\n--- テスト2: JPEGエクスポート ---", level="INFO")
    exporter_jpg = ImageExporter(mock_engine_instance, test_settings_jpg)
    exporter_for_test = exporter_jpg
    exporter_jpg.signals.progress_updated.connect(handle_progress)
    exporter_jpg.signals.export_finished.connect(handle_finished)
    exporter_jpg.run()
    if Path(test_settings_jpg['filepath']).exists(): Path(test_settings_jpg['filepath']).unlink() # クリーンアップ

    logger.log("\n--- テスト3: 生成中のキャンセル (シミュレート) ---", level="INFO")
    exporter_cancel = ImageExporter(mock_engine_instance, test_settings_png)
    exporter_for_test = exporter_cancel # モックエンジンはこのインスタンスのフラグにアクセスする必要がある
    exporter_cancel.signals.progress_updated.connect(handle_progress)
    exporter_cancel.signals.export_finished.connect(handle_finished)
    exporter_cancel.cancel() # 実行前にキャンセルを要求、generate_image_for_outputがそれを検知するはず
    exporter_cancel.run()

    logger.log("\nImageExporter スタンドアロンテスト終了。", level="INFO")
