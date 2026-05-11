@echo off
title Kitchen AI System Startup

echo ========================================
echo      Kitchen AI System Startup Script
echo ========================================
echo.

echo [0/3] Activating conda environment...
call D:\Anaconda\Scripts\activate.bat yolo-v8

if errorlevel 1 (
    echo Failed to activate conda environment.
    pause
    exit /b
)

echo.
echo [1/3] Initializing database...
cd /d D:\2026\kitchen_ai_system
python update_db.py

if errorlevel 1 (
    echo Database initialization failed.
    pause
    exit /b
)

echo.
echo [2/3] Starting backend API server (includes inference service)...
start "Kitchen AI Backend" cmd /k "call D:\Anaconda\Scripts\activate.bat yolo-v8 && cd /d D:\2026\kitchen_ai_system\backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 5 /nobreak >nul

echo.
echo [3/3] Starting camera service...
start "Kitchen AI Camera Service" cmd /k "call D:\Anaconda\Scripts\activate.bat yolo-v8 && cd /d D:\2026\kitchen_ai_system && python -m backend.services.camera_service"

echo.
echo ========================================
echo      All backend services started!
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo API Docs:    http://localhost:8000/docs
echo.
echo Services:
echo   - Backend API + Inference (auto-started)
echo   - Camera Service (standalone)
echo.
echo Press any key to exit this window...
pause >nul