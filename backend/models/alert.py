"""告警模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, ForeignKey, Text, Index
from sqlalchemy.orm import relationship

from core.database import Base


class AlertLevel(enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(enum.Enum):
    PENDING = "pending"  # 对应 unhandled
    CONFIRMED = "confirmed"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, index=True)
    camera_id = Column(String(100), ForeignKey("cameras.camera_id"), index=True)
    camera_name = Column(String(200))
    alert_type = Column(String(100), nullable=False, index=True)
    violation_type = Column(String(100), index=True)
    violation_name = Column(String(200))
    confidence = Column(Float, default=0.0)
    # 映射现有level字段到severity
    severity = Column("level", Enum(AlertLevel, name="alert_level"), default=AlertLevel.WARNING, index=True)
    status = Column(Enum(AlertStatus, name="alert_status"), default=AlertStatus.PENDING, index=True)
    image_path = Column(String(500))
    video_clip_path = Column(String(500))
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime, index=True)
    resolved_at = Column(DateTime, index=True)
    acknowledged_at = Column(DateTime, index=True)
    acknowledged_by = Column(Integer, index=True)
    handled_by = Column(String(100))
    remark = Column(Text)
    is_false_positive = Column(Boolean, default=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # 关系
    owner = relationship("User", back_populates="alerts", foreign_keys=[user_id])
    camera = relationship("Camera", back_populates="alerts")

    __table_args__ = (
        # 复合索引，优化常见查询
        Index("idx_alert_camera_detected", "camera_id", "detected_at"),
        Index("idx_alert_user_detected", "user_id", "detected_at"),
        Index("idx_alert_status_detected", "status", "detected_at"),
        Index("idx_alert_severity_detected", "level", "detected_at"),
        {"sqlite_autoincrement": True},
    )