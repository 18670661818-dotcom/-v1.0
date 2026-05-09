"""摄像头管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, User, Camera, CameraStatus
from models.schemas import CameraCreate, CameraUpdate, CameraResponse
from utils.auth_utils import get_current_user, get_current_admin

router = APIRouter(prefix="/api/cameras", tags=["摄像头管理"])


@router.get("/", response_model=List[CameraResponse])
def list_cameras(
    status: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取摄像头列表（按用户所属企业过滤）"""
    query = db.query(Camera)

    # 管理员可以看到所有摄像头，普通用户只能看自己企业的
    if current_user.role.value not in ["admin"]:
        query = query.filter(Camera.company_name == current_user.company_name)

    if status:
        try:
            query = query.filter(Camera.status == CameraStatus(status))
        except ValueError:
            pass  # 无效的status值，忽略过滤

    cameras = query.all()
    
    # 添加告警数量
    from sqlalchemy import func
    from models.database import Alert
    
    results = []
    for cam in cameras:
        alert_count = db.query(func.count(Alert.id)).filter(
            Alert.camera_id == cam.camera_id
        ).scalar()
        
        cam_response = CameraResponse.from_orm(cam)
        cam_response.alerts_count = alert_count or 0
        results.append(cam_response)
    
    return results


@router.post("/", response_model=CameraResponse)
def add_camera(
    camera_data: CameraCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """添加摄像头"""
    # 检查camera_id是否重复
    existing = db.query(Camera).filter(
        Camera.camera_id == camera_data.camera_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="摄像头ID已存在")
    
    camera = Camera(
        **camera_data.dict(),
        company_name=current_user.company_name,
        user_id=current_user.id,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    
    # TODO: 通知推理引擎添加新的摄像头流
    from services.inference_service import inference_service
    if inference_service:
        inference_service.add_camera(camera.camera_id, camera.rtsp_url)
    
    return camera


@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: str,
    camera_data: CameraUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新摄像头配置"""
    camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    
    update_data = camera_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(camera, key, value)
    
    db.commit()
    db.refresh(camera)
    
    # 如果RTSP地址变了，需要重新连接
    if "rtsp_url" in update_data:
        from services.inference_service import inference_service
        if inference_service:
            inference_service.update_camera(camera_id, camera.rtsp_url)
    
    return camera


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除摄像头"""
    camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    
    db.delete(camera)
    db.commit()
    
    from services.inference_service import inference_service
    if inference_service:
        inference_service.remove_camera(camera_id)
    
    return {"message": "摄像头已删除"}


@router.get("/status/summary")
def camera_status_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """摄像头状态汇总"""
    from sqlalchemy import func
    
    query = db.query(Camera)
    if current_user.role.value != "admin":
        query = query.filter(Camera.company_name == current_user.company_name)
    
    total = query.count()
    online = query.filter(Camera.status == CameraStatus.ONLINE).count()
    offline = query.filter(Camera.status == CameraStatus.OFFLINE).count()
    
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "online_rate": f"{online/total*100:.1f}%" if total > 0 else "0%"
    }