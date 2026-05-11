"""操作日志模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from core.database import Base


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    username = Column(String(50), index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), index=True)  # 例如：camera, alert, user
    target_id = Column(String(100), index=True)  # 目标ID
    detail = Column(Text)  # 详细信息，JSON格式
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 关系
    user = relationship("User", back_populates="operation_logs")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )