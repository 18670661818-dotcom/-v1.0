"""Pydantic数据验证模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# ==================== 用户相关 ====================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    company_name: str = Field(..., min_length=2)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    company_name: str
    role: str
    is_active: bool
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user_info: UserResponse


# ==================== 摄像头相关 ====================
class CameraCreate(BaseModel):
    camera_id: str
    name: str
    rtsp_url: str
    location: str = ""
    enabled: bool = True


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None


class CameraResponse(BaseModel):
    id: int
    camera_id: str
    name: str
    rtsp_url: str
    location: str
    status: str
    enabled: bool
    last_heartbeat: Optional[datetime]
    alerts_count: int = 0

    class Config:
        from_attributes = True


# ==================== 告警相关 ====================
class AlertResponse(BaseModel):
    id: int
    alert_id: str
    camera_id: str
    camera_name: str
    violation_type: str
    violation_name: str
    confidence: float
    level: str
    detected_at: datetime
    acknowledged_at: Optional[datetime]
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    alert_ids: List[str]


class AlertQuery(BaseModel):
    camera_id: Optional[str] = None
    violation_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    level: Optional[str] = None
    page: int = 1
    page_size: int = 20


class AlertStats(BaseModel):
    total_today: int
    total_week: int
    by_type: dict
    by_camera: dict
    trend: List[dict]


# ==================== Dashboard ====================
class DashboardStats(BaseModel):
    total_cameras: int
    online_cameras: int
    total_alerts: int
    pending_alerts: int
    critical_alerts: int
    system_uptime: float


class AlertStatsDetailed(BaseModel):
    total: int
    pending: int
    acknowledged: int
    resolved: int
    by_severity: dict


class CameraStats(BaseModel):
    total: int
    online: int
    offline: int
    error: int
    maintenance: int


class DashboardData(BaseModel):
    cameras_online: int
    cameras_total: int
    alerts_today: int
    gpu_usage: float = 0
    fps_avg: float = 0
    recent_alerts: List[AlertResponse]
    alert_stats: AlertStats