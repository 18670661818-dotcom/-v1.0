"""RTSP connectivity test API. Tests do not persist camera state."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import Camera, User, get_db
from utils.auth_utils import get_current_admin, get_current_user
from utils.rtsp_tester import RTSPTester


router = APIRouter(prefix="/api/rtsp-test", tags=["rtsp-test"])
tester = RTSPTester()


@router.post("/single")
def test_single(
    camera_id: str,
    rtsp_url: str,
    timeout: int = 10,
    current_user: User = Depends(get_current_admin),
):
    return tester.test_single_rtsp(camera_id, rtsp_url, timeout)


@router.post("/batch")
def test_batch(
    camera_ids: Optional[list] = None,
    timeout: int = 10,
    max_workers: int = 10,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Camera).filter(Camera.is_active == True)
    if camera_ids:
        query = query.filter(Camera.camera_id.in_(camera_ids))

    cameras = query.all()
    if not cameras:
        raise HTTPException(status_code=404, detail="No cameras found")

    results = tester.test_batch(
        {camera.camera_id: camera.rtsp_url for camera in cameras},
        max_workers=max_workers,
        timeout=timeout,
    )
    report_path = tester.generate_report(results)
    return {
        "total": len(results),
        "success": sum(1 for result in results if result.success),
        "failed": sum(1 for result in results if not result.success),
        "report_path": report_path,
        "results": results,
    }


@router.post("/quick-check/{camera_id}")
def quick_check(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    camera = db.query(Camera).filter(Camera.camera_id == camera_id, Camera.is_active == True).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    result = tester.test_single_rtsp(camera_id, camera.rtsp_url, timeout=5, capture_frame=False)
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
