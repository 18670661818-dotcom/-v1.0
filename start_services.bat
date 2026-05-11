@echo off
title Kitchen AI Services

echo ========================================
echo      Kitchen AI Services Launcher
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
echo [2/2] Starting services...
echo.
echo Service Architecture:
echo   ├── camera_service    (RTSP读取、帧缓存、断流重连)
echo   ├── inference_service (YOLO推理、帧率限制、批量处理)
echo   ├── alert_service     (告警生成、冷却、频率限制)
echo   └── websocket_service (实时推送、状态广播)
echo.

cd /d D:\2026\kitchen_ai_system
python -m backend.services.main

echo.
echo Services stopped.
pause
