"""视频流推送路由 - MJPEG格式"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import cv2
import time
import threading
import logging
from collections import deque
from typing import Dict, Deque

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["视频流"])

# 帧缓冲配置
BUFFER_SECONDS = 5  # 缓冲5秒的帧
TARGET_FPS = 15  # 目标帧率

# 存储每个摄像头的帧缓冲队列
_frame_buffers: Dict[str, Deque] = {}
_buffer_lock = threading.Lock()


def update_frame(camera_id: str, frame):
    """推理引擎调用此方法更新帧"""
    try:
        # 提高JPEG质量以获得更清晰的画面
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_data = buffer.tobytes()
        timestamp = time.time()

        with _buffer_lock:
            if camera_id not in _frame_buffers:
                # 初始化缓冲队列，容量为 BUFFER_SECONDS * TARGET_FPS
                _frame_buffers[camera_id] = deque(maxlen=BUFFER_SECONDS * TARGET_FPS)
            _frame_buffers[camera_id].append((timestamp, frame_data))

        logger.debug(f"更新摄像头 {camera_id} 的帧，大小: {len(frame_data)} bytes")
    except Exception as e:
        logger.error(f"更新帧失败: {e}")


def generate_mjpeg(camera_id: str):
    """生成MJPEG流 - 使用帧缓冲机制实现流畅播放"""
    logger.info(f"开始生成摄像头 {camera_id} 的MJPEG流")
    frame_count = 0
    last_frame_time = 0
    frame_interval = 1.0 / TARGET_FPS  # 帧间隔

    while True:
        current_time = time.time()

        # 控制发送帧率
        if current_time - last_frame_time >= frame_interval:
            frame_to_send = None

            with _buffer_lock:
                buffer = _frame_buffers.get(camera_id)
                if buffer and len(buffer) > 0:
                    # 直接使用最新的帧，避免延迟导致的问题
                    frame_to_send = buffer[-1][1]

            if frame_to_send is not None:
                frame_count += 1
                if frame_count % 30 == 0:  # 每30帧记录一次
                    logger.debug(f"摄像头 {camera_id} 已发送 {frame_count} 帧")
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
                last_frame_time = current_time
            else:
                # 没有帧时等待
                if frame_count == 0:
                    logger.warning(f"摄像头 {camera_id} 暂无可用帧")
                time.sleep(0.1)  # 等待帧到达
        else:
            # 等待直到下一帧时间
            time.sleep(0.01)


@router.get("/{camera_id}")
def stream_camera(camera_id: str):
    """获取摄像头的MJPEG视频流"""
    logger.info(f"请求摄像头 {camera_id} 的视频流")
    return StreamingResponse(
        generate_mjpeg(camera_id),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )