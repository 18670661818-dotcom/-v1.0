@echo off
chcp 65001 >nul

echo ==========================================
echo Kitchen AI - 部署初始化脚本
echo ==========================================

REM 检查 Python 环境
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 未找到 Python，请先安装 Python 3.7+
    pause
    exit /b 1
)

echo Python 环境检查通过

REM 检查依赖
echo 检查项目依赖...
pip show fastapi >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 警告: 未检测到 FastAPI，正在安装依赖...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

echo 依赖检查完成

REM 创建必要的目录
echo 创建必要的目录...
if not exist "storage" mkdir storage
if not exist "storage\alerts" mkdir storage\alerts
if not exist "storage\logs" mkdir storage\logs
if not exist "models" mkdir models

echo 目录创建完成

REM 数据库初始化
echo.
echo ==========================================
echo 步骤 1: 数据库初始化
echo ==========================================
python scripts\init_db.py
if %ERRORLEVEL% NEQ 0 (
    echo 警告: 数据库初始化可能未完全成功，请检查上述输出
)

REM 创建管理员账号（如果需要）
echo.
echo ==========================================
echo 步骤 2: 创建管理员账号
echo ==========================================

REM 检查是否已有管理员账号
python -c "from scripts.create_admin import list_admin_users; list_admin_users()" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 创建默认管理员账号...
    python scripts\create_admin.py create --username admin --password admin123456 --email admin@kitchen-ai.com
)

echo.
echo ==========================================
echo 部署初始化完成！
echo ==========================================
echo.
echo 下一步:
echo 1. 检查配置文件 .env 或 .env.development
echo 2. 启动后端服务: python main.py
echo 3. 访问 API 文档: http://localhost:8000/docs
echo 4. 使用管理员账号登录
echo 5. ⚠️  生产环境请立即修改管理员密码！
echo ==========================================

pause