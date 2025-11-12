@echo off
:: このファイルは「ANSI」(Shift_IS) で保存してください。

echo Streamlitアプリを起動しています...
echo ブラウザが自動で開かない場合は、ターミナルに表示されるURLを開いてください。
echo.
:: 念のため、もし他のvenvが有効になっていたら無効化を試みる (エラーは無視)
REM call deactivate 2> nul

:: 1. このbatファイルがあるフォルダ(ルート)に移動
cd /d "%~dp0"
echo [デバッグ] 現在の場所: %CD%

:: 2. 「core」フォルダに移動 (存在確認なし)
echo [デバッグ] 'core' フォルダに移動します...
cd core

:: 3. 仮想環境(venv)のPython.exeの存在確認
echo [デバッグ] 'venv\Scripts\python.exe' を探しています...
if not exist ".\venv\Scripts\python.exe" (
    echo [エラー] 'venv\Scripts\python.exe' が見つかりません。
    echo.
    echo [!] core フォルダ内にある setup.bat を実行しましたか？
    echo.
    pause
    exit /b
)
echo [デバッグ] 'python.exe' が見つかりました。

:: 4. coreフォルダ内のvenvにあるpython.exeを使ってstreamlitを「モジュール」として実行
echo 仮想環境を起動して app.py を実行します...
call .\venv\Scripts\python.exe -m streamlit run app.py

:: 5. 終了処理 (pause)
echo.
echo Streamlitが終了しました。
pause