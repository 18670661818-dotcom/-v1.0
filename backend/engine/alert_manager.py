"""Standalone alert manager used by legacy camera_service.py."""
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import cv2
import numpy as np


logger = logging.getLogger(__name__)

COMPLIANT_BEHAVIORS = {"chef_uniform", "chef_hat", "with_mask"}


class AlertManager:
    COOLDOWN_SECONDS = 600
    MIN_CONSECUTIVE_FRAMES = 10
    MERGE_WINDOW_SECONDS = 900
    MAX_ALERTS_PER_HOUR = 10

    def __init__(self):
        self._last_alert: Dict[str, datetime] = {}
        self._consecutive_frames: Dict[str, int] = defaultdict(int)
        self._hourly_counts: Dict[str, List[datetime]] = defaultdict(list)

    def _key(self, camera_id: str, alert_type: str) -> str:
        return f"{camera_id}:{alert_type}"

    def _prune_hourly_counts(self, camera_id: str, now: datetime):
        cutoff = now - timedelta(hours=1)
        self._hourly_counts[camera_id] = [t for t in self._hourly_counts[camera_id] if t > cutoff]

    def _should_alert(self, camera_id: str, alert_type: str, now: datetime) -> bool:
        key = self._key(camera_id, alert_type)
        self._consecutive_frames[key] += 1
        if self._consecutive_frames[key] < self.MIN_CONSECUTIVE_FRAMES:
            return False

        last_alert = self._last_alert.get(key)
        if last_alert and (now - last_alert).total_seconds() < self.COOLDOWN_SECONDS:
            return False

        self._prune_hourly_counts(camera_id, now)
        return len(self._hourly_counts[camera_id]) < self.MAX_ALERTS_PER_HOUR

    def _reset_missing_detection_counters(self, camera_id: str, seen_types: set[str]):
        prefix = f"{camera_id}:"
        for key in list(self._consecutive_frames.keys()):
            if key.startswith(prefix):
                alert_type = key.split(":", 1)[1]
                if alert_type not in seen_types:
                    self._consecutive_frames[key] = 0

    def _find_merge_target(self, db, camera_id: str, alert_type: str, now: datetime):
        from models.database import Alert

        cutoff = now - timedelta(seconds=self.MERGE_WINDOW_SECONDS)
        return (
            db.query(Alert)
            .filter(Alert.camera_id == camera_id)
            .filter(Alert.alert_type == alert_type)
            .filter(Alert.created_at >= cutoff)
            .order_by(Alert.created_at.desc())
            .first()
        )

    def _save_image(self, camera_id: str, alert_type: str, frame: Optional[np.ndarray]) -> Optional[str]:
        if frame is None:
            return None
        try:
            from core.config import settings
            import os

            date_str = datetime.now().strftime("%Y-%m-%d")
            dir_path = os.path.join(settings.ALERT_IMAGE_DIR, date_str)
            os.makedirs(dir_path, exist_ok=True)
            path = os.path.join(dir_path, f"{camera_id}_{alert_type}_{datetime.now().strftime('%H%M%S')}.jpg")
            cv2.imwrite(path, frame)
            return path
        except Exception as exc:
            logger.error("Failed to save alert image: %s", exc)
            return None

    def process_detections(self, camera_id: str, location: str, detections: list, frame: Optional[np.ndarray] = None):
        now = datetime.now()
        seen_types = {
            det.get("class_name")
            for det in detections
            if det.get("class_name") and det.get("class_name") not in COMPLIANT_BEHAVIORS
        }
        self._reset_missing_detection_counters(camera_id, seen_types)

        for alert_type in seen_types:
            if not self._should_alert(camera_id, alert_type, now):
                continue

            candidates = [det for det in detections if det.get("class_name") == alert_type]
            confidence = max(float(det.get("confidence", 0.0)) for det in candidates)

            try:
                from models.database import Alert, AlertLevel, AlertStatus, Camera, SessionLocal

                db = SessionLocal()
                camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
                existing = self._find_merge_target(db, camera_id, alert_type, now)
                if existing:
                    existing.confidence = max(existing.confidence or 0.0, confidence)
                    existing.created_at = now
                    existing.detected_at = now
                    db.commit()
                    alert_id = existing.id
                else:
                    alert = Alert(
                        alert_id=str(uuid.uuid4()),
                        camera_id=camera_id,
                        camera_name=camera.name if camera else camera_id,
                        alert_type=alert_type,
                        violation_type=alert_type,
                        violation_name=alert_type,
                        confidence=confidence,
                        level=AlertLevel.WARNING,
                        status=AlertStatus.PENDING,
                        image_path=self._save_image(camera_id, alert_type, frame),
                        detected_at=now,
                        created_at=now,
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    alert_id = alert.id

                db.close()
                key = self._key(camera_id, alert_type)
                self._last_alert[key] = now
                self._hourly_counts[camera_id].append(now)
                self._consecutive_frames[key] = 0
                logger.warning("ALERT | %s | %s | conf=%.2f | id=%s", camera_id, alert_type, confidence, alert_id)
            except Exception as exc:
                logger.error("Failed to save alert: %s", exc)
