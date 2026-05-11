"""
管理员账号创建脚本
用于创建或重置管理员账号
"""
import os
import sys
import argparse

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.config import settings
from core.database import SessionLocal
from core.logger import database_log


def create_admin_user(username: str, password: str, email: str = None, company_name: str = "Kitchen AI"):
    """
    创建管理员账号

    Args:
        username: 用户名
        password: 密码（将被哈希存储）
        email: 邮箱（可选）
        company_name: 公司名称

    Returns:
        bool: 是否创建成功
    """
    try:
        from models.user import User, UserRole
        from utils.auth_utils import get_password_hash

        db = SessionLocal()
        try:
            # 检查用户名是否已存在
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                print(f"✗ 用户名 '{username}' 已存在")
                return False

            # 检查邮箱是否已存在
            if email:
                existing_email = db.query(User).filter(User.email == email).first()
                if existing_email:
                    print(f"✗ 邮箱 '{email}' 已被使用")
                    return False

            # 创建管理员账号
            admin = User(
                username=username,
                email=email or f"{username}@kitchen-ai.com",
                hashed_password=get_password_hash(password),
                company_name=company_name,
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

            print(f"✓ 管理员账号创建成功")
            print(f"  用户ID: {admin.id}")
            print(f"  用户名: {admin.username}")
            print(f"  邮箱: {admin.email}")
            print(f"  角色: {admin.role.value}")
            print(f"  创建时间: {admin.created_at}")

            database_log.info(f"管理员账号创建成功: {username}")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"✗ 管理员账号创建失败: {e}")
        database_log.error(f"管理员账号创建失败: {e}")
        return False


def reset_admin_password(username: str, new_password: str):
    """
    重置管理员密码

    Args:
        username: 用户名
        new_password: 新密码

    Returns:
        bool: 是否重置成功
    """
    try:
        from models.user import User
        from utils.auth_utils import get_password_hash

        db = SessionLocal()
        try:
            # 查找用户
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"✗ 用户 '{username}' 不存在")
                return False

            # 更新密码
            user.hashed_password = get_password_hash(new_password)
            db.commit()

            print(f"✓ 密码重置成功")
            print(f"  用户名: {user.username}")
            print(f"  新密码: {new_password}")

            database_log.info(f"管理员密码重置成功: {username}")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"✗ 密码重置失败: {e}")
        database_log.error(f"密码重置失败: {e}")
        return False


def list_admin_users():
    """列出所有管理员账号"""
    try:
        from models.user import User, UserRole

        db = SessionLocal()
        try:
            admins = db.query(User).filter(User.role == UserRole.ADMIN).all()

            if not admins:
                print("没有找到管理员账号")
                return

            print(f"\n找到 {len(admins)} 个管理员账号:")
            print("-" * 80)
            print(f"{'ID':<5} {'用户名':<20} {'邮箱':<30} {'创建时间':<20}")
            print("-" * 80)

            for admin in admins:
                created_at = admin.created_at.strftime("%Y-%m-%d %H:%M") if admin.created_at else "N/A"
                print(f"{admin.id:<5} {admin.username:<20} {admin.email:<30} {created_at:<20}")

            print("-" * 80)
        finally:
            db.close()
    except Exception as e:
        print(f"✗ 查询管理员账号失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Kitchen AI - 管理员账号管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 创建管理员命令
    create_parser = subparsers.add_parser("create", help="创建管理员账号")
    create_parser.add_argument("--username", "-u", required=True, help="用户名")
    create_parser.add_argument("--password", "-p", required=True, help="密码")
    create_parser.add_argument("--email", "-e", help="邮箱（可选）")
    create_parser.add_argument("--company", "-c", default="Kitchen AI", help="公司名称")

    # 重置密码命令
    reset_parser = subparsers.add_parser("reset-password", help="重置管理员密码")
    reset_parser.add_argument("--username", "-u", required=True, help="用户名")
    reset_parser.add_argument("--password", "-p", required=True, help="新密码")

    # 列出管理员命令
    subparsers.add_parser("list", help="列出所有管理员账号")

    args = parser.parse_args()

    print("=" * 60)
    print("Kitchen AI - 管理员账号管理工具")
    print("=" * 60)

    if args.command == "create":
        print(f"\n创建管理员账号: {args.username}")
        create_admin_user(args.username, args.password, args.email, args.company)

    elif args.command == "reset-password":
        print(f"\n重置管理员密码: {args.username}")
        reset_admin_password(args.username, args.password)

    elif args.command == "list":
        list_admin_users()

    else:
        parser.print_help()
        print("\n示例用法:")
        print("  创建管理员: python create_admin.py create --username admin --password admin123456")
        print("  重置密码: python create_admin.py reset-password --username admin --password newpass123")
        print("  列出管理员: python create_admin.py list")


if __name__ == "__main__":
    main()