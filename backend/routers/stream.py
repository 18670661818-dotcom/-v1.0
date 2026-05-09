"""视频流推送路由 - MJPEG格式"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import cv2
import time
import threading

router = APIRouter(prefix="/api/stream", tags=["视频流"])

# 存储每个摄像头的当前帧
_stream_frames = {}
_lock = threading.Lock()


def update_frame(camera_id: str, frame):
    """推理引擎调用此方法更新帧"""
    with _lock:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        _stream_frames[camera_id] = buffer.tobytes()


def generate_mjpeg(camera_id: str):
    """生成MJPEG流"""
    while True:
        with _lock:
            frame = _stream_frames.get(camera_id)
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            # 没有帧时发送空白
            time.sleep(0.1)


@router.get("/{camera_id}")
def stream_camera(camera_id: str):
    """获取摄像头的MJPEG视频流"""
    return StreamingResponse(
        generate_mjpeg(camera_id),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )