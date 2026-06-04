@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title LOCAL AI - Repair Safe Start
color 0a

cd /d "%~dp0"
set "OLLAMA_KEEP_ALIVE=0"

if not exist "logs" mkdir logs

echo ========================================
echo    LOCAL AI - REPAIR SAFE START
echo ========================================
echo.

echo [0/5] Checking canonical file names...
if not exist "gui.py" (
    echo ERROR: gui.py not found. You may have extracted files as gui^(1^).py.
    echo Copy/rename gui^(1^).py to gui.py or extract the patch with overwrite.
    pause
    exit /b 1
)
if not exist "main.py" (
    echo ERROR: main.py not found.
    pause
    exit /b 1
)
if exist "gui(1).py" echo WARNING: gui^(1^).py exists. Python ignores it. Main file is gui.py.
if exist "main(2).py" echo WARNING: main^(2^).py exists. Python ignores it. Main file is main.py.
if exist "setup_and_run(1).bat" echo WARNING: setup_and_run^(1^).bat exists. Make sure you run setup_and_run.bat from this folder.

echo.
echo [1/5] Python version:
where py >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install Python 3.10+ and try again.
    pause
    exit /b 1
)
py -c "import sys; print(sys.version)"
if errorlevel 1 pause & exit /b 1

if not exist "config.json" (
    echo ERROR: config.json not found near this BAT file.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%A in (`py -c "import json; c=json.load(open('config.json',encoding='utf-8-sig')); print(c.get('ollama_models_dir',''))"`) do set "OLLAMA_MODELS_DIR=%%A"
if not "%OLLAMA_MODELS_DIR%"=="" (
    set "OLLAMA_MODELS=%OLLAMA_MODELS_DIR%"
    echo Using OLLAMA_MODELS=%OLLAMA_MODELS%
) else (
    echo Using OLLAMA_MODELS=%OLLAMA_MODELS%
)

for /f "usebackq delims=" %%A in (`py -c "import json; c=json.load(open('config.json',encoding='utf-8-sig')); print(c.get('brain_model',''))"`) do set "BRAIN_MODEL=%%A"

echo.
echo [2/5] Installing dependencies...
if exist "requirements.txt" (
    py -m pip install -r requirements.txt
) else (
    py -m pip install customtkinter psutil pyautogui ollama Pillow pywin32 faster-whisper sounddevice silero-vad torch soundfile numpy uiautomation pyperclip dxcam opencv-python pygetwindow
)
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [3/5] Creating folders...
if not exist "memory" mkdir memory
if not exist "logs" mkdir logs

echo.
echo [4/5] Checking Ollama model from config.json...
where ollama >nul 2>nul
if errorlevel 1 (
    echo ERROR: Ollama CLI not found in PATH.
    pause
    exit /b 1
)
if "%BRAIN_MODEL%"=="" (
    echo ERROR: brain_model is empty in config.json.
    pause
    exit /b 1
)
echo Brain model: %BRAIN_MODEL%
ollama show "%BRAIN_MODEL%" >nul 2>nul
if errorlevel 1 (
    echo ERROR: brain_model from config.json is not installed in Ollama: %BRAIN_MODEL%
    echo This script will NOT auto-pull or replace models.
    echo Run: ollama list
    pause
    exit /b 1
)
echo Installed models visible to Ollama:
ollama list

echo.
echo [5/5] Starting app with crash logging...
echo Game VRAM guard: OLLAMA_KEEP_ALIVE=%OLLAMA_KEEP_ALIVE%
echo If it exits, read logs\startup_error.log and logs\startup.log
echo.

py main.py > logs\startup.log 2>&1
set "APP_EXIT=%ERRORLEVEL%"

echo.
echo App exited with code %APP_EXIT%.
echo.
if exist logs\startup_error.log (
    echo Last startup_error.log lines:
    powershell -NoProfile -Command "Get-Content 'logs/startup_error.log' -Tail 80"
) else if exist logs\startup.log (
    echo Last startup.log lines:
    powershell -NoProfile -Command "Get-Content 'logs/startup.log' -Tail 80"
)
echo.
echo Console will not close automatically.
pause
exit /b %APP_EXIT%
