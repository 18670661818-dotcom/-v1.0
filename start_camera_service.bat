@echo off
title Kitchen AI Camera Service

echo ========================================
echo      Kitchen AI Camera Service
echo ========================================
echo.

echo [1/2] Activating conda environment...
call D:\Anaconda\Scripts\activate.bat yolo-v8

if errorlevel 1 (
    echo Failed to activate conda environment.
    pause
    exit /b
)

echo.
echo [2/2] Starting camera service...
cd /d D:\2026\kitchen_ai_system
python camera_service.py

echo.
echo Camera service stopped.
pause
