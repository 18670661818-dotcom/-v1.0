"""系统设置路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import time

from utils.auth_utils import get_current_user
from models.database import User

router = APIRouter(prefix="/api/settings", tags=["系统设置"])

# 系统配置存储（实际应用中应该存储在数据库中）
system_config = {
    # 告警设置
    "alert_cooldown": 30,
    "alert_min_confidence": 0.6,
    "enable_sound_alert": True,
    "enable_email_alert": False,
    "alert_email": "",
    # 摄像头设置
    "frame_interval": 2,
    "max_concurrent_streams": 9,
    "auto_reconnect": True,
    "reconnect_interval": 10,
    # 检测设置
    "detection_enabled": True,
    "detection_sensitivity": 0.5,
    # 系统设置
    "data_retention_days": 30,
    "auto_cleanup": True,
    "maintenance_start": None,
    "maintenance_end": None,
}


class SystemConfig(BaseModel):
    # 告警设置
    alert_cooldown: Optional[int] = 30
    alert_min_confidence: Optional[float] = 0.6
    enable_sound_alert: Optional[bool] = True
    enable_email_alert: Optional[bool] = False
    alert_email: Optional[str] = ""
    # 摄像头设置
    frame_interval: Optional[int] = 2
    max_concurrent_streams: Optional[int] = 9
    auto_reconnect: Optional[bool] = True
    reconnect_interval: Optional[int] = 10
    # 检测设置
    detection_enabled: Optional[bool] = True
    detection_sensitivity: Optional[float] = 0.5
    # 系统设置
    data_retention_days: Optional[int] = 30
    auto_cleanup: Optional[bool] = True
    maintenance_start: Optional[str] = None
    maintenance_end: Optional[str] = None


@router.get("/config")
def get_config(
    current_user: User = Depends(get_current_user)
):
    """获取系统配置"""
    # 只有管理员可以获取完整配置
    if current_user.role.value != "admin":
        # 普通用户只能获取部分配置
        return {
            "alert_cooldown": system_config["alert_cooldown"],
            "alert_min_confidence": system_config["alert_min_confidence"],
            "enable_sound_alert": system_config["enable_sound_alert"],
            "enable_email_alert": system_config["enable_email_alert"],
            "frame_interval": system_config["frame_interval"],
            "detection_enabled": system_config["detection_enabled"],
            "detection_sensitivity": system_config["detection_sensitivity"],
        }

    return system_config


@router.put("/config")
def update_config(
    config: SystemConfig,
    current_user: User = Depends(get_current_user)
):
    """更新系统配置"""
    # 只有管理员可以更新配置
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="权限不足")

    # 更新配置
    config_dict = config.dict(exclude_unset=True)
    for key, value in config_dict.items():
        if value is not None:
            system_config[key] = value

    return {"message": "配置更新成功", "config": system_config}