"""用户模型测试"""
import pytest
from models.database import User, UserRole
from utils.auth_utils import get_password_hash, verify_password


def test_create_user(db_session):
    """测试创建用户"""
    user = User(
        username="newuser",
        email="new@example.com",
        hashed_password=get_password_hash("password"),
        company_name="Test Company",
        role=UserRole.VIEWER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    assert user.id is not None
    assert user.username == "newuser"
    assert user.email == "new@example.com"
    assert user.role == UserRole.VIEWER
    assert user.is_active is True


def test_user_roles(db_session):
    """测试用户角色"""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin"),
        company_name="Admin Company",
        role=UserRole.ADMIN,
    )
    operator = User(
        username="operator",
        email="operator@example.com",
        hashed_password=get_password_hash("operator"),
        company_name="Operator Company",
        role=UserRole.OPERATOR,
    )
    viewer = User(
        username="viewer",
        email="viewer@example.com",
        hashed_password=get_password_hash("viewer"),
        company_name="Viewer Company",
        role=UserRole.VIEWER,
    )
    
    db_session.add_all([admin, operator, viewer])
    db_session.commit()
    
    assert admin.role == UserRole.ADMIN
    assert operator.role == UserRole.OPERATOR
    assert viewer.role == UserRole.VIEWER


def test_password_hashing():
    """测试密码哈希"""
    password = "testpassword"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_user_unique_constraints(db_session):
    """测试用户唯一约束"""
    user1 = User(
        username="uniqueuser",
        email="unique@example.com",
        hashed_password=get_password_hash("pass1"),
        company_name="Company1",
    )
    db_session.add(user1)
    db_session.commit()
    
    # 测试用户名唯一性
    user2 = User(
        username="uniqueuser",
        email="different@example.com",
        hashed_password=get_password_hash("pass2"),
        company_name="Company2",
    )
    db_session.add(user2)
    
    with pytest.raises(Exception):  # 应该抛出唯一性约束异常
        db_session.commit()
    
    db_session.rollback()
    
    # 测试邮箱唯一性
    user3 = User(
        username="differentuser",
        email="unique@example.com",
        hashed_password=get_password_hash("pass3"),
        company_name="Company3",
    )
    db_session.add(user3)
    
    with pytest.raises(Exception):  # 应该抛出唯一性约束异常
        db_session.commit()


def test_user_default_values(db_session):
    """测试用户默认值"""
    user = User(
        username="defaultuser",
        email="default@example.com",
        hashed_password=get_password_hash("pass"),
        company_name="Default Company",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    assert user.role == UserRole.VIEWER  # 默认角色
    assert user.is_active is True  # 默认激活
    assert user.created_at is not None  # 自动设置创建时间