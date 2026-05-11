"""
数据库迁移脚本
从 SQLite 迁移到 PostgreSQL
"""
import os
import sys
import sqlite3
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.config import settings


def export_sqlite_data(sqlite_db_path: str) -> dict:
    """从 SQLite 导出数据"""
    print(f"正在从 SQLite 导出数据: {sqlite_db_path}")
    
    if not os.path.exists(sqlite_db_path):
        print(f"错误: SQLite 数据库文件不存在: {sqlite_db_path}")
        return {}
    
    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {}
    
    # 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row['name'] for row in cursor.fetchall()]
    
    for table in tables:
        print(f"  导出表: {table}")
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        data[table] = [dict(row) for row in rows]
        print(f"    导出 {len(rows)} 条记录")
    
    conn.close()
    return data


def import_to_postgres(data: dict, postgres_url: str):
    """导入数据到 PostgreSQL"""
    print(f"\n正在导入数据到 PostgreSQL...")
    
    # 创建 PostgreSQL 引擎
    engine = create_engine(postgres_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 创建表结构
        from models.database import Base
        Base.metadata.create_all(bind=engine)
        print("数据库表结构创建完成")
        
        # 导入数据
        for table_name, rows in data.items():
            if not rows:
                continue
            
            print(f"  导入表: {table_name} ({len(rows)} 条记录)")
            
            # 构建 INSERT 语句
            columns = rows[0].keys()
            placeholders = ', '.join([f':{col}' for col in columns])
            columns_str = ', '.join(columns)
            
            insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            
            # 批量插入
            for row in rows:
                try:
                    session.execute(text(insert_sql), row)
                except Exception as e:
                    print(f"    警告: 插入记录失败: {e}")
                    session.rollback()
                    continue
            
            session.commit()
            print(f"    导入完成")
        
        print("\n数据导入成功！")
        
    except Exception as e:
        print(f"错误: 数据导入失败: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    """主函数"""
    print("=" * 60)
    print("Kitchen AI - SQLite 到 PostgreSQL 迁移工具")
    print("=" * 60)
    
    # 配置
    sqlite_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kitchen_ai.db")
    
    # PostgreSQL 连接字符串
    postgres_url = os.getenv("DATABASE_URL", "postgresql://kitchen_user:kitchen_password@localhost:5432/kitchen_ai")
    
    print(f"\n配置信息:")
    print(f"  SQLite 数据库: {sqlite_db_path}")
    print(f"  PostgreSQL 连接: {postgres_url}")
    
    # 确认迁移
    confirm = input("\n是否继续迁移？(y/n): ").strip().lower()
    if confirm != 'y':
        print("迁移已取消")
        return
    
    try:
        # 1. 导出 SQLite 数据
        data = export_sqlite_data(sqlite_db_path)
        
        if not data:
            print("没有数据需要迁移")
            return
        
        # 2. 导入到 PostgreSQL
        import_to_postgres(data, postgres_url)
        
        # 3. 备份原 SQLite 数据库
        backup_path = f"{sqlite_db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(sqlite_db_path, backup_path)
        print(f"\nSQLite 数据库已备份到: {backup_path}")
        
        print("\n" + "=" * 60)
        print("迁移完成！")
        print("=" * 60)
        print("\n下一步:")
        print("1. 更新 .env.production 文件中的 DATABASE_URL")
        print("2. 重启后端服务")
        print("3. 验证数据是否正确迁移")
        
    except Exception as e:
        print(f"\n迁移失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()