"""Camera management API backed by the database."""
from datetime import datetime
from typing import Optional

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.logger import get_logger
from models.database import Camera, CameraStatus, User, get_db
from services.camera_service import camera_service
from utils.auth_utils import get_current_user, get_current_admin


logger = get_logger("api.camera")
router = APIRouter(prefix="/api/cameras", tags=["cameras"])


class CameraCreate(BaseModel):
    camera_id: str
    rtsp_url: str
    name: Optional[str] = None
    location: Optional[str] = ""
    description: Optional[str] = None
    enabled: bool = True
    detection_enabled: bool = True


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    detection_enabled: Optional[bool] = None


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status or CameraStatus.OFFLINE.value)


def _camera_to_dict(camera: Camera, runtime_status: Optional[dict] = None) -> dict:
    return {
        "id": camera.id,
        "camera_id": camera.camera_id,
        "name": camera.name,
        "location": camera.location,
        "description": camera.description,
        "rtsp_url": camera.rtsp_url,
        "status": _status_value(camera.status),
        "enabled": bool(camera.is_active),
        "is_active": bool(camera.is_active),
        "detection_enabled": bool(camera.detection_enabled),
        "created_at": camera.created_at.isoformat() if camera.created_at else None,
        "updated_at": camera.updated_at.isoformat() if camera.updated_at else None,
        "last_heartbeat": camera.last_heartbeat.isoformat() if camera.last_heartbeat else None,
        "last_online_at": camera.last_online_at.isoformat() if camera.last_online_at else None,
        "last_offline_at": camera.last_offline_at.isoformat() if camera.last_offline_at else None,
        "runtime": runtime_status,
    }


