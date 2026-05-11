"""摄像头模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from core.database import Base


class CameraStatus(enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    rtsp_url = Column(String(500), nullable=False)
    location = Column(String(300))
    description = Column(String(500))
    status = Column(Enum(CameraStatus, name="camera_status"), default=CameraStatus.OFFLINE, index=True)
    # 映射现有enabled字段到is_active
    is_active = Column("enabled", Boolean, default=True, index=True)
    detection_enabled = Column(Boolean, default=True, index=True)
    company_name = Column(String(200), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_heartbeat = Column(DateTime)
    last_online_at = Column(DateTime)
    last_offline_at = Column(DateTime)

    # 关系
    owner = relationship("User", back_populates="cameras")
    alerts = relationship("Alert", back_populates="camera", foreign_keys="Alert.camera_id")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )