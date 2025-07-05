import sys
import os
import subprocess
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QTabWidget, QLabel,
                             QLineEdit, QPushButton, QTextEdit, QFileDialog,
                             QCheckBox, QSpinBox, QComboBox, QGroupBox,
                             QMessageBox, QProgressBar, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon


class RobocopyThread(QThread):
    """robocopyコマンドを別スレッドで実行"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.output_signal.emit(output.strip())

            return_code = process.poll()
            self.finished_signal.emit(return_code)

        except Exception as e:
            self.output_signal.emit(f"エラー: {str(e)}")
            self.finished_signal.emit(-1)


class RobocopyGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robocopy GUI")
        self.setGeometry(100, 100, 1000, 700)

        # 設定ファイルのパス
        self.config_file = Path("robocopy_config.json")

        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # メインレイアウト
        main_layout = QVBoxLayout(main_widget)

        # スプリッター（上下分割）
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        # 設定エリア
        settings_widget = QWidget()
        splitter.addWidget(settings_widget)

        # 出力エリア
        output_widget = QWidget()
        splitter.addWidget(output_widget)

        # サイズ比率設定
        splitter.setSizes([500, 200])

        self.init_settings_ui(settings_widget)
        self.init_output_ui(output_widget)
        self.init_control_buttons(main_layout)

        # 設定読み込み
        self.load_settings()

    def init_settings_ui(self, parent):
        """設定UIの初期化"""
        layout = QVBoxLayout(parent)

        # 基本設定
        basic_group = QGroupBox("基本設定")
        basic_layout = QGridLayout(basic_group)

        # コピー元
        basic_layout.addWidget(QLabel("コピー元:"), 0, 0)
        self.source_edit = QLineEdit()
        basic_layout.addWidget(self.source_edit, 0, 1)
        self.source_btn = QPushButton("参照")
        self.source_btn.clicked.connect(self.browse_source)
        basic_layout.addWidget(self.source_btn, 0, 2)

        # コピー先
        basic_layout.addWidget(QLabel("コピー先:"), 1, 0)
        self.dest_edit = QLineEdit()
        basic_layout.addWidget(self.dest_edit, 1, 1)
        self.dest_btn = QPushButton("参照")
        self.dest_btn.clicked.connect(self.browse_dest)
        basic_layout.addWidget(self.dest_btn, 1, 2)

        # ファイル指定
        basic_layout.addWidget(QLabel("ファイル指定:"), 2, 0)
        self.files_edit = QLineEdit()
        self.files_edit.setPlaceholderText("例: *.txt *.doc (空白区切り)")
        basic_layout.addWidget(self.files_edit, 2, 1, 1, 2)

        layout.addWidget(basic_group)

        # タブウィジェット
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # よく使用するオプション
        common_tab = QWidget()
        tab_widget.addTab(common_tab, "よく使用するオプション")
        self.init_common_options(common_tab)

        # コピーオプション
        copy_tab = QWidget()
        tab_widget.addTab(copy_tab, "コピーオプション")
        self.init_copy_options(copy_tab)

        # ファイル選択オプション
        file_tab = QWidget()
        tab_widget.addTab(file_tab, "ファイル選択")
        self.init_file_options(file_tab)

        # 再試行オプション
        retry_tab = QWidget()
        tab_widget.addTab(retry_tab, "再試行・ログ")
        self.init_retry_options(retry_tab)

        # 詳細オプション
        advanced_tab = QWidget()
        tab_widget.addTab(advanced_tab, "詳細オプション")
        self.init_advanced_options(advanced_tab)

    def init_common_options(self, parent):
        """よく使用するオプションのUI"""
        layout = QVBoxLayout(parent)

        # サブディレクトリ
        self.subdirs_cb = QCheckBox("/S - サブディレクトリもコピー（空ディレクトリは除く）")
        layout.addWidget(self.subdirs_cb)

        self.subdirs_empty_cb = QCheckBox("/E - サブディレクトリもコピー（空ディレクトリも含む）")
        layout.addWidget(self.subdirs_empty_cb)

        # ミラー
        self.mirror_cb = QCheckBox("/MIR - ミラーコピー（コピー先を完全に同期）")
        layout.addWidget(self.mirror_cb)

        # 既存ファイル
        self.overwrite_cb = QCheckBox("/Y - 既存ファイルを上書き確認なし")
        layout.addWidget(self.overwrite_cb)

        # 進行状況表示
        self.progress_cb = QCheckBox("/ETA - 進行状況とETAを表示")
        layout.addWidget(self.progress_cb)

        # テストモード
        self.test_cb = QCheckBox("/L - テストモード（実際にはコピーしない）")
        layout.addWidget(self.test_cb)

        layout.addStretch()

    def init_copy_options(self, parent):
        """コピーオプションのUI"""
        layout = QVBoxLayout(parent)

        # コピー属性
        attr_group = QGroupBox("コピー属性")
        attr_layout = QVBoxLayout(attr_group)

        self.copy_all_cb = QCheckBox("/COPYALL - すべてをコピー（/COPY:DATSOU と同等）")
        attr_layout.addWidget(self.copy_all_cb)

        self.copy_data_cb = QCheckBox("/COPY:DAT - データ、属性、タイムスタンプをコピー")
        attr_layout.addWidget(self.copy_data_cb)

        self.purge_cb = QCheckBox("/PURGE - コピー元にないファイルを削除")
        attr_layout.addWidget(self.purge_cb)

        layout.addWidget(attr_group)

        # バックアップモード
        backup_group = QGroupBox("バックアップモード")
        backup_layout = QVBoxLayout(backup_group)

        self.backup_cb = QCheckBox("/B - バックアップモード")
        backup_layout.addWidget(self.backup_cb)

        self.restartable_cb = QCheckBox("/Z - 再開可能モード")
        backup_layout.addWidget(self.restartable_cb)

        layout.addWidget(backup_group)

        layout.addStretch()

    def init_file_options(self, parent):
        """ファイル選択オプションのUI"""
        layout = QVBoxLayout(parent)

        # 日付フィルター
        date_group = QGroupBox("日付フィルター")
        date_layout = QGridLayout(date_group)

        self.max_age_cb = QCheckBox("/MAXAGE:")
        date_layout.addWidget(self.max_age_cb, 0, 0)
        self.max_age_spin = QSpinBox()
        self.max_age_spin.setMaximum(9999)
        date_layout.addWidget(self.max_age_spin, 0, 1)
        date_layout.addWidget(QLabel("日以内のファイル"), 0, 2)

        self.min_age_cb = QCheckBox("/MINAGE:")
        date_layout.addWidget(self.min_age_cb, 1, 0)
        self.min_age_spin = QSpinBox()
        self.min_age_spin.setMaximum(9999)
        date_layout.addWidget(self.min_age_spin, 1, 1)
        date_layout.addWidget(QLabel("日以前のファイル"), 1, 2)

        layout.addWidget(date_group)

        # サイズフィルター
        size_group = QGroupBox("サイズフィルター")
        size_layout = QGridLayout(size_group)

        self.max_size_cb = QCheckBox("/MAX:")
        size_layout.addWidget(self.max_size_cb, 0, 0)
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setMaximum(999999)
        size_layout.addWidget(self.max_size_spin, 0, 1)
        size_layout.addWidget(QLabel("MB以下のファイル"), 0, 2)

        self.min_size_cb = QCheckBox("/MIN:")
        size_layout.addWidget(self.min_size_cb, 1, 0)
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setMaximum(999999)
        size_layout.addWidget(self.min_size_spin, 1, 1)
        size_layout.addWidget(QLabel("MB以上のファイル"), 1, 2)

        layout.addWidget(size_group)

        # 除外
        exclude_group = QGroupBox("除外")
        exclude_layout = QVBoxLayout(exclude_group)

        self.exclude_files_cb = QCheckBox("/XF - 除外ファイル:")
        exclude_layout.addWidget(self.exclude_files_cb)
        self.exclude_files_edit = QLineEdit()
        self.exclude_files_edit.setPlaceholderText("例: *.tmp *.log")
        exclude_layout.addWidget(self.exclude_files_edit)

        self.exclude_dirs_cb = QCheckBox("/XD - 除外ディレクトリ:")
        exclude_layout.addWidget(self.exclude_dirs_cb)
        self.exclude_dirs_edit = QLineEdit()
        self.exclude_dirs_edit.setPlaceholderText("例: temp logs")
        exclude_layout.addWidget(self.exclude_dirs_edit)

        layout.addWidget(exclude_group)

        layout.addStretch()

    def init_retry_options(self, parent):
        """再試行・ログオプションのUI"""
        layout = QVBoxLayout(parent)

        # 再試行設定
        retry_group = QGroupBox("再試行設定")
        retry_layout = QGridLayout(retry_group)

        self.retry_cb = QCheckBox("/R:")
        retry_layout.addWidget(self.retry_cb, 0, 0)
        self.retry_spin = QSpinBox()
        self.retry_spin.setMaximum(9999)
        self.retry_spin.setValue(1)
        retry_layout.addWidget(self.retry_spin, 0, 1)
        retry_layout.addWidget(QLabel("回再試行"), 0, 2)

        self.wait_cb = QCheckBox("/W:")
        retry_layout.addWidget(self.wait_cb, 1, 0)
        self.wait_spin = QSpinBox()
        self.wait_spin.setMaximum(9999)
        self.wait_spin.setValue(30)
        retry_layout.addWidget(self.wait_spin, 1, 1)
        retry_layout.addWidget(QLabel("秒待機"), 1, 2)

        layout.addWidget(retry_group)

        # ログ設定
        log_group = QGroupBox("ログ設定")
        log_layout = QVBoxLayout(log_group)

        self.log_cb = QCheckBox("/LOG - ログファイル出力:")
        log_layout.addWidget(self.log_cb)

        log_file_layout = QHBoxLayout()
        self.log_file_edit = QLineEdit()
        log_file_layout.addWidget(self.log_file_edit)
        self.log_file_btn = QPushButton("参照")
        self.log_file_btn.clicked.connect(self.browse_log_file)
        log_file_layout.addWidget(self.log_file_btn)
        log_layout.addLayout(log_file_layout)

        self.log_append_cb = QCheckBox("/LOG+ - ログファイルに追記")
        log_layout.addWidget(self.log_append_cb)

        layout.addWidget(log_group)

        layout.addStretch()

    def init_advanced_options(self, parent):
        """詳細オプションのUI"""
        layout = QVBoxLayout(parent)

        # マルチスレッド
        thread_group = QGroupBox("マルチスレッド")
        thread_layout = QGridLayout(thread_group)

        self.multithread_cb = QCheckBox("/MT:")
        thread_layout.addWidget(self.multithread_cb, 0, 0)
        self.multithread_spin = QSpinBox()
        self.multithread_spin.setRange(1, 128)
        self.multithread_spin.setValue(8)
        thread_layout.addWidget(self.multithread_spin, 0, 1)
        thread_layout.addWidget(QLabel("スレッド"), 0, 2)

        layout.addWidget(thread_group)

        # その他の詳細オプション
        other_group = QGroupBox("その他")
        other_layout = QVBoxLayout(other_group)

        self.create_cb = QCheckBox("/CREATE - ファイルツリーのみ作成")
        other_layout.addWidget(self.create_cb)

        self.fat_cb = QCheckBox("/FFT - FAT ファイル時間を使用")
        other_layout.addWidget(self.fat_cb)

        self.dcopy_cb = QCheckBox("/DCOPY:T - ディレクトリタイムスタンプをコピー")
        other_layout.addWidget(self.dcopy_cb)

        self.sec_cb = QCheckBox("/SEC - セキュリティをコピー")
        other_layout.addWidget(self.sec_cb)

        self.compress_cb = QCheckBox("/COMPRESS - ネットワーク圧縮を有効化")
        other_layout.addWidget(self.compress_cb)

        layout.addWidget(other_group)

        layout.addStretch()

    def init_output_ui(self, parent):
        """出力UIの初期化"""
        layout = QVBoxLayout(parent)

        # 出力エリア
        output_label = QLabel("実行結果:")
        layout.addWidget(output_label)

        self.output_text = QTextEdit()
        self.output_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.output_text)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def init_control_buttons(self, layout):
        """制御ボタンの初期化"""
        button_layout = QHBoxLayout()

        # コマンド表示
        self.show_command_btn = QPushButton("コマンド表示")
        self.show_command_btn.clicked.connect(self.show_command)
        button_layout.addWidget(self.show_command_btn)

        # 実行
        self.execute_btn = QPushButton("実行")
        self.execute_btn.clicked.connect(self.execute_robocopy)
        button_layout.addWidget(self.execute_btn)

        # 停止
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_robocopy)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        button_layout.addStretch()

        # 設定保存・読み込み
        self.save_btn = QPushButton("設定保存")
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("設定読み込み")
        self.load_btn.clicked.connect(self.load_settings_dialog)
        button_layout.addWidget(self.load_btn)

        layout.addLayout(button_layout)

    def browse_source(self):
        """コピー元フォルダ選択"""
        folder = QFileDialog.getExistingDirectory(self, "コピー元フォルダを選択")
        if folder:
            self.source_edit.setText(folder)

    def browse_dest(self):
        """コピー先フォルダ選択"""
        folder = QFileDialog.getExistingDirectory(self, "コピー先フォルダを選択")
        if folder:
            self.dest_edit.setText(folder)

    def browse_log_file(self):
        """ログファイル選択"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "ログファイルを選択", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.log_file_edit.setText(file_path)

    def build_command(self):
        """robocopyコマンドを構築"""
        command = ["robocopy"]

        # 基本パラメータ
        source = self.source_edit.text().strip()
        dest = self.dest_edit.text().strip()

        if not source or not dest:
            raise ValueError("コピー元とコピー先を指定してください")

        command.extend([f'"{source}"', f'"{dest}"'])

        # ファイル指定
        files = self.files_edit.text().strip()
        if files:
            command.extend(files.split())

        # よく使用するオプション
        if self.subdirs_cb.isChecked():
            command.append("/S")
        if self.subdirs_empty_cb.isChecked():
            command.append("/E")
        if self.mirror_cb.isChecked():
            command.append("/MIR")
        if self.overwrite_cb.isChecked():
            command.append("/Y")
        if self.progress_cb.isChecked():
            command.append("/ETA")
        if self.test_cb.isChecked():
            command.append("/L")

        # コピーオプション
        if self.copy_all_cb.isChecked():
            command.append("/COPYALL")
        if self.copy_data_cb.isChecked():
            command.append("/COPY:DAT")
        if self.purge_cb.isChecked():
            command.append("/PURGE")
        if self.backup_cb.isChecked():
            command.append("/B")
        if self.restartable_cb.isChecked():
            command.append("/Z")

        # ファイル選択オプション
        if self.max_age_cb.isChecked():
            command.append(f"/MAXAGE:{self.max_age_spin.value()}")
        if self.min_age_cb.isChecked():
            command.append(f"/MINAGE:{self.min_age_spin.value()}")
        if self.max_size_cb.isChecked():
            command.append(f"/MAX:{self.max_size_spin.value()}000000")
        if self.min_size_cb.isChecked():
            command.append(f"/MIN:{self.min_size_spin.value()}000000")

        # 除外オプション
        if self.exclude_files_cb.isChecked() and self.exclude_files_edit.text().strip():
            command.append(f"/XF")
            command.extend(self.exclude_files_edit.text().strip().split())
        if self.exclude_dirs_cb.isChecked() and self.exclude_dirs_edit.text().strip():
            command.append(f"/XD")
            command.extend(self.exclude_dirs_edit.text().strip().split())

        # 再試行オプション
        if self.retry_cb.isChecked():
            command.append(f"/R:{self.retry_spin.value()}")
        if self.wait_cb.isChecked():
            command.append(f"/W:{self.wait_spin.value()}")

        # ログオプション
        if self.log_cb.isChecked() and self.log_file_edit.text().strip():
            if self.log_append_cb.isChecked():
                command.append(f"/LOG+:{self.log_file_edit.text().strip()}")
            else:
                command.append(f"/LOG:{self.log_file_edit.text().strip()}")

        # 詳細オプション
        if self.multithread_cb.isChecked():
            command.append(f"/MT:{self.multithread_spin.value()}")
        if self.create_cb.isChecked():
            command.append("/CREATE")
        if self.fat_cb.isChecked():
            command.append("/FFT")
        if self.dcopy_cb.isChecked():
            command.append("/DCOPY:T")
        if self.sec_cb.isChecked():
            command.append("/SEC")
        if self.compress_cb.isChecked():
            command.append("/COMPRESS")

        return command

    def show_command(self):
        """生成されるコマンドを表示"""
        try:
            command = self.build_command()
            command_str = " ".join(command)

            msg = QMessageBox()
            msg.setWindowTitle("生成されるコマンド")
            msg.setText(command_str)
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            msg.exec()

        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))

    def execute_robocopy(self):
        """robocopyを実行"""
        try:
            command = self.build_command()

            self.output_text.clear()
            self.output_text.append(f"実行コマンド: {' '.join(command)}\n")

            self.execute_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不確定プログレス

            # 別スレッドで実行
            self.robocopy_thread = RobocopyThread(command)
            self.robocopy_thread.output_signal.connect(self.append_output)
            self.robocopy_thread.finished_signal.connect(self.execution_finished)
            self.robocopy_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))

    def stop_robocopy(self):
        """robocopyを停止"""
        if hasattr(self, 'robocopy_thread') and self.robocopy_thread.isRunning():
            self.robocopy_thread.terminate()
            self.robocopy_thread.wait()
            self.execution_finished(-1)

    def append_output(self, text):
        """出力テキストを追加"""
        self.output_text.append(text)
        self.output_text.verticalScrollBar().setValue(
            self.output_text.verticalScrollBar().maximum()
        )

    def execution_finished(self, return_code):
        """実行完了時の処理"""
        self.execute_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

        if return_code == 0:
            self.output_text.append("\n実行完了")
        elif return_code > 0:
            self.output_text.append(f"\n実行完了（警告あり: リターンコード {return_code}）")
        else:
            self.output_text.append(f"\nエラーで終了（リターンコード {return_code}）")

    def get_settings(self):
        """現在の設定を取得"""
        settings = {
            # 基本設定
            'source': self.source_edit.text(),
            'dest': self.dest_edit.text(),
            'files': self.files_edit.text(),

            # よく使用するオプション
            'subdirs': self.subdirs_cb.isChecked(),
            'subdirs_empty': self.subdirs_empty_cb.isChecked(),
            'mirror': self.mirror_cb.isChecked(),
            'overwrite': self.overwrite_cb.isChecked(),
            'progress': self.progress_cb.isChecked(),
            'test': self.test_cb.isChecked(),

            # コピーオプション
            'copy_all': self.copy_all_cb.isChecked(),
            'copy_data': self.copy_data_cb.isChecked(),
            'purge': self.purge_cb.isChecked(),
            'backup': self.backup_cb.isChecked(),
            'restartable': self.restartable_cb.isChecked(),

            # ファイル選択オプション
            'max_age': self.max_age_cb.isChecked(),
            'max_age_value': self.max_age_spin.value(),
            'min_age': self.min_age_cb.isChecked(),
            'min_age_value': self.min_age_spin.value(),
            'max_size': self.max_size_cb.isChecked(),
            'max_size_value': self.max_size_spin.value(),
            'min_size': self.min_size_cb.isChecked(),
            'min_size_value': self.min_size_spin.value(),
            'exclude_files': self.exclude_files_cb.isChecked(),
            'exclude_files_value': self.exclude_files_edit.text(),
            'exclude_dirs': self.exclude_dirs_cb.isChecked(),
            'exclude_dirs_value': self.exclude_dirs_edit.text(),

            # 再試行オプション
            'retry': self.retry_cb.isChecked(),
            'retry_value': self.retry_spin.value(),
            'wait': self.wait_cb.isChecked(),
            'wait_value': self.wait_spin.value(),
            'log': self.log_cb.isChecked(),
            'log_file': self.log_file_edit.text(),
            'log_append': self.log_append_cb.isChecked(),

            # 詳細オプション
            'multithread': self.multithread_cb.isChecked(),
            'multithread_value': self.multithread_spin.value(),
            'create': self.create_cb.isChecked(),
            'fat': self.fat_cb.isChecked(),
            'dcopy': self.dcopy_cb.isChecked(),
            'sec': self.sec_cb.isChecked(),
            'compress': self.compress_cb.isChecked(),
        }
        return settings

    def set_settings(self, settings):
        """設定を適用"""
        # 基本設定
        self.source_edit.setText(settings.get('source', ''))
        self.dest_edit.setText(settings.get('dest', ''))
        self.files_edit.setText(settings.get('files', ''))

        # よく使用するオプション
        self.subdirs_cb.setChecked(settings.get('subdirs', False))
        self.subdirs_empty_cb.setChecked(settings.get('subdirs_empty', False))
        self.mirror_cb.setChecked(settings.get('mirror', False))
        self.overwrite_cb.setChecked(settings.get('overwrite', False))
        self.progress_cb.setChecked(settings.get('progress', False))
        self.test_cb.setChecked(settings.get('test', False))

        # コピーオプション
        self.copy_all_cb.setChecked(settings.get('copy_all', False))
        self.copy_data_cb.setChecked(settings.get('copy_data', False))
        self.purge_cb.setChecked(settings.get('purge', False))
        self.backup_cb.setChecked(settings.get('backup', False))
        self.restartable_cb.setChecked(settings.get('restartable', False))

        # ファイル選択オプション
        self.max_age_cb.setChecked(settings.get('max_age', False))
        self.max_age_spin.setValue(settings.get('max_age_value', 0))
        self.min_age_cb.setChecked(settings.get('min_age', False))
        self.min_age_spin.setValue(settings.get('min_age_value', 0))
        self.max_size_cb.setChecked(settings.get('max_size', False))
        self.max_size_spin.setValue(settings.get('max_size_value', 0))
        self.min_size_cb.setChecked(settings.get('min_size', False))
        self.min_size_spin.setValue(settings.get('min_size_value', 0))
        self.exclude_files_cb.setChecked(settings.get('exclude_files', False))
        self.exclude_files_edit.setText(settings.get('exclude_files_value', ''))
        self.exclude_dirs_cb.setChecked(settings.get('exclude_dirs', False))
        self.exclude_dirs_edit.setText(settings.get('exclude_dirs_value', ''))

        # 再試行オプション
        self.retry_cb.setChecked(settings.get('retry', False))
        self.retry_spin.setValue(settings.get('retry_value', 1))
        self.wait_cb.setChecked(settings.get('wait', False))
        self.wait_spin.setValue(settings.get('wait_value', 30))
        self.log_cb.setChecked(settings.get('log', False))
        self.log_file_edit.setText(settings.get('log_file', ''))
        self.log_append_cb.setChecked(settings.get('log_append', False))

        # 詳細オプション
        self.multithread_cb.setChecked(settings.get('multithread', False))
        self.multithread_spin.setValue(settings.get('multithread_value', 8))
        self.create_cb.setChecked(settings.get('create', False))
        self.fat_cb.setChecked(settings.get('fat', False))
        self.dcopy_cb.setChecked(settings.get('dcopy', False))
        self.sec_cb.setChecked(settings.get('sec', False))
        self.compress_cb.setChecked(settings.get('compress', False))

    def save_settings(self):
        """設定をファイルに保存"""
        try:
            settings = self.get_settings()

            file_path, _ = QFileDialog.getSaveFileName(
                self, "設定を保存", str(self.config_file),
                "JSON Files (*.json);;All Files (*)"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "保存完了", f"設定を保存しました: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "保存エラー", f"設定の保存に失敗しました: {str(e)}")

    def load_settings(self):
        """設定をファイルから読み込み（起動時）"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                self.set_settings(settings)
        except Exception as e:
            # 起動時のエラーは無視（デフォルト値を使用）
            pass

    def load_settings_dialog(self):
        """設定をファイルから読み込み（手動）"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "設定を読み込み", str(self.config_file.parent),
                "JSON Files (*.json);;All Files (*)"
            )

            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                self.set_settings(settings)
                QMessageBox.information(self, "読み込み完了", f"設定を読み込みました: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "読み込みエラー", f"設定の読み込みに失敗しました: {str(e)}")

    def closeEvent(self, event):
        """アプリケーション終了時の処理"""
        # 現在の設定を自動保存
        try:
            settings = self.get_settings()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except:
            pass

        # 実行中のスレッドを停止
        if hasattr(self, 'robocopy_thread') and self.robocopy_thread.isRunning():
            self.robocopy_thread.terminate()
            self.robocopy_thread.wait()

        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Robocopy GUI")

    # アプリケーションのスタイル設定
    app.setStyle('Fusion')

    window = RobocopyGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
