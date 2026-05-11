"""Alert lifecycle API."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.logger import get_logger
from models.database import Alert, AlertLevel, AlertStatus, Camera, User, get_db, init_db
from utils.auth_utils import get_current_user


logger = get_logger("api.alert")
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertActionRequest(BaseModel):
    handled_by: Optional[str] = None
    remark: Optional[str] = None


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _alert_to_dict(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "alert_id": alert.alert_id,
        "camera_id": alert.camera_id,
        "camera_name": alert.camera_name,
        "alert_type": alert.alert_type or alert.violation_type,
        "violation_type": alert.violation_type or alert.alert_type,
        "violation_name": alert.violation_name,
        "confidence": alert.confidence or 0.0,
        "level": _enum_value(alert.severity) or AlertLevel.WARNING.value,
        "status": _enum_value(alert.status) or AlertStatus.PENDING.value,
        "image_path": alert.image_path,
        "video_clip_path": alert.video_clip_path,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
        "confirmed_at": alert.confirmed_at.isoformat() if alert.confirmed_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "handled_by": alert.handled_by,
        "remark": alert.remark,
        "is_false_positive": bool(alert.is_false_positive),
        "image_url": f"/api/alerts/image/{alert.alert_id}" if alert.image_path and alert.alert_id else None,
    }


def _get_alert_or_404(db: Session, alert_id: int) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _serialize_status(status: Optional[str]):
    if not status:
        return None
    try:
        return AlertStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert status")


@router.get("")
@router.get("/")
def list_alerts(
    camera_id: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    level: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List alerts with lifecycle fields."""
    query = db.query(Alert)

    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)
    if status:
        query = query.filter(Alert.status == _serialize_status(status))
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if level:
        try:
            query = query.filter(Alert.severity == AlertLevel(level))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid alert level")
    if start_date:
        query = query.filter(Alert.created_at >= start_date)
    if end_date:
        query = query.filter(Alert.created_at <= end_date)

    if page is not None or page_size is not None:
        effective_page = page or 1
        effective_size = page_size or limit
        skip = (effective_page - 1) * effective_size
        limit = effective_size
    else:
        effective_page = (skip // limit) + 1
        effective_size = limit

    total = query.count()
    alerts = (
        query.order_by(Alert.created_at.desc(), Alert.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": effective_page,
        "page_size": effective_size,
        "total_pages": (total + effective_size - 1) // effective_size,
        "items": [_alert_to_dict(alert) for alert in alerts],
    }


@router.get("/stats")
def get_alert_stats(
    camera_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Alert)
    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)
    if start_date:
        query = query.filter(Alert.created_at >= start_date)
    if end_date:
        query = query.filter(Alert.created_at <= end_date)

    by_status = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1]
        for row in query.with_entities(Alert.status, func.count(Alert.id)).group_by(Alert.status).all()
    }
    by_type = {
        row[0]: row[1]
        for row in query.with_entities(Alert.alert_type, func.count(Alert.id)).group_by(Alert.alert_type).all()
    }

    return {
        "total": query.count(),
        "pending": by_status.get(AlertStatus.PENDING.value, 0),
        "confirmed": by_status.get(AlertStatus.CONFIRMED.value, 0),
        "resolved": by_status.get(AlertStatus.RESOLVED.value, 0),
        "false_positive": by_status.get(AlertStatus.FALSE_POSITIVE.value, 0),
        "by_status": by_status,
        "by_type": by_type,
    }


@router.get("/today/count")
def get_today_alert_count(db: Session = Depends(get_db)):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    count = db.query(Alert).filter(Alert.created_at >= today, Alert.created_at < tomorrow).count()
    return {"count": count, "date": today.date().isoformat()}


@router.get("/image/{alert_id}")
def get_alert_image(alert_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    import os

    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert or not alert.image_path or not os.path.exists(alert.image_path):
        raise HTTPException(status_code=404, detail="Alert image not found")
    return FileResponse(alert.image_path, media_type="image/jpeg")


@router.get("/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    return _alert_to_dict(_get_alert_or_404(db, alert_id))


@router.post("/{alert_id}/confirm")
def confirm_alert(
    alert_id: int,
    data: AlertActionRequest = AlertActionRequest(),
    db: Session = Depends(get_db),
):
    alert = _get_alert_or_404(db, alert_id)
    now = datetime.now()
    alert.status = AlertStatus.CONFIRMED
    alert.confirmed_at = now
    alert.acknowledged_at = now
    alert.handled_by = data.handled_by
    if data.remark is not None:
        alert.remark = data.remark
    db.commit()
    db.refresh(alert)
    logger.info("Alert confirmed: %s", alert_id)
    return _alert_to_dict(alert)


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    data: AlertActionRequest = AlertActionRequest(),
    db: Session = Depends(get_db),
):
    alert = _get_alert_or_404(db, alert_id)
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now()
    alert.handled_by = data.handled_by
    if data.remark is not None:
        alert.remark = data.remark
    db.commit()
    db.refresh(alert)
    logger.info("Alert resolved: %s", alert_id)
    return _alert_to_dict(alert)


@router.post("/{alert_id}/false-positive")
def mark_false_positive(
    alert_id: int,
    data: AlertActionRequest = AlertActionRequest(),
    db: Session = Depends(get_db),
):
    alert = _get_alert_or_404(db, alert_id)
    alert.status = AlertStatus.FALSE_POSITIVE
    alert.is_false_positive = True
    alert.resolved_at = datetime.now()
    alert.handled_by = data.handled_by
    if data.remark is not None:
        alert.remark = data.remark
    db.commit()
    db.refresh(alert)
    logger.info("Alert marked false positive: %s", alert_id)
    return _alert_to_dict(alert)


@router.put("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    status: str,
    data: AlertActionRequest = AlertActionRequest(),
    db: Session = Depends(get_db),
):
    if status == AlertStatus.CONFIRMED.value:
        return confirm_alert(alert_id, data, db)
    if status == AlertStatus.RESOLVED.value:
        return resolve_alert(alert_id, data, db)
    if status == AlertStatus.FALSE_POSITIVE.value:
        return mark_false_positive(alert_id, data, db)
    if status != AlertStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Invalid alert status")

    alert = _get_alert_or_404(db, alert_id)
    alert.status = AlertStatus.PENDING
    db.commit()
    db.refresh(alert)
    return _alert_to_dict(alert)


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = _get_alert_or_404(db, alert_id)
    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted"}


@router.post("/batch-delete")
def batch_delete_alerts(alert_ids: List[int], db: Session = Depends(get_db)):
    deleted_count = db.query(Alert).filter(Alert.id.in_(alert_ids)).delete(synchronize_session=False)
    db.commit()
    return {"message": "Alerts deleted", "count": deleted_count}


@router.on_event("startup")
def migrate_alert_schema_on_startup():
    init_db()
