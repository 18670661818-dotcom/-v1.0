"""更新数据库初始化脚本"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.models.database import init_db

if __name__ == "__main__":
    print("正在初始化数据库...")
    init_db()
    print("数据库初始化完成")
