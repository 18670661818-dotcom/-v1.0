@echo off
title Kitchen AI System Startup

echo ========================================
echo      Kitchen AI System Startup Script
echo ========================================
echo.

echo [0/4] Activating conda environment...
call D:\Anaconda\Scripts\activate.bat yolo-v8

if errorlevel 1 (
    echo Failed to activate conda environment.
    pause
    exit /b
)

echo.
echo [1/4] Initializing database...
cd /d D:\2026\kitchen_ai_system
python update_db.py

if errorlevel 1 (
    echo Database initialization failed.
    pause
    exit /b
)

echo.
echo [2/4] Starting backend API server...
start "Kitchen AI Backend" cmd /k "call D:\Anaconda\Scripts\activate.bat yolo-v8 && cd /d D:\2026\kitchen_ai_system\backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo.
echo [3/4] Starting camera service...
start "Kitchen AI Camera Service" cmd /k "call D:\Anaconda\Scripts\activate.bat yolo-v8 && cd /d D:\2026\kitchen_ai_system && python camera_service.py"

timeout /t 2 /nobreak >nul

echo.
echo [4/4] Starting inference engine...
start "Kitchen AI Inference" cmd /k "call D:\Anaconda\Scripts\activate.bat yolo-v8 && cd /d D:\2026\kitchen_ai_system\backend && python -m services.inference_engine"

echo.
echo ========================================
echo      All backend services started!
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo API Docs:    http://localhost:8000/docs
echo.
echo Press any key to exit this window...
pause >nul