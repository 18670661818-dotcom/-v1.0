"""告警模型测试"""
import pytest
from datetime import datetime
from models.database import Alert, AlertLevel, AlertStatus, Camera, CameraStatus, User, UserRole
from utils.auth_utils import get_password_hash


@pytest.fixture
def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="alertuser",
        email="alert@example.com",
        hashed_password=get_password_hash("password"),
        company_name="Alert Company",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_camera(db_session, test_user):
    """创建测试摄像头"""
    camera = Camera(
        camera_id="alert_cam",
        name="告警测试摄像头",
        rtsp_url="rtsp://test.com/alert",
        location="厨房",
        company_name=test_user.company_name,
        user_id=test_user.id,
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    return camera


def test_create_alert(db_session, test_user, test_camera):
    """测试创建告警"""
    alert = Alert(
        alert_id="alert_001",
        camera_id=test_camera.camera_id,
        camera_name=test_camera.name,
        alert_type="smoke",
        violation_type="smoke",
        violation_name="发现烟雾",
        confidence=0.85,
        severity=AlertLevel.CRITICAL,
        user_id=test_user.id,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    
    assert alert.id is not None
    assert alert.alert_id == "alert_001"
    assert alert.severity == AlertLevel.CRITICAL
    assert alert.status == AlertStatus.PENDING


def test_alert_levels(db_session, test_user, test_camera):
    """测试告警级别"""
    critical_alert = Alert(
        alert_id="critical_alert",
        camera_id=test_camera.camera_id,
        alert_type="fire",
        violation_type="fire",
        severity=AlertLevel.CRITICAL,
        user_id=test_user.id,
    )
    warning_alert = Alert(
        alert_id="warning_alert",
        camera_id=test_camera.camera_id,
        alert_type="smoke",
        violation_type="smoke",
        severity=AlertLevel.WARNING,
        user_id=test_user.id,
    )
    info_alert = Alert(
        alert_id="info_alert",
        camera_id=test_camera.camera_id,
        alert_type="info",
        violation_type="info",
        severity=AlertLevel.INFO,
        user_id=test_user.id,
    )
    
    db_session.add_all([critical_alert, warning_alert, info_alert])
    db_session.commit()
    
    assert critical_alert.severity == AlertLevel.CRITICAL
    assert warning_alert.severity == AlertLevel.WARNING
    assert info_alert.severity == AlertLevel.INFO


def test_alert_status(db_session, test_user, test_camera):
    """测试告警状态"""
    alert = Alert(
        alert_id="status_alert",
        camera_id=test_camera.camera_id,
        alert_type="smoke",
        violation_type="smoke",
        severity=AlertLevel.WARNING,
        user_id=test_user.id,
    )
    
    # 测试状态变更
    alert.status = AlertStatus.CONFIRMED
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    
    assert alert.status == AlertStatus.CONFIRMED
    
    alert.status = AlertStatus.RESOLVED
    db_session.commit()
    db_session.refresh(alert)
    
    assert alert.status == AlertStatus.RESOLVED


def test_alert_timestamps(db_session, test_user, test_camera):
    """测试告警时间戳"""
    alert = Alert(
        alert_id="timestamp_alert",
        camera_id=test_camera.camera_id,
        alert_type="smoke",
        violation_type="smoke",
        severity=AlertLevel.WARNING,
        user_id=test_user.id,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    
    assert alert.created_at is not None
    assert alert.detected_at is not None
    
    # 测试确认时间
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = test_user.id
    db_session.commit()
    db_session.refresh(alert)
    
    assert alert.acknowledged_at is not None
    assert alert.acknowledged_by == test_user.id


def test_alert_camera_relationship(db_session, test_user, test_camera):
    """测试告警与摄像头的关系"""
    alert = Alert(
        alert_id="relation_alert",
        camera_id=test_camera.camera_id,
        alert_type="smoke",
        violation_type="smoke",
        severity=AlertLevel.WARNING,
        user_id=test_user.id,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    
    # 验证关系
    assert alert.camera.id == test_camera.id
    assert alert in test_camera.alerts


def test_alert_user_relationship(db_session, test_user, test_camera):
    """测试告警与用户的关系"""
    alert = Alert(
        alert_id="user_alert",
        camera_id=test_camera.camera_id,
        alert_type="smoke",
        violation_type="smoke",
        severity=AlertLevel.WARNING,
        user_id=test_user.id,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    
    # 验证关系
    assert alert.owner.id == test_user.id
    assert alert in test_user.alerts