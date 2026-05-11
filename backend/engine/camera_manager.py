"""
摄像头管理器
"""
import time
import threading
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, inference_engine):
        self.engine = inference_engine
        self._streams = {}
        self._running = True

    def start_all(self):
        # 使用模拟摄像头（从RTSP读取）
        from config import CAMERA_CONFIG
        for cam_id, config in CAMERA_CONFIG.items():
            if config.get("enabled", True):
                t = threading.Thread(
                    target=self._mock_worker,
                    args=(cam_id, config.get("rtsp_url", ""), 0.1),  # 10 FPS
                    daemon=True,
                )
                t.start()
                self._streams[cam_id] = {"thread": t, "config": config}
                time.sleep(0.1)
        logger.info(f"已启动 {len(self._streams)} 路摄像头")

    def _mock_worker(self, cam_id, rtsp_url, interval):
        logger.info(f"[{cam_id}] 连接 {rtsp_url}")
        cap = None
        frame_count = 0

        if rtsp_url:
            cap = cv2.VideoCapture(rtsp_url)
            if not cap.isOpened():
                logger.warning(f"[{cam_id}] 无法打开RTSP流，将使用模拟帧")
            else:
                logger.info(f"[{cam_id}] RTSP流已打开")

        last_time = 0
        while self._running:
            current = time.time()
            if current - last_time >= interval:
                frame = None
                if cap and cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        frame = cv2.resize(frame, (640, 640))
                        frame_count += 1
                        if frame_count % 10 == 0:
                            logger.debug(f"[{cam_id}] 已读取 {frame_count} 帧")
                    else:
                        logger.warning(f"[{cam_id}] 读取帧失败")
                else:
                    # 生成模拟帧
                    frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
                    frame_count += 1
                    if frame_count % 10 == 0:
                        logger.debug(f"[{cam_id}] 已生成 {frame_count} 个模拟帧")

                if frame is not None:
                    self.engine.submit_frame(cam_id, frame)
                last_time = current
            else:
                time.sleep(0.1)

        if cap:
            cap.release()
        logger.info(f"[{cam_id}] 工作线程结束，共处理 {frame_count} 帧")

    def stop_all(self):
        self._running = False
        for cam_id, info in self._streams.items():
            info["thread"].join(timeout=3)
        logger.info("所有摄像头已停止")