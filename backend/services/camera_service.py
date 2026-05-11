"""Camera runtime service backed by database camera records."""
import logging
import signal
import sys
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Dict, Optional

import cv2
import numpy as np

from core.logger import camera_log

logger = logging.getLogger(__name__)


class FrameCache:
    def __init__(self, max_size: int = 30):
        self.max_size = max_size
        self._cache: Dict[str, deque] = {}
        self._latest_frame: Dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def update(self, camera_id: str, frame: np.ndarray) -> None:
        with self._lock:
            self._cache.setdefault(camera_id, deque(maxlen=self.max_size)).append(
                {"frame": frame, "timestamp": time.time()}
            )
            self._latest_frame[camera_id] = frame

    def get_latest(self, camera_id: str) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest_frame.get(camera_id)

    def get_frame_count(self, camera_id: str) -> int:
        with self._lock:
            return len(self._cache.get(camera_id, []))


class CameraWorker:
    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        location: str,
        frame_cache: FrameCache,
        frame_callback: Optional[Callable] = None,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 3.0,
    ):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.location = location
        self.frame_cache = frame_cache
        self.frame_callback = frame_callback
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self.frame_count = 0
        self.last_frame_time = 0.0
        self.fps = 0.0
        self.is_online = False
        self.is_reconnecting = False
        self.reconnect_attempts = 0
        self._last_reconnect_time = 0.0

    def _update_db_status(self, status: str) -> None:
        try:
            from models.database import Camera, CameraStatus, SessionLocal

            status_map = {
                "online": CameraStatus.ONLINE,
                "offline": CameraStatus.OFFLINE,
                "error": CameraStatus.ERROR,
                "reconnecting": CameraStatus.RECONNECTING,
            }
            db = SessionLocal()
            camera = db.query(Camera).filter(Camera.camera_id == self.camera_id).first()
            if camera:
                now = datetime.utcnow()
                camera.status = status_map[status]
                camera.updated_at = now
                if status == "online":
                    camera.last_heartbeat = now
                    camera.last_online_at = now
                if status in ("offline", "error"):
                    camera.last_offline_at = now
                db.commit()
            db.close()
        except Exception as exc:
            logger.debug("[%s] failed to update camera status: %s", self.camera_id, exc)

    def _set_status(self, status: str) -> None:
        self.is_online = status == "online"
        self.is_reconnecting = status == "reconnecting"
        self._update_db_status(status)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name=f"Camera-{self.camera_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
            self._cap = None
        self._set_status("offline")

    def _status_frame(self, text: str, error: bool = False) -> np.ndarray:
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        color = (0, 0, 180) if error else (0, 120, 0)
        cv2.rectangle(frame, (0, 0), (640, 88), color, -1)
        cv2.putText(frame, f"Camera: {self.camera_id}", (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, text, (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Location: {self.location}", (20, 604), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        return frame

    def _publish_frame(self, frame: np.ndarray) -> None:
        self.frame_cache.update(self.camera_id, frame)
        if self.frame_callback:
            self.frame_callback(self.camera_id, frame)

    def _run(self) -> None:
        logger.info("[%s] connecting RTSP: %s", self.camera_id, self.rtsp_url)
        camera_log.log_connect(self.camera_id, self.rtsp_url)
        self._cap = cv2.VideoCapture(self.rtsp_url)
        if not self._cap.isOpened():
            self._set_status("error")
            camera_log.log_error(self.camera_id, "无法打开RTSP流")
            if not self._reconnect():
                self._offline_loop()
                return

        self._set_status("online")
        camera_log.log_connect(self.camera_id, self.rtsp_url)
        self.reconnect_attempts = 0
        last_time = time.time()

        while self._running:
            current_time = time.time()
            if current_time - last_time < 0.1:
                time.sleep(0.01)
                continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._set_status("offline")
                camera_log.log_disconnect(self.camera_id, "帧读取失败")
                self._publish_frame(self._status_frame("offline - reconnecting", error=True))
                if self._reconnect():
                    last_time = time.time()
                    continue
                self._offline_loop()
                return

            if self.is_reconnecting:
                self.reconnect_attempts = 0
                self._set_status("online")
                camera_log.log_reconnect_success(self.camera_id)

            frame = cv2.resize(frame, (640, 640))
            self.frame_count += 1
            self.last_frame_time = current_time
            self.fps = 1.0 / (current_time - last_time) if current_time > last_time else 0.0
            self._publish_frame(frame)
            last_time = current_time

        if self._cap:
            self._cap.release()
            self._cap = None
        self._set_status("offline")

    def _offline_loop(self) -> None:
        last_time = 0.0
        while self._running:
            current_time = time.time()
            if current_time - last_time < 1.0:
                time.sleep(0.1)
                continue
            self._set_status("reconnecting")
            self._publish_frame(
                self._status_frame(
                    f"offline - reconnecting ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})",
                    error=True,
                )
            )
            if self._reconnect():
                self._run()
                return
            last_time = current_time

    def _reconnect(self) -> bool:
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self._set_status("error")
            camera_log.log_reconnect_failed(self.camera_id, "达到最大重连次数")
            return False

        current_time = time.time()
        wait_time = self.reconnect_delay - (current_time - self._last_reconnect_time)
        if wait_time > 0:
            time.sleep(wait_time)

        self.reconnect_attempts += 1
        self._last_reconnect_time = time.time()
        self._set_status("reconnecting")
        camera_log.log_reconnect(self.camera_id, self.reconnect_attempts, self.max_reconnect_attempts)

        if self._cap:
            self._cap.release()
        self._cap = cv2.VideoCapture(self.rtsp_url)
        if self._cap.isOpened():
            self.reconnect_attempts = 0
            self._set_status("online")
            camera_log.log_reconnect_success(self.camera_id)
            return True

        self._set_status("error")
        camera_log.log_reconnect_failed(self.camera_id, "无法打开RTSP流")
        return False


class CameraService:
    def __init__(self):
        self.frame_cache = FrameCache(max_size=30)
        self._cameras: Dict[str, CameraWorker] = {}
        self._running = False
        self._frame_callback: Optional[Callable] = None

    def set_frame_callback(self, callback: Callable) -> None:
        self._frame_callback = callback

    def add_camera(self, camera_id: str, rtsp_url: str, location: str = "") -> None:
        if camera_id in self._cameras:
            self.remove_camera(camera_id)
        worker = CameraWorker(camera_id, rtsp_url, location, self.frame_cache, self._frame_callback)
        self._cameras[camera_id] = worker
        if self._running:
            worker.start()

    def remove_camera(self, camera_id: str) -> None:
        if camera_id in self._cameras:
            self._cameras[camera_id].stop()
            del self._cameras[camera_id]

    def start_camera(self, camera_id: str) -> bool:
        if camera_id not in self._cameras:
            return False
        self._running = True
        self._cameras[camera_id].start()
        return True

    def stop_camera(self, camera_id: str) -> bool:
        if camera_id not in self._cameras:
            return False
        self._cameras[camera_id].stop()
        return True

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for worker in self._cameras.values():
            worker.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for worker in list(self._cameras.values()):
            worker.stop()

    def get_camera_status(self, camera_id: str) -> Optional[Dict]:
        worker = self._cameras.get(camera_id)
        if not worker:
            return None
        return {
            "camera_id": camera_id,
            "location": worker.location,
            "frame_count": worker.frame_count,
            "fps": round(worker.fps, 2),
            "cache_size": self.frame_cache.get_frame_count(camera_id),
            "is_online": worker.is_online,
            "is_reconnecting": worker.is_reconnecting,
            "reconnect_attempts": worker.reconnect_attempts,
        }

    def get_all_status(self) -> Dict:
        return {
            "running": self._running,
            "cameras": {camera_id: self.get_camera_status(camera_id) for camera_id in self._cameras},
            "total_cameras": len(self._cameras),
        }


camera_service = CameraService()


def load_camera_config() -> dict:
    """Load active cameras from the database only."""
    config = {}
    try:
        from models.database import Camera, SessionLocal

        db = SessionLocal()
        cameras = db.query(Camera).filter(Camera.is_active == True).all()
        for cam in cameras:
            config[cam.camera_id] = {
                "rtsp_url": cam.rtsp_url,
                "location": cam.location or cam.name,
                "enabled": cam.is_active,
            }
        db.close()
        logger.info("loaded %s active cameras from database", len(config))
    except Exception as exc:
        logger.warning("failed to load cameras from database: %s", exc)
    return config


def main():
    camera_config = load_camera_config()
    service = CameraService()

    for camera_id, config in camera_config.items():
        if config.get("enabled", True):
            service.add_camera(camera_id, config.get("rtsp_url", ""), config.get("location", ""))

    def frame_callback(camera_id: str, frame):
        try:
            from services.inference_service import get_inference_service

            inference_service = get_inference_service()
            location = service._cameras[camera_id].location if camera_id in service._cameras else ""
            inference_service.submit_frame(camera_id, frame, location)
        except Exception as exc:
            logger.debug("failed to submit frame for inference: %s", exc)

    service.set_frame_callback(frame_callback)

    def signal_handler(sig, frame):
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
