@echo off
echo __pycache__フォルダを削除しています...

:: 現在のディレクトリとサブディレクトリから__pycache__フォルダを再帰的に削除
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" (
        echo 削除中: %%d
        rmdir /s /q "%%d"
    )
)

:: .pycファイルも削除する場合（オプション）
:: for /r . %%f in (*.pyc) do del "%%f"

echo 完了しました。
pause