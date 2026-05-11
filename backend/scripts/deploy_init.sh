#!/bin/bash

# Kitchen AI - 部署初始化脚本

set -e

echo "=========================================="
echo "Kitchen AI - 部署初始化脚本"
echo "=========================================="

# 检查 Python 环境
echo "检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到 Python，请先安装 Python 3.7+"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "Python 环境检查通过: $($PYTHON_CMD --version)"

# 检查依赖
echo "检查项目依赖..."
if ! pip show fastapi &> /dev/null; then
    echo "警告: 未检测到 FastAPI，正在安装依赖..."
    pip install -r requirements.txt
fi

echo "依赖检查完成"

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p storage/alerts
mkdir -p storage/logs
mkdir -p models

echo "目录创建完成"

# 数据库初始化
echo ""
echo "=========================================="
echo "步骤 1: 数据库初始化"
echo "=========================================="
$PYTHON_CMD scripts/init_db.py || echo "警告: 数据库初始化可能未完全成功，请检查上述输出"

# 创建管理员账号（如果需要）
echo ""
echo "=========================================="
echo "步骤 2: 创建管理员账号"
echo "=========================================="

# 检查是否已有管理员账号
if ! $PYTHON_CMD -c "from scripts.create_admin import list_admin_users; list_admin_users()" 2>/dev/null; then
    echo "创建默认管理员账号..."
    $PYTHON_CMD scripts/create_admin.py create --username admin --password admin123456 --email admin@kitchen-ai.com
fi

echo ""
echo "=========================================="
echo "部署初始化完成！"
echo "=========================================="
echo ""
echo "下一步:"
echo "1. 检查配置文件 .env 或 .env.development"
echo "2. 启动后端服务: $PYTHON_CMD main.py"
echo "3. 访问 API 文档: http://localhost:8000/docs"
echo "4. 使用管理员账号登录"
echo "5. ⚠️  生产环境请立即修改管理员密码！"
echo "=========================================="