def _get_active_camera_or_404(db: Session, camera_id: str) -> Camera:
    camera = (
        db.query(Camera)
        .filter(Camera.camera_id == camera_id)
        .filter(Camera.is_active == True)
        .first()
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


def _set_camera_status(db: Session, camera: Camera, status: CameraStatus):
    now = datetime.utcnow()
    camera.status = status
    camera.updated_at = now
    if status == CameraStatus.ONLINE:
        camera.last_heartbeat = now
        camera.last_online_at = now
    if status in (CameraStatus.OFFLINE, CameraStatus.ERROR):
        camera.last_offline_at = now


@router.get("")
@router.get("/")
def list_cameras(
    status: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Camera)
    if not include_inactive:
        query = query.filter(Camera.is_active == True)
    if status:
        try:
            query = query.filter(Camera.status == CameraStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid camera status")

    cameras = query.order_by(Camera.created_at.desc(), Camera.id.desc()).all()
    return [
        _camera_to_dict(camera, camera_service.get_camera_status(camera.camera_id))
        for camera in cameras
    ]


@router.get("/status")
def get_all_camera_status(current_user: User = Depends(get_current_user)):
    return camera_service.get_all_status()


@router.get("/status/summary")
def camera_status_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total = db.query(Camera).filter(Camera.is_active == True).count()
    online = (
        db.query(Camera)
        .filter(Camera.is_active == True)
        .filter(Camera.status == CameraStatus.ONLINE)
        .count()
    )
    offline = (
        db.query(Camera)
        .filter(Camera.is_active == True)
        .filter(Camera.status == CameraStatus.OFFLINE)
        .count()
    )
    error = (
        db.query(Camera)
        .filter(Camera.is_active == True)
        .filter(Camera.status == CameraStatus.ERROR)
        .count()
    )
    reconnecting = (
        db.query(Camera)
        .filter(Camera.is_active == True)
        .filter(Camera.status == CameraStatus.RECONNECTING)
        .count()
    )
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "error": error,
        "reconnecting": reconnecting,
        "online_rate": f"{online / total * 100:.1f}%" if total else "0%",
    }


@router.get("/{camera_id}")
def get_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    camera = _get_active_camera_or_404(db, camera_id)
    return _camera_to_dict(camera, camera_service.get_camera_status(camera_id))


@router.post("")
@router.post("/")
def create_camera(
    camera_data: CameraCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    existing = db.query(Camera).filter(Camera.camera_id == camera_data.camera_id).first()
    if existing and existing.is_active:
        raise HTTPException(status_code=400, detail="Camera ID already exists")

    if existing and not existing.is_active:
        camera = existing
        camera.rtsp_url = camera_data.rtsp_url
        camera.name = camera_data.name or camera_data.camera_id
        camera.location = camera_data.location or ""
        camera.description = camera_data.description
        camera.is_active = camera_data.enabled
        camera.detection_enabled = camera_data.detection_enabled
        camera.status = CameraStatus.OFFLINE
        camera.updated_at = datetime.utcnow()
    else:
        camera = Camera(
            camera_id=camera_data.camera_id,
            name=camera_data.name or camera_data.camera_id,
            rtsp_url=camera_data.rtsp_url,
            location=camera_data.location or "",
            description=camera_data.description,
            is_active=camera_data.enabled,
            detection_enabled=camera_data.detection_enabled,
            status=CameraStatus.OFFLINE,
        )
        db.add(camera)

    db.commit()
    db.refresh(camera)

    logger.info("Camera created: %s", camera.camera_id)
    return _camera_to_dict(camera, camera_service.get_camera_status(camera.camera_id))


@router.put("/{camera_id}")
def update_camera(
    camera_id: str,
    camera_data: CameraUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    camera = _get_active_camera_or_404(db, camera_id)
    update_data = camera_data.dict(exclude_unset=True)

    if "enabled" in update_data:
        camera.is_active = update_data.pop("enabled")
    for key, value in update_data.items():
        setattr(camera, key, value)
    camera.updated_at = datetime.utcnow()
    if not camera.is_active:
        _set_camera_status(db, camera, CameraStatus.OFFLINE)

    db.commit()
    db.refresh(camera)

    was_running = camera_service.get_camera_status(camera_id) is not None
    camera_service.remove_camera(camera_id)
    if camera.is_active and was_running:
        camera_service.add_camera(camera_id, camera.rtsp_url, camera.location or camera.name)

    logger.info("Camera updated: %s", camera_id)
    return _camera_to_dict(camera, camera_service.get_camera_status(camera_id))


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    camera = _get_active_camera_or_404(db, camera_id)
    camera.is_active = False
    _set_camera_status(db, camera, CameraStatus.OFFLINE)
    db.commit()

    camera_service.remove_camera(camera_id)
    logger.info("Camera soft deleted: %s", camera_id)
    return {"message": "摄像头已删除", "camera_id": camera_id, "is_active": False}


@router.post("/{camera_id}/start")
def start_camera(
    camera_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    camera = _get_active_camera_or_404(db, camera_id)
    _set_camera_status(db, camera, CameraStatus.RECONNECTING)
    db.commit()

    camera_service.remove_camera(camera_id)
    camera_service.add_camera(camera_id, camera.rtsp_url, camera.location or camera.name)
    camera_service.start_camera(camera_id)

    return _camera_to_dict(camera, camera_service.get_camera_status(camera_id))


@router.post("/{camera_id}/stop")
def stop_camera(
    camera_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    camera = _get_active_camera_or_404(db, camera_id)
    camera_service.stop_camera(camera_id)
    _set_camera_status(db, camera, CameraStatus.OFFLINE)
    db.commit()
    db.refresh(camera)
    return _camera_to_dict(camera, camera_service.get_camera_status(camera_id))


@router.post("/{camera_id}/test")
def test_camera(
    camera_id: str,
    timeout: int = Query(10, ge=1, le=60),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test RTSP connectivity only. This endpoint does not write camera data."""
    camera = _get_active_camera_or_404(db, camera_id)
    started = datetime.utcnow()
    cap = cv2.VideoCapture(camera.rtsp_url)
    try:
        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        success = bool(cap.isOpened())
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if success else None
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if success else None
        fps = float(cap.get(cv2.CAP_PROP_FPS)) if success else None
    finally:
        cap.release()

    elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    return {
        "camera_id": camera_id,
        "success": success,
        "connect_time_ms": elapsed_ms,
        "stream_info": {
            "width": width,
            "height": height,
            "fps": fps,
        } if success else None,
    }


@router.get("/{camera_id}/status")
def get_camera_status(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    camera = _get_active_camera_or_404(db, camera_id)
    runtime_status = camera_service.get_camera_status(camera_id)
    return {
        **_camera_to_dict(camera, runtime_status),
        "runtime_status": runtime_status,
    }
