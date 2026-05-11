"""Lightweight camera manager that loads camera sources from the database."""
import logging
import threading
import time

import cv2
import numpy as np


logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, inference_engine):
        self.engine = inference_engine
        self._streams = {}
        self._running = True

    def start_all(self):
        from models.database import Camera, SessionLocal

        db = SessionLocal()
        try:
            cameras = db.query(Camera).filter(Camera.is_active == True).all()
            for camera in cameras:
                thread = threading.Thread(
                    target=self._worker,
                    args=(camera.camera_id, camera.rtsp_url, 0.1),
                    daemon=True,
                )
                thread.start()
                self._streams[camera.camera_id] = {"thread": thread}
                time.sleep(0.1)
        finally:
            db.close()
        logger.info("started %s camera streams from database", len(self._streams))

    def _worker(self, camera_id, rtsp_url, interval):
        cap = cv2.VideoCapture(rtsp_url) if rtsp_url else None
        if cap and not cap.isOpened():
            logger.warning("[%s] failed to open RTSP stream", camera_id)

        last_time = 0.0
        while self._running:
            current = time.time()
            if current - last_time < interval:
                time.sleep(0.1)
                continue

            frame = None
            if cap and cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    frame = cv2.resize(frame, (640, 640))
            if frame is None:
                frame = np.zeros((640, 640, 3), dtype=np.uint8)

            self.engine.submit_frame(camera_id, frame)
            last_time = current

        if cap:
            cap.release()

    def stop_all(self):
        self._running = False
        for info in self._streams.values():
            info["thread"].join(timeout=3)
        logger.info("camera manager stopped")
