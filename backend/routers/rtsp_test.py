"""RTSP测试API"""
import json
import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from models.database import get_db, User, Camera, CameraStatus
from utils.rtsp_tester import RTSPTester
from utils.auth_utils import get_current_user, get_current_admin

router = APIRouter(prefix="/api/rtsp-test", tags=["RTSP测试"])

tester = RTSPTester()


@router.post("/single")
def test_single(
    camera_id: str,
    rtsp_url: str,
    timeout: int = 10,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """测试单个RTSP流"""
    result = tester.test_single_rtsp(camera_id, rtsp_url, timeout)
    
    # 更新数据库中的摄像头状态
    camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if camera:
        from datetime import datetime
        camera.status = CameraStatus.ONLINE if result.success else CameraStatus.OFFLINE
        if result.success:
            camera.last_heartbeat = datetime.utcnow()
        db.commit()
    
    return result


@router.post("/batch")
def test_batch(
    camera_ids: Optional[list] = None,
    timeout: int = 10,
    max_workers: int = 10,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """批量测试数据库中已配置的摄像头"""
    # 获取摄像头列表
    query = db.query(Camera)
    if camera_ids:
        query = query.filter(Camera.camera_id.in_(camera_ids))
    
    cameras = query.all()
    
    if not cameras:
        raise HTTPException(status_code=404, detail="没有找到摄像头")
    
    # 构建测试配置
    config = {cam.camera_id: cam.rtsp_url for cam in cameras}
    
    # 执行测试
    results = tester.test_batch(
        config,
        max_workers=max_workers,
        timeout=timeout
    )
    
    # 生成报告
    report_path = tester.generate_report(results)
    
    # 更新摄像头状态
    for result in results:
        cam = db.query(Camera).filter(Camera.camera_id == result.camera_id).first()
        if cam:
            from models.database import CameraStatus
            cam.status = CameraStatus.ONLINE if result.success else CameraStatus.OFFLINE
            if result.success:
                cam.last_heartbeat = result.test_time
    
    db.commit()
    
    return {
        "total": len(results),
        "success": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "report_path": report_path,
        "results": results
    }


@router.post("/quick-check/{camera_id}")
def quick_check(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """快速检查单个摄像头是否在线"""
    camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    
    result = tester.test_single_rtsp(
        camera_id, 
        camera.rtsp_url, 
        timeout=5,
        capture_frame=False  # 不抓帧，更快
    )
    
    # 更新状态
    from models.database import CameraStatus
    camera.status = CameraStatus.ONLINE if result.success else CameraStatus.OFFLINE
    db.commit()
    
    return {
        "camera_id": camera_id,
        "online": result.success,
        "stream_info": {
            "resolution": f"{result.width}x{result.height}" if result.success else None,
            "fps": result.fps,
            "codec": result.codec,
        } if result.success else None,
        "connect_time_ms": result.connect_time_ms,
    }