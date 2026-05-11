"""
数据库初始化脚本
用于首次部署时创建数据库表结构和基础数据
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.config import settings
from core.database import engine, SessionLocal, Base
from core.logger import database_log


def check_database_connection():
    """检查数据库连接"""
    print("检查数据库连接...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ 数据库连接成功")
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def create_tables():
    """创建数据库表"""
    print("\n创建数据库表...")
    try:
        # 导入所有模型以确保它们被注册
        from models.database import DetectionLog
        from models.user import User
        from models.camera import Camera
        from models.alert import Alert
        from models.config import Config

        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✓ 数据库表创建成功")
        return True
    except Exception as e:
        print(f"✗ 数据库表创建失败: {e}")
        database_log.error(f"数据库表创建失败: {e}")
        return False


def run_migrations():
    """运行数据库迁移（轻量级迁移）"""
    print("\n运行数据库迁移...")
    try:
        from models.database import _ensure_alert_schema, _ensure_schema_updates
        _ensure_alert_schema()
        _ensure_schema_updates()
        print("✓ 数据库迁移完成")
        return True
    except Exception as e:
        print(f"✗ 数据库迁移失败: {e}")
        database_log.error(f"数据库迁移失败: {e}")
        return False


def create_default_admin():
    """创建默认管理员账号"""
    print("\n创建默认管理员账号...")
    try:
        from models.user import User, UserRole
        from utils.auth_utils import get_password_hash

        db = SessionLocal()
        try:
            # 检查管理员是否已存在
            admin = db.query(User).filter(User.username == "admin").first()
            if admin:
                print("✓ 管理员账号已存在")
                return True

            # 创建管理员账号
            admin = User(
                username="admin",
                email="admin@kitchen-ai.com",
                hashed_password=get_password_hash("admin123456"),
                company_name="Kitchen AI",
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            print("✓ 默认管理员账号创建成功")
            print("  用户名: admin")
            print("  密码: admin123456")
            print("  ⚠️  请在生产环境中立即修改密码！")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"✗ 管理员账号创建失败: {e}")
        database_log.error(f"管理员账号创建失败: {e}")
        return False


def create_default_config():
    """创建默认配置"""
    print("\n创建默认配置...")
    try:
        from models.config import Config

        db = SessionLocal()
        try:
            # 检查配置是否已存在
            config_count = db.query(Config).count()
            if config_count > 0:
                print("✓ 配置已存在")
                return True

            # 创建默认配置
            default_configs = [
                Config(key="system_name", value="后厨智能监测系统", description="系统名称"),
                Config(key="alert_cooldown", value="30", description="告警冷却时间（秒）"),
                Config(key="detection_fps", value="3", description="检测帧率"),
                Config(key="confidence_threshold", value="0.4", description="置信度阈值"),
                Config(key="max_alerts_per_hour", value="100", description="每小时最大告警数"),
            ]

            for config in default_configs:
                db.add(config)
            db.commit()
            print("✓ 默认配置创建成功")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"✗ 默认配置创建失败: {e}")
        database_log.error(f"默认配置创建失败: {e}")
        return False


def optimize_database():
    """优化数据库"""
    print("\n优化数据库...")
    try:
        if "sqlite" in settings.DATABASE_URL:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA optimize"))
                conn.execute(text("PRAGMA analysis_limit=1000"))
                conn.execute(text("PRAGMA cache_size=-2000"))
            print("✓ SQLite 数据库优化完成")
        else:
            print("✓ PostgreSQL 数据库无需手动优化")
        return True
    except Exception as e:
        print(f"✗ 数据库优化失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Kitchen AI - 数据库初始化脚本")
    print("=" * 60)
    print(f"\n数据库类型: {settings.DATABASE_URL.split('://')[0]}")
    print(f"数据库连接: {settings.DATABASE_URL}")

    # 确认初始化
    confirm = input("\n是否继续初始化数据库？(y/n): ").strip().lower()
    if confirm != 'y':
        print("初始化已取消")
        return

    # 执行初始化步骤
    steps = [
        ("检查数据库连接", check_database_connection),
        ("创建数据库表", create_tables),
        ("运行数据库迁移", run_migrations),
        ("创建默认管理员", create_default_admin),
        ("创建默认配置", create_default_config),
        ("优化数据库", optimize_database),
    ]

    success_count = 0
    for step_name, step_func in steps:
        if step_func():
            success_count += 1
        else:
            print(f"\n⚠️  步骤 '{step_name}' 失败，但继续执行后续步骤...")

    # 输出结果
    print("\n" + "=" * 60)
    if success_count == len(steps):
        print("✅ 数据库初始化完成！")
    else:
        print(f"⚠️  数据库初始化部分完成 ({success_count}/{len(steps)} 步骤成功)")
    print("=" * 60)

    print("\n下一步:")
    print("1. 启动后端服务: python main.py")
    print("2. 访问 API 文档: http://localhost:8000/docs")
    print("3. 使用管理员账号登录")
    print("4. ⚠️  生产环境请立即修改管理员密码！")


if __name__ == "__main__":
    main()