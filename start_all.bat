@echo off
echo ========================================
echo    Kitchen AI System Startup Script
echo ========================================
echo.

echo [1/3] Initializing database...
cd /d d:\2026\kitchen_ai_system
python update_db.py
echo.

echo [2/3] Starting backend API server...
start "Kitchen AI Backend" cmd /k "cd /d d:\2026\kitchen_ai_system\backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul

echo [3/3] Starting inference engine...
start "Kitchen AI Inference" cmd /k "cd /d d:\2026\kitchen_ai_system\backend && python -m services.inference_service"
echo.

echo ========================================
echo    All services started!
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key to exit this window...
pause >nul
