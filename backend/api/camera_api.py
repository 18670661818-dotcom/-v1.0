"""
摄像头API
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel

from services.camera_service import camera_service
from core.logger import get_logger

logger = get_logger("api.camera")
router = APIRouter(prefix="/api/cameras", tags=["摄像头管理"])


class CameraCreate(BaseModel):
    """创建摄像头请求模型"""
    camera_id: str
    rtsp_url: str
    location: Optional[str] = ""
    enabled: bool = True


class CameraUpdate(BaseModel):
    """更新摄像头请求模型"""
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None


class CameraStatus(BaseModel):
    """摄像头状态响应模型"""
    camera_id: str
    location: str
    frame_count: int
    fps: float
    cache_size: int
    is_online: bool
    is_reconnecting: bool
    reconnect_attempts: int


@router.get("", response_model=List[dict])
def list_cameras():
    """获取所有摄像头列表"""
    try:
        from models.database import SessionLocal, Camera
        db = SessionLocal()
        cameras = db.query(Camera).all()
        db.close()
        return [
            {
                "id": cam.id,
                "camera_id": cam.camera_id,
                "name": cam.name,
                "location": cam.location,
                "rtsp_url": cam.rtsp_url,
                "enabled": cam.enabled,
                "created_at": cam.created_at.isoformat() if cam.created_at else None
            }
            for cam in cameras
        ]
    except Exception as e:
        logger.error(f"获取摄像头列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_all_camera_status():
    """获取所有摄像头实时状态"""
    return camera_service.get_all_status()


@router.get("/{camera_id}")
def get_camera(camera_id: str):
    """获取单个摄像头信息"""
    try:
        from models.database import SessionLocal, Camera
        db = SessionLocal()
        camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        db.close()

        if not camera:
            raise HTTPException(status_code=404, detail="摄像头不存在")

        return {
            "id": camera.id,
            "camera_id": camera.camera_id,
            "name": camera.name,
            "location": camera.location,
            "rtsp_url": camera.rtsp_url,
            "enabled": camera.enabled,
            "created_at": camera.created_at.isoformat() if camera.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取摄像头失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{camera_id}/status")
def get_camera_status(camera_id: str):
    """获取摄像头实时状态"""
    status = camera_service.get_camera_status(camera_id)
    if not status:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return status


@router.post("", status_code=201)
def create_camera(camera: CameraCreate):
    """创建新摄像头"""
    try:
        from models.database import SessionLocal, Camera

        db = SessionLocal()

        # 检查是否已存在
        existing = db.query(Camera).filter(Camera.camera_id == camera.camera_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="摄像头ID已存在")

        # 创建新摄像头
        new_camera = Camera(
            camera_id=camera.camera_id,
            name=f"Camera {camera.camera_id}",
            location=camera.location,
            rtsp_url=camera.rtsp_url,
            enabled=camera.enabled
        )
        db.add(new_camera)
        db.commit()
        db.refresh(new_camera)

        # 如果启用，添加到摄像头服务
        if camera.enabled:
            camera_service.add_camera(
                camera_id=camera.camera_id,
                rtsp_url=camera.rtsp_url,
                location=camera.location
            )

        db.close()

        logger.info(f"创建摄像头: {camera.camera_id}")
        return {
            "id": new_camera.id,
            "camera_id": new_camera.camera_id,
            "message": "摄像头创建成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建摄像头失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{camera_id}")
def update_camera(camera_id: str, camera_update: CameraUpdate):
    """更新摄像头配置"""
    try:
        from models.database import SessionLocal, Camera

        db = SessionLocal()
        camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()

        if not camera:
            raise HTTPException(status_code=404, detail="摄像头不存在")

        # 更新字段
        if camera_update.rtsp_url is not None:
            camera.rtsp_url = camera_update.rtsp_url
        if camera_update.location is not None:
            camera.location = camera_update.location
        if camera_update.enabled is not None:
            camera.enabled = camera_update.enabled

        db.commit()
        db.close()

        # 重新加载摄像头
        if camera.enabled:
            camera_service.remove_camera(camera_id)
            camera_service.add_camera(
                camera_id=camera_id,
                rtsp_url=camera.rtsp_url,
                location=camera.location
            )
        else:
            camera_service.remove_camera(camera_id)

        logger.info(f"更新摄像头: {camera_id}")
        return {"message": "摄像头更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新摄像头失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{camera_id}")
def delete_camera(camera_id: str):
    """删除摄像头"""
    try:
        from models.database import SessionLocal, Camera

        db = SessionLocal()
        camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()

        if not camera:
            raise HTTPException(status_code=404, detail="摄像头不存在")

        db.delete(camera)
        db.commit()
        db.close()

        # 从摄像头服务中移除
        camera_service.remove_camera(camera_id)

        logger.info(f"删除摄像头: {camera_id}")
        return {"message": "摄像头删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除摄像头失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{camera_id}/restart")
def restart_camera(camera_id: str):
    """重启摄像头"""
    try:
        status = camera_service.get_camera_status(camera_id)
        if not status:
            raise HTTPException(status_code=404, detail="摄像头不存在")

        # 获取摄像头配置
        from models.database import SessionLocal, Camera
        db = SessionLocal()
        camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        db.close()

        if not camera:
            raise HTTPException(status_code=404, detail="摄像头配置不存在")

        # 重启摄像头
        camera_service.remove_camera(camera_id)
        camera_service.add_camera(
            camera_id=camera_id,
            rtsp_url=camera.rtsp_url,
            location=camera.location or ""
        )

        logger.info(f"重启摄像头: {camera_id}")
        return {"message": "摄像头重启成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重启摄像头失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
