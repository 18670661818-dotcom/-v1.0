"""pytest配置文件"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db
from models.database import init_db


# 使用内存SQLite数据库进行测试
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    """创建测试数据库引擎"""
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """创建测试数据库会话"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session):
    """创建测试用户"""
    from models.database import User, UserRole
    from utils.auth_utils import get_password_hash
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass"),
        company_name="Test Company",
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture(scope="function")
def test_admin(db_session):
    """创建测试管理员"""
    from models.database import User, UserRole
    from utils.auth_utils import get_password_hash
    
    admin = User(
        username="testadmin",
        email="admin@example.com",
        hashed_password=get_password_hash("adminpass"),
        company_name="Test Company",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    return admin


@pytest.fixture(scope="function")
def user_token(client, test_user):
    """获取普通用户令牌"""
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def admin_token(client, test_admin):
    """获取管理员令牌"""
    response = client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "adminpass"
    })
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def user_headers(user_token):
    """获取普通用户请求头"""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="function")
def admin_headers(admin_token):
    """获取管理员请求头"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="function")
def test_camera(db_session, test_admin):
    """创建测试摄像头"""
    from models.database import Camera, CameraStatus
    
    camera = Camera(
        camera_id="test_cam",
        name="测试摄像头",
        rtsp_url="rtsp://test.com/stream",
        location="测试位置",
        company_name=test_admin.company_name,
        user_id=test_admin.id,
        status=CameraStatus.ONLINE,
        is_active=True,
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    
    return camera


@pytest.fixture(scope="function")
def test_alert(db_session, test_admin, test_camera):
    """创建测试告警"""
    from models.database import Alert, AlertLevel, AlertStatus
    
    alert = Alert(
        alert_id="test_alert",
        camera_id=test_camera.camera_id,
        camera_name=test_camera.name,
        alert_type="smoke",
        violation_type="smoke",
        violation_name="发现烟雾",
        confidence=0.85,
        severity=AlertLevel.CRITICAL,
        status=AlertStatus.PENDING,
        user_id=test_admin.id,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    
    return alert


@pytest.fixture(scope="function")
def test_config(db_session):
    """创建测试配置"""
    from models.config import Config
    
    config = Config(
        key="test_config",
        value="test_value",
        value_type="string",
        description="测试配置",
        category="test",
        is_public=True,
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    
    return config