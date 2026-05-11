"""
告警API
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from core.logger import get_logger

logger = get_logger("api.alert")
router = APIRouter(prefix="/api/alerts", tags=["告警管理"])


class AlertResponse(BaseModel):
    """告警响应模型"""
    id: int
    camera_id: str
    camera_name: Optional[str]
    violation_type: str
    confidence: float
    level: str
    status: str
    detected_at: str
    image_url: Optional[str]


class AlertStats(BaseModel):
    """告警统计模型"""
    total: int
    pending: int
    confirmed: int
    resolved: int
    false_positive: int


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    camera_id: Optional[str] = None,
    status: Optional[str] = None,
    level: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取告警列表

    - **camera_id**: 按摄像头过滤
    - **status**: 按状态过滤 (pending/confirmed/resolved/false_positive)
    - **level**: 按级别过滤 (info/warning/critical)
    - **start_date**: 开始日期
    - **end_date**: 结束日期
    """
    try:
        from models.database import SessionLocal, Alert, Camera

        db = SessionLocal()
        query = db.query(Alert)

        # 过滤条件
        if camera_id:
            query = query.filter(Alert.camera_id == camera_id)
        if status:
            query = query.filter(Alert.status == status)
        if level:
            query = query.filter(Alert.level == level)
        if start_date:
            query = query.filter(Alert.detected_at >= start_date)
        if end_date:
            query = query.filter(Alert.detected_at <= end_date)

        # 排序和分页
        alerts = query.order_by(Alert.detected_at.desc())\
                      .offset(skip)\
                      .limit(limit)\
                      .all()

        db.close()

        return [
            {
                "id": alert.id,
                "camera_id": alert.camera_id,
                "camera_name": alert.camera_name,
                "violation_type": alert.violation_type,
                "confidence": alert.confidence,
                "level": alert.level.value if hasattr(alert.level, 'value') else alert.level,
                "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
                "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
                "image_url": alert.image_url
            }
            for alert in alerts
        ]
    except Exception as e:
        logger.error(f"获取告警列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=AlertStats)
def get_alert_stats(
    camera_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """获取告警统计"""
    try:
        from models.database import SessionLocal, Alert

        db = SessionLocal()
        query = db.query(Alert)

        if camera_id:
            query = query.filter(Alert.camera_id == camera_id)
        if start_date:
            query = query.filter(Alert.detected_at >= start_date)
        if end_date:
            query = query.filter(Alert.detected_at <= end_date)

        total = query.count()
        pending = query.filter(Alert.status == "pending").count()
        confirmed = query.filter(Alert.status == "confirmed").count()
        resolved = query.filter(Alert.status == "resolved").count()
        false_positive = query.filter(Alert.status == "false_positive").count()

        db.close()

        return {
            "total": total,
            "pending": pending,
            "confirmed": confirmed,
            "resolved": resolved,
            "false_positive": false_positive
        }
    except Exception as e:
        logger.error(f"获取告警统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alert_id}")
def get_alert(alert_id: int):
    """获取单个告警详情"""
    try:
        from models.database import SessionLocal, Alert

        db = SessionLocal()
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        db.close()

        if not alert:
            raise HTTPException(status_code=404, detail="告警不存在")

        return {
            "id": alert.id,
            "camera_id": alert.camera_id,
            "camera_name": alert.camera_name,
            "violation_type": alert.violation_type,
            "confidence": alert.confidence,
            "level": alert.level.value if hasattr(alert.level, 'value') else alert.level,
            "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
            "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
            "image_url": alert.image_url,
            "notes": alert.notes
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取告警详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{alert_id}/status")
def update_alert_status(alert_id: int, status: str):
    """
    更新告警状态

    - **status**: 新状态 (confirmed/resolved/false_positive)
    """
    try:
        from models.database import SessionLocal, Alert

        valid_statuses = ["pending", "confirmed", "resolved", "false_positive"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"无效状态，可选值: {valid_statuses}"
            )

        db = SessionLocal()
        alert = db.query(Alert).filter(Alert.id == alert_id).first()

        if not alert:
            raise HTTPException(status_code=404, detail="告警不存在")

        alert.status = status
        alert.updated_at = datetime.now()
        db.commit()
        db.close()

        logger.info(f"更新告警状态: {alert_id} -> {status}")
        return {"message": "告警状态更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新告警状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{alert_id}")
def delete_alert(alert_id: int):
    """删除告警"""
    try:
        from models.database import SessionLocal, Alert

        db = SessionLocal()
        alert = db.query(Alert).filter(Alert.id == alert_id).first()

        if not alert:
            raise HTTPException(status_code=404, detail="告警不存在")

        db.delete(alert)
        db.commit()
        db.close()

        logger.info(f"删除告警: {alert_id}")
        return {"message": "告警删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除告警失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-delete")
def batch_delete_alerts(alert_ids: List[int]):
    """批量删除告警"""
    try:
        from models.database import SessionLocal, Alert

        db = SessionLocal()
        deleted_count = db.query(Alert)\
                          .filter(Alert.id.in_(alert_ids))\
                          .delete(synchronize_session=False)
        db.commit()
        db.close()

        logger.info(f"批量删除告警: {len(alert_ids)} 条")
        return {"message": f"成功删除 {deleted_count} 条告警"}
    except Exception as e:
        logger.error(f"批量删除告警失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today/count")
def get_today_alert_count():
    """获取今日告警数量"""
    try:
        from models.database import SessionLocal, Alert

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        db = SessionLocal()
        count = db.query(Alert)\
                  .filter(Alert.detected_at >= today)\
                  .filter(Alert.detected_at < tomorrow)\
                  .count()
        db.close()

        return {"count": count, "date": today.date().isoformat()}
    except Exception as e:
        logger.error(f"获取今日告警数量失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
