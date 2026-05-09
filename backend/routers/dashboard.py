"""
Kitchen AI System - Dashboard Routes
厨房AI系统仪表盘路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta

from models.database import get_db, Alert, Camera, User, CameraStatus, AlertLevel
from models.schemas import DashboardStats, AlertStats, CameraStats
from utils.auth_utils import get_current_user

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取仪表盘统计数据
    """
    # 摄像头统计
    if current_user.role.value == "admin":
        total_cameras = db.query(Camera).count()
        online_cameras = db.query(Camera).filter(
            Camera.status == CameraStatus.ONLINE
        ).count()
    else:
        total_cameras = db.query(Camera).filter(
            Camera.user_id == current_user.id
        ).count()
        online_cameras = db.query(Camera).filter(
            Camera.user_id == current_user.id,
            Camera.status == CameraStatus.ONLINE
        ).count()

    # 告警统计
    if current_user.role.value == "admin":
        total_alerts = db.query(Alert).count()
        # 统计未确认的告警（相当于pending）
        pending_alerts = db.query(Alert).filter(
            Alert.acknowledged_at.is_(None)
        ).count()
        # 统计严重级别的未确认告警
        critical_alerts = db.query(Alert).filter(
            Alert.level == AlertLevel.CRITICAL,
            Alert.acknowledged_at.is_(None)
        ).count()
    else:
        total_alerts = db.query(Alert).filter(
            Alert.user_id == current_user.id
        ).count()
        pending_alerts = db.query(Alert).filter(
            Alert.user_id == current_user.id,
            Alert.acknowledged_at.is_(None)
        ).count()
        critical_alerts = db.query(Alert).filter(
            Alert.user_id == current_user.id,
            Alert.level == AlertLevel.CRITICAL,
            Alert.acknowledged_at.is_(None)
        ).count()

    # 系统运行时间（假设从第一个摄像头创建时间开始计算）
    if current_user.role.value == "admin":
        first_camera = db.query(Camera).order_by(Camera.created_at.asc()).first()
    else:
        first_camera = db.query(Camera).filter(
            Camera.user_id == current_user.id
        ).order_by(Camera.created_at.asc()).first()

    system_uptime = 0.0
    if first_camera:
        uptime_delta = datetime.utcnow() - first_camera.created_at
        system_uptime = uptime_delta.total_seconds() / 3600  # 转换为小时

    return DashboardStats(
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_alerts=total_alerts,
        pending_alerts=pending_alerts,
        critical_alerts=critical_alerts,
        system_uptime=system_uptime
    )


@router.get("/alerts/stats", response_model=AlertStats)
def get_alert_dashboard_stats(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取告警仪表盘统计
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    if current_user.role.value == "admin":
        query = db.query(Alert).filter(Alert.detected_at >= start_date)
    else:
        query = db.query(Alert).filter(
            Alert.user_id == current_user.id,
            Alert.detected_at >= start_date
        )

    # 总数统计
    total = query.count()
    # 未确认的告警
    pending = query.filter(Alert.acknowledged_at.is_(None)).count()
    # 已确认的告警
    acknowledged = query.filter(Alert.acknowledged_at.isnot(None)).count()
    # 没有resolved状态，使用acknowledged作为近似
    resolved = 0

    # 按严重程度统计
    severity_stats = {}
    for level in AlertLevel:
        count = query.filter(Alert.level == level).count()
        severity_stats[level.value] = count

    return AlertStats(
        total=total,
        pending=pending,
        acknowledged=acknowledged,
        resolved=resolved,
        by_severity=severity_stats
    )


@router.get("/cameras/stats", response_model=CameraStats)
def get_camera_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取摄像头仪表盘统计
    """
    if current_user.role.value == "admin":
        query = db.query(Camera)
    else:
        query = db.query(Camera).filter(Camera.user_id == current_user.id)

    total = query.count()
    online = query.filter(Camera.status == CameraStatus.ONLINE).count()
    offline = query.filter(Camera.status == CameraStatus.OFFLINE).count()
    error = query.filter(Camera.status == CameraStatus.ERROR).count()
    # 没有MAINTENANCE状态，使用0
    maintenance = 0

    return CameraStats(
        total=total,
        online=online,
        offline=offline,
        error=error,
        maintenance=maintenance
    )


@router.get("/alerts/timeline")
def get_alert_timeline(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取告警时间线数据（用于图表）
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # 按日期分组统计告警数量
    if current_user.role.value == "admin":
        results = db.query(
            func.date(Alert.detected_at).label('date'),
            func.count(Alert.id).label('count')
        ).filter(
            Alert.detected_at >= start_date
        ).group_by(
            func.date(Alert.detected_at)
        ).order_by(
            func.date(Alert.detected_at)
        ).all()
    else:
        results = db.query(
            func.date(Alert.detected_at).label('date'),
            func.count(Alert.id).label('count')
        ).filter(
            Alert.user_id == current_user.id,
            Alert.detected_at >= start_date
        ).group_by(
            func.date(Alert.detected_at)
        ).order_by(
            func.date(Alert.detected_at)
        ).all()

    timeline = []
    for result in results:
        timeline.append({
            "date": result.date.isoformat(),
            "count": result.count
        })

    return {"timeline": timeline}


@router.get("/cameras/performance")
def get_camera_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取摄像头性能数据
    """
    if current_user.role.value == "admin":
        cameras = db.query(Camera).all()
    else:
        cameras = db.query(Camera).filter(
            Camera.user_id == current_user.id
        ).all()

    performance_data = []
    for camera in cameras:
        # 统计每个摄像头的未确认告警数量
        alert_count = db.query(Alert).filter(
            Alert.camera_id == camera.camera_id,
            Alert.acknowledged_at.is_(None)
        ).count()

        # 计算平均置信度
        avg_confidence = db.query(
            func.avg(Alert.confidence)
        ).filter(
            Alert.camera_id == camera.camera_id
        ).scalar() or 0.0

        performance_data.append({
            "camera_id": camera.camera_id,
            "camera_name": camera.name,
            "status": camera.status.value if camera.status else "offline",
            "pending_alerts": alert_count,
            "avg_confidence": round(float(avg_confidence), 2)
        })

    return {"performance": performance_data}


@router.get("/system/health")
def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取系统健康状态
    """
    # 检查数据库连接
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "error"

    # 检查摄像头状态
    if current_user.role.value == "admin":
        cameras = db.query(Camera).all()
    else:
        cameras = db.query(Camera).filter(Camera.user_id == current_user.id).all()
    
    total_cameras = len(cameras)
    online_cameras = sum(1 for c in cameras if c.status == CameraStatus.ONLINE)

    # 检查最近告警
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    if current_user.role.value == "admin":
        recent_alerts = db.query(Alert).filter(
            Alert.detected_at >= one_hour_ago
        ).count()
    else:
        recent_alerts = db.query(Alert).filter(
            Alert.user_id == current_user.id,
            Alert.detected_at >= one_hour_ago
        ).count()

    return {
        "database": db_status,
        "total_cameras": total_cameras,
        "online_cameras": online_cameras,
        "offline_cameras": total_cameras - online_cameras,
        "recent_alerts_1h": recent_alerts,
        "timestamp": datetime.utcnow().isoformat()
    }