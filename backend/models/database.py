"""SQLAlchemy数据库模型"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Boolean, ForeignKey, Text, Enum, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_recycle=3600,   # 每小时回收连接
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"          # 超级管理员
    MANAGER = "manager"      # 企业管理员
    VIEWER = "viewer"        # 普通查看者


class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class AlertLevel(str, enum.Enum):
    CRITICAL = "critical"    # 严重违规
    WARNING = "warning"      # 一般违规
    INFO = "info"            # 提示


class User(Base):
    """企业用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    company_name = Column(String(200), index=True)  # 企业名称，添加索引
    role = Column(Enum(UserRole), default=UserRole.VIEWER, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # 关联
    cameras = relationship("Camera", back_populates="owner")
    alerts = relationship("Alert", back_populates="owner", foreign_keys="Alert.user_id")


class Camera(Base):
    """摄像头配置表"""
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    rtsp_url = Column(String(500), nullable=False)
    location = Column(String(300))
    status = Column(Enum(CameraStatus), default=CameraStatus.OFFLINE, index=True)
    enabled = Column(Boolean, default=True, index=True)

    # 所属企业和用户
    company_name = Column(String(200), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    owner = relationship("User", back_populates="cameras")

    created_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat = Column(DateTime)

    # 关联告警
    alerts = relationship("Alert", back_populates="camera", foreign_keys="Alert.camera_id")

    # 复合索引 - 用于按用户和状态查询
    __table_args__ = (
        Index('idx_camera_user_status', 'user_id', 'status'),
        Index('idx_camera_company_status', 'company_name', 'status'),
    )


class Alert(Base):
    """告警记录表"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, index=True)  # UUID
    camera_id = Column(String(100), ForeignKey("cameras.camera_id"), index=True)
    camera_name = Column(String(200))

    # 违规详情
    violation_type = Column(String(100), nullable=False, index=True)  # no_hat, smoke等
    violation_name = Column(String(200))  # 中文名称
    confidence = Column(Float, default=0.0)
    level = Column(Enum(AlertLevel), default=AlertLevel.WARNING, index=True)

    # 时间信息
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime, index=True)  # 确认时间
    acknowledged_by = Column(Integer, ForeignKey("users.id"))

    # 截图路径
    image_path = Column(String(500))

    # 关联
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    owner = relationship("User", back_populates="alerts", foreign_keys=[user_id])
    camera = relationship("Camera", back_populates="alerts")

    created_at = Column(DateTime, default=datetime.utcnow)

    # 复合索引 - 用于常见查询场景
    __table_args__ = (
        # 按用户查询告警，按时间排序
        Index('idx_alert_user_detected', 'user_id', 'detected_at'),
        # 按摄像头查询告警
        Index('idx_alert_camera_detected', 'camera_id', 'detected_at'),
        # 查询未确认的告警
        Index('idx_alert_acknowledged', 'acknowledged_at', 'level'),
        # 按类型和级别查询
        Index('idx_alert_type_level', 'violation_type', 'level'),
        # 今日告警统计
        Index('idx_alert_user_level_detected', 'user_id', 'level', 'detected_at'),
    )


class DetectionLog(Base):
    """检测日志表（用于统计分析）"""
    __tablename__ = "detection_logs"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(100), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    class_name = Column(String(100), index=True)
    count = Column(Integer, default=0)

    # 复合索引 - 用于统计查询
    __table_args__ = (
        Index('idx_detection_camera_timestamp', 'camera_id', 'timestamp'),
        Index('idx_detection_class_timestamp', 'class_name', 'timestamp'),
    )


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)

    # 创建默认管理员账户
    db = SessionLocal()
    try:
        from utils.auth_utils import get_password_hash

        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@kitchen-ai.com",
                hashed_password=get_password_hash("admin123"),
                company_name="系统管理",
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            print("✅ 默认管理员账户已创建: admin/admin123")
    finally:
        db.close()


# 依赖注入：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def optimize_database():
    """数据库优化 - 重建索引和清理"""
    if "sqlite" in DATABASE_URL:
        with engine.connect() as conn:
            conn.execute("PRAGMA optimize")
            conn.execute("PRAGMA analysis_limit=1000")
            conn.execute("PRAGMA cache_size=-2000")  # 2MB缓存
            print("✅ SQLite 优化完成")