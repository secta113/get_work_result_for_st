@echo off
:: このファイルは「ANSI」(Shift_JIS) で保存してください。
:: このファイルは core フォルダ内に置いて実行してください。

echo --- Python セットアップ開始 ---
echo (Python がインストールされていないとエラーになります)
echo.

:: 1. このbatファイルがあるフォルダ(core)に移動
cd /d "%~dp0"

:: 2. Pythonがインストールされているか確認 (簡易チェック)
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [エラー] Python が見つかりません。
    echo Python をインストールしてから、再度このファイルを実行してください。
    echo https://www.python.org/downloads/release/python-31210/
    echo.
    pause
    exit /b
)

echo Python が見つかりました。
echo.

:: 3. 仮想環境(venv)の作成
echo 1. 仮想環境 (venv) を作成しています...
echo (core フォルダ内に venv フォルダが作成されます)
python -m venv venv
if %errorlevel% neq 0 (
    echo [エラー] 仮想環境の作成に失敗しました。
    echo.
    pause
    exit /b
)
echo ...仮想環境 (venv) の作成完了。
echo.

:: 4. 必要なライブラリのインストール
echo 2. 必要なライブラリをインストールしています...
echo (streamlit, requests などをインストールします)

:: 作成したvenvを有効化して pip を実行
call .\venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [エラー] ライブラリのインストールに失敗しました。
    echo (requirements.txt が同じフォルダにあるか確認してください)
    echo.
    pause
    exit /b
)
echo ...ライブラリのインストール完了。
echo.

:: 5. 完了
echo --- セットアップが正常に完了しました ---
echo.
echo フォルダを閉じて、外にある apprun.bat を実行してください。
echo.
pause