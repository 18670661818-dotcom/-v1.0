@echo off
title Kitchen AI System - 测试运行器

echo ========================================
echo      Kitchen AI System - 测试运行器
echo ========================================
echo.

echo [1/2] 激活conda环境...
call D:\Anaconda\Scripts\activate.bat yolo-v8

if errorlevel 1 (
    echo 无法激活conda环境。
    pause
    exit /b 1
)

echo.
echo [2/2] 运行测试...
cd /d D:\2026\kitchen_ai_system\backend
python run_tests.py

if errorlevel 1 (
    echo.
    echo 测试失败!
    pause
    exit /b 1
)

echo.
echo ========================================
echo      测试完成!
echo ========================================
echo.
pause