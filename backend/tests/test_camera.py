"""摄像头模型测试"""
import pytest
from models.database import Camera, CameraStatus, User, UserRole
from utils.auth_utils import get_password_hash


@pytest.fixture
def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="camerauser",
        email="camera@example.com",
        hashed_password=get_password_hash("password"),
        company_name="Camera Company",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_camera(db_session, test_user):
    """测试创建摄像头"""
    camera = Camera(
        camera_id="cam_001",
        name="测试摄像头",
        rtsp_url="rtsp://test.com/stream",
        location="厨房",
        company_name=test_user.company_name,
        user_id=test_user.id,
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    
    assert camera.id is not None
    assert camera.camera_id == "cam_001"
    assert camera.name == "测试摄像头"
    assert camera.status == CameraStatus.OFFLINE
    assert camera.is_active is True


def test_camera_status(db_session, test_user):
    """测试摄像头状态"""
    camera = Camera(
        camera_id="status_cam",
        name="状态测试摄像头",
        rtsp_url="rtsp://test.com/status",
        location="大厅",
        company_name=test_user.company_name,
        user_id=test_user.id,
    )
    
    # 测试不同状态
    camera.status = CameraStatus.ONLINE
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    
    assert camera.status == CameraStatus.ONLINE
    
    camera.status = CameraStatus.ERROR
    db_session.commit()
    db_session.refresh(camera)
    
    assert camera.status == CameraStatus.ERROR


def test_camera_enabled_flag(db_session, test_user):
    """测试摄像头启用标志"""
    camera = Camera(
        camera_id="enabled_cam",
        name="启用测试摄像头",
        rtsp_url="rtsp://test.com/enabled",
        location="走廊",
        company_name=test_user.company_name,
        user_id=test_user.id,
        is_active=False,
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)

    assert camera.is_active is False


def test_camera_unique_id(db_session, test_user):
    """测试摄像头ID唯一性"""
    camera1 = Camera(
        camera_id="unique_cam",
        name="摄像头1",
        rtsp_url="rtsp://test.com/1",
        location="位置1",
        company_name=test_user.company_name,
        user_id=test_user.id,
    )
    db_session.add(camera1)
    db_session.commit()
    
    camera2 = Camera(
        camera_id="unique_cam",  # 相同的camera_id
        name="摄像头2",
        rtsp_url="rtsp://test.com/2",
        location="位置2",
        company_name=test_user.company_name,
        user_id=test_user.id,
    )
    db_session.add(camera2)
    
    with pytest.raises(Exception):  # 应该抛出唯一性约束异常
        db_session.commit()


def test_camera_user_relationship(db_session, test_user):
    """测试摄像头与用户的关系"""
    camera = Camera(
        camera_id="relation_cam",
        name="关系测试摄像头",
        rtsp_url="rtsp://test.com/relation",
        location="办公室",
        company_name=test_user.company_name,
        user_id=test_user.id,
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    
    # 验证关系
    assert camera.owner.id == test_user.id
    assert camera in test_user.cameras