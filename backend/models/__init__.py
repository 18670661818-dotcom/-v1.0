"""
数据库模型模块
导出所有模型以便其他模块使用
"""
from .user import User, UserRole
from .camera import Camera, CameraStatus
from .alert import Alert, AlertLevel, AlertStatus
from .operation_log import OperationLog

# 保持向后兼容，从database.py导入其他模型
from .database import DetectionLog

__all__ = [
    "User", "UserRole",
    "Camera", "CameraStatus",
    "Alert", "AlertLevel", "AlertStatus",
    "OperationLog",
    "DetectionLog",
]
