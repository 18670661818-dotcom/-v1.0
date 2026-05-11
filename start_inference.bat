@echo off
chcp 65001 >nul
echo ========================================
echo 厨房AI系统 - 推理服务
echo ========================================
echo.

:: 激活conda环境
call D:\Anaconda\Scripts\activate.bat yolo-v8

:: 切换到项目目录
cd /d d:\2026\kitchen_ai_system\backend

:: 启动推理服务
python -m services.main --service inference --fps 3.0

pause
