#!/bin/bash

# PostgreSQL 初始化脚本
# 用于生产环境数据库初始化

set -e

echo "=========================================="
echo "Kitchen AI - PostgreSQL 初始化脚本"
echo "=========================================="

# 配置参数
DB_NAME="kitchen_ai"
DB_USER="kitchen_user"
DB_PASSWORD="kitchen_password"
DB_HOST="localhost"
DB_PORT="5432"

# 检查 PostgreSQL 是否运行
echo "检查 PostgreSQL 服务状态..."
if ! command -v psql &> /dev/null; then
    echo "错误: 未找到 psql 命令，请先安装 PostgreSQL 客户端"
    exit 1
fi

# 创建数据库用户
echo "创建数据库用户: $DB_USER"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || echo "用户已存在，跳过"

# 创建数据库
echo "创建数据库: $DB_NAME"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo "数据库已存在，跳过"

# 授予权限
echo "授予权限..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# 创建扩展（可选）
echo "创建数据库扩展..."
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || true

echo "=========================================="
echo "PostgreSQL 初始化完成！"
echo "=========================================="
echo ""
echo "数据库连接信息："
echo "  主机: $DB_HOST"
echo "  端口: $DB_PORT"
echo "  数据库: $DB_NAME"
echo "  用户: $DB_USER"
echo "  密码: $DB_PASSWORD"
echo ""
echo "连接字符串："
echo "  postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "请将此连接字符串添加到 .env.production 文件中"
echo "=========================================="