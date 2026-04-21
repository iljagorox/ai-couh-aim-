@echo off
chcp 65001 >nul
title SENTINEL AI - Setup and Run
color 0a

cd /d "%~dp0"

echo ========================================
echo    SENTINEL AI - ENVIRONMENT SETUP
echo ========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install Python 3.9+ and try again.
    pause
    exit /b 1
)

echo [1/4] Installing Python dependencies...
py -m pip install --upgrade pip
py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
py -m pip install faster-whisper silero-vad sounddevice ollama customtkinter pywin32 psutil pyautogui Pillow
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/4] Creating necessary folders...
if not exist "screenshots" mkdir screenshots
if not exist "memory" mkdir memory
if not exist "logs" mkdir logs

echo.
echo [3/4] Pulling correct Ollama models...
ollama pull gemma3:4b-it-qat
if errorlevel 1 (
    echo ERROR: Failed to pull gemma3:4b-it-qat
    pause
    exit /b 1
)

echo.
echo [4/4] Starting SENTINEL AI...
echo.
py main.py

pause