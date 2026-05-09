"""
告警管理器 - 同时写入数据库
"""
import time
import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertManager:
    def __init__(self):
        self._last_alert = defaultdict(dict)
        self._detection_window = defaultdict(lambda: defaultdict(list))
        self._window_seconds = 30
        self._alert_history = []
        self._cooldown = 30

    def process_detections(self, camera_id: str, location: str, detections: list):
        current_time = time.time()

        for det in detections:
            class_name = det["class_name"]

            self._detection_window[camera_id][class_name].append(current_time)
            self._detection_window[camera_id][class_name] = [
                t for t in self._detection_window[camera_id][class_name]
                if current_time - t <= self._window_seconds
            ]

            last_time = self._last_alert[camera_id].get(class_name, 0)
            if current_time - last_time < self._cooldown:
                continue

            alert = {
                "camera_id": camera_id,
                "violation_type": class_name,
                "confidence": det["confidence"],
                "timestamp": current_time,
            }
            self._alert_history.append(alert)
            self._last_alert[camera_id][class_name] = current_time

            logger.warning(f"ALERT | {camera_id} | {class_name} | conf={det['confidence']:.2f}")

            # 写入数据库
            try:
                from models.database import SessionLocal, Alert, Camera, AlertLevel
                db = SessionLocal()
                camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
                db_alert = Alert(
                    camera_id=camera_id,
                    camera_name=camera.name if camera else camera_id,
                    violation_type=class_name,
                    confidence=det["confidence"],
                    level=AlertLevel.WARNING,
                    detected_at=datetime.now(),
                )
                db.add(db_alert)
                db.commit()
                db.close()
            except Exception as e:
                logger.error(f"写入数据库失败: {e}")