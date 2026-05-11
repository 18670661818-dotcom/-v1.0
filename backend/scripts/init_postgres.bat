@echo off
chcp 65001 >nul

echo ==========================================
echo Kitchen AI - PostgreSQL 初始化脚本
echo ==========================================

REM 配置参数
set DB_NAME=kitchen_ai
set DB_USER=kitchen_user
set DB_PASSWORD=kitchen_password
set DB_HOST=localhost
set DB_PORT=5432

REM 检查 PostgreSQL 是否安装
where psql >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 未找到 psql 命令
    echo 请先安装 PostgreSQL 客户端或将其添加到 PATH 环境变量
    echo 下载地址: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

echo 检查 PostgreSQL 服务状态...
pg_isready -h %DB_HOST% -p %DB_PORT% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 无法连接到 PostgreSQL 服务
    echo 请确保 PostgreSQL 服务正在运行
    pause
    exit /b 1
)

echo PostgreSQL 服务运行正常

REM 创建数据库用户
echo 创建数据库用户: %DB_USER%
psql -h %DB_HOST% -p %DB_PORT% -U postgres -c "CREATE USER %DB_USER% WITH PASSWORD '%DB_PASSWORD%';" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo 用户创建成功
) else (
    echo 用户已存在或创建失败，继续执行...
)

REM 创建数据库
echo 创建数据库: %DB_NAME%
psql -h %DB_HOST% -p %DB_PORT% -U postgres -c "CREATE DATABASE %DB_NAME% OWNER %DB_USER%;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo 数据库创建成功
) else (
    echo 数据库已存在或创建失败，继续执行...
)

REM 授予权限
echo 授予权限...
psql -h %DB_HOST% -p %DB_PORT% -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE %DB_NAME% TO %DB_USER%;"

REM 创建扩展（可选）
echo 创建数据库扩展...
psql -h %DB_HOST% -p %DB_PORT% -U postgres -d %DB_NAME% -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>nul

echo ==========================================
echo PostgreSQL 初始化完成！
echo ==========================================
echo.
echo 数据库连接信息：
echo   主机: %DB_HOST%
echo   端口: %DB_PORT%
echo   数据库: %DB_NAME%
echo   用户: %DB_USER%
echo   密码: %DB_PASSWORD%
echo.
echo 连接字符串：
echo   postgresql://%DB_USER%:%DB_PASSWORD%@%DB_HOST%:%DB_PORT%/%DB_NAME%
echo.
echo 请将此连接字符串添加到 .env.production 文件中
echo ==========================================

pause