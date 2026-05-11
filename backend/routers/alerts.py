"""告警管理路由"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional

from models.database import get_db, User, Alert, AlertLevel, Camera
from models.schemas import AlertAcknowledge
from utils.auth_utils import get_current_user
from core.cache_manager import cached
import os

router = APIRouter(prefix="/api/alerts", tags=["告警管理"])


# 违规类别中文映射
VIOLATION_NAMES = {
    "cockroach": "发现蟑螂",
    "hairnet": "佩戴发网",
    "no_gloves": "未戴手套",
    "no_hat": "未戴帽子",
    "rat": "发现老鼠",
    "with_mask": "佩戴口罩",
    "without_mask": "未佩戴口罩",
    "smoke": "吸烟行为",
    "phone": "玩手机",
    "overflow": "溢出",
    "garbage": "垃圾",
    "garbage_bin": "垃圾桶",
    "no_chef_uniform": "未穿工作服",
    "no_chef_hat": "未戴厨师帽",
}

# 合规行为（不生成告警）
COMPLIANT_BEHAVIORS = {
    "chef_uniform": "穿工作服",
    "chef_hat": "戴厨师帽",
    "with_mask": "佩戴口罩",
}

# 告警级别映射
VIOLATION_LEVELS = {
    "cockroach": AlertLevel.CRITICAL,
    "rat": AlertLevel.CRITICAL,
    "smoke": AlertLevel.CRITICAL,
    "without_mask": AlertLevel.WARNING,
    "no_gloves": AlertLevel.WARNING,
    "no_hat": AlertLevel.WARNING,
    "no_chef_uniform": AlertLevel.WARNING,
    "no_chef_hat": AlertLevel.WARNING,
    "phone": AlertLevel.WARNING,
    "overflow": AlertLevel.INFO,
    "garbage": AlertLevel.INFO,
}


def _get_violation_name(violation_type: str) -> str:
    return VIOLATION_NAMES.get(violation_type, violation_type)


def _get_violation_level(violation_type: str) -> AlertLevel:
    return VIOLATION_LEVELS.get(violation_type, AlertLevel.INFO)


@router.get("/")
def list_alerts(
    camera_id: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取告警列表（分页）"""
    query = db.query(Alert)
    
    # 按用户企业过滤
    if current_user.role.value != "admin":
        query = query.filter(Alert.user_id == current_user.id)
    
    # 各种过滤条件
    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)
    if violation_type:
        query = query.filter(Alert.violation_type == violation_type)
    if level:
        try:
            query = query.filter(Alert.level == AlertLevel(level))
        except ValueError:
            pass  # 无效的level值，忽略过滤
    if start_time:
        query = query.filter(Alert.detected_at >= datetime.fromisoformat(start_time))
    if end_time:
        query = query.filter(Alert.detected_at <= datetime.fromisoformat(end_time))
    if acknowledged is not None:
        if acknowledged:
            query = query.filter(Alert.acknowledged_at.isnot(None))
        else:
            query = query.filter(Alert.acknowledged_at.is_(None))
    
    # 总数
    total = query.count()
    
    # 分页
    alerts = query.order_by(desc(Alert.detected_at))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    # 构建响应
    items = []
    for alert in alerts:
        item = {
            "id": alert.id,
            "alert_id": alert.alert_id if alert.alert_id else str(alert.id),
            "camera_id": alert.camera_id,
            "camera_name": alert.camera_name if alert.camera_name else alert.camera_id,
            "violation_type": alert.violation_type,
            "violation_name": VIOLATION_NAMES.get(alert.violation_type, alert.violation_type),
            "confidence": alert.confidence if alert.confidence else 0,
            "level": alert.level.value if alert.level else "warning",
            "detected_at": alert.detected_at.isoformat() if alert.detected_at else "",
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "image_url": f"/api/alerts/image/{alert.alert_id}" if alert.image_path else None,
        }
        items.append(item)
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": items
    }


@router.get("/stats", )
@cached(ttl=60, key_prefix="alert_stats")
def alert_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """告警统计数据"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    base_query = db.query(Alert)
    if current_user.role.value != "admin":
        base_query = base_query.filter(Alert.user_id == current_user.id)
    
    # 今日告警数
    today_alerts = base_query.filter(Alert.detected_at >= today_start).count()
    
    # 本周告警数
    week_alerts = base_query.filter(Alert.detected_at >= week_start).count()
    
    # 按类型统计
    type_stats = db.query(
        Alert.violation_type, func.count(Alert.id)
    ).filter(
        Alert.detected_at >= today_start
    )
    if current_user.role.value != "admin":
        type_stats = type_stats.filter(Alert.user_id == current_user.id)
    type_stats = type_stats.group_by(Alert.violation_type).all()
    
    by_type = {row[0]: row[1] for row in type_stats}
    
    # 按摄像头统计
    cam_stats = db.query(
        Alert.camera_id, Alert.camera_name, func.count(Alert.id)
    ).filter(
        Alert.detected_at >= today_start
    )
    if current_user.role.value != "admin":
        cam_stats = cam_stats.filter(Alert.user_id == current_user.id)
    cam_stats = cam_stats.group_by(Alert.camera_id, Alert.camera_name).all()
    
    by_camera = {f"{row[0]} ({row[1] or row[0]})": row[2] for row in cam_stats}
    
    # 近7天趋势
    trend = []
    for i in range(7):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        count = base_query.filter(
            Alert.detected_at >= day_start,
            Alert.detected_at < day_end
        ).count()
        
        trend.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })
    
    trend.reverse()
    
    return {
        "total_today": today_alerts,
        "total_week": week_alerts,
        "by_type": by_type,
        "by_camera": by_camera,
        "trend": trend,
    }


@router.post("/acknowledge")
def acknowledge_alerts(
    data: AlertAcknowledge,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认告警"""
    query = db.query(Alert).filter(Alert.alert_id.in_(data.alert_ids))
    
    # 非管理员只能确认自己相关的告警
    if current_user.role.value != "admin":
        query = query.filter(Alert.user_id == current_user.id)
    
    alerts = query.all()

    if not alerts:
        raise HTTPException(status_code=404, detail="告警不存在或无权限操作")

    now = datetime.utcnow()
    for alert in alerts:
        alert.acknowledged_at = now
        alert.acknowledged_by = current_user.id

    db.commit()

    return {"message": f"已确认 {len(alerts)} 条告警", "count": len(alerts)}


@router.get("/image/{alert_id}")
def get_alert_image(alert_id: str, db: Session = Depends(get_db)):
    """获取告警截图"""
    from fastapi.responses import FileResponse
    
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert or not alert.image_path:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    if not os.path.exists(alert.image_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")
    
    return FileResponse(alert.image_path, media_type="image/jpeg")