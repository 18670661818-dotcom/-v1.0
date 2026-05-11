"""Alert creation service with noise-reduction policy and lifecycle helpers."""
import asyncio
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set

import cv2
import numpy as np

from core.config import settings
from core.logger import get_logger, alert_log
from models.database import Alert, AlertLevel, AlertStatus, Camera, SessionLocal


logger = get_logger("alert_service")


COMPLIANT_BEHAVIORS = {"chef_uniform", "chef_hat", "with_mask"}


class AlertPolicy:
    COOLDOWN_SECONDS = 600
    MIN_CONSECUTIVE_FRAMES = 10
    MERGE_WINDOW_SECONDS = 900
    MAX_ALERTS_PER_HOUR = 10

    ALERT_LEVELS = {
        "fire": AlertLevel.CRITICAL,
        "smoke": AlertLevel.CRITICAL,
        "fight": AlertLevel.CRITICAL,
        "cockroach": AlertLevel.CRITICAL,
        "rat": AlertLevel.CRITICAL,
        "without_mask": AlertLevel.WARNING,
        "no_mask": AlertLevel.WARNING,
        "no_hat": AlertLevel.WARNING,
        "no_chef_hat": AlertLevel.WARNING,
        "no_uniform": AlertLevel.WARNING,
        "no_chef_uniform": AlertLevel.WARNING,
        "no_gloves": AlertLevel.WARNING,
        "phone": AlertLevel.WARNING,
        "smoking": AlertLevel.WARNING,
        "overflow": AlertLevel.INFO,
        "garbage": AlertLevel.INFO,
        "garbage_bin": AlertLevel.INFO,
    }

    ALERT_NAMES = {
        "fire": "fire",
        "smoke": "smoke",
        "fight": "fight",
        "cockroach": "cockroach",
        "rat": "rat",
        "without_mask": "without mask",
        "no_mask": "without mask",
        "no_hat": "without hat",
        "no_chef_hat": "without chef hat",
        "no_uniform": "without uniform",
        "no_chef_uniform": "without chef uniform",
        "no_gloves": "without gloves",
        "phone": "phone use",
        "smoking": "smoking",
        "overflow": "overflow",
        "garbage": "garbage",
        "garbage_bin": "garbage bin",
    }


class AlertService:
    def __init__(self):
        self.policy = AlertPolicy()
        self._cooldown_cache: Dict[str, datetime] = {}
        self._consecutive_frames: Dict[str, int] = defaultdict(int)
        self._hourly_counts: Dict[str, List[datetime]] = defaultdict(list)
        self._callbacks: List[Any] = []
        self._stats = {
            "total_alerts": 0,
            "blocked_by_cooldown": 0,
            "blocked_by_consecutive": 0,
            "blocked_by_rate_limit": 0,
            "merged_alerts": 0,
        }

    def register_callback(self, callback):
        self._callbacks.append(callback)

    def _key(self, camera_id: str, alert_type: str) -> str:
        return f"{camera_id}:{alert_type}"

    def _get_alert_level(self, alert_type: str) -> AlertLevel:
        return self.policy.ALERT_LEVELS.get(alert_type, AlertLevel.WARNING)

    def _get_alert_name(self, alert_type: str) -> str:
        return self.policy.ALERT_NAMES.get(alert_type, alert_type)

    def _get_camera_name(self, db, camera_id: str) -> str:
        camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        return camera.name if camera else camera_id

    def _prune_hourly_counts(self, camera_id: str, now: datetime):
        cutoff = now - timedelta(hours=1)
        self._hourly_counts[camera_id] = [t for t in self._hourly_counts[camera_id] if t > cutoff]

    def _check_policy(self, camera_id: str, alert_type: str, now: datetime) -> Tuple[bool, str]:
        key = self._key(camera_id, alert_type)
        self._consecutive_frames[key] += 1
        if self._consecutive_frames[key] < self.policy.MIN_CONSECUTIVE_FRAMES:
            self._stats["blocked_by_consecutive"] += 1
            return False, "consecutive_frames"

        last_alert = self._cooldown_cache.get(key)
        if last_alert and (now - last_alert).total_seconds() < self.policy.COOLDOWN_SECONDS:
            self._stats["blocked_by_cooldown"] += 1
            return False, "cooldown"

        self._prune_hourly_counts(camera_id, now)
        if len(self._hourly_counts[camera_id]) >= self.policy.MAX_ALERTS_PER_HOUR:
            self._stats["blocked_by_rate_limit"] += 1
            return False, "hourly_rate_limit"

        return True, "ok"

    def _reset_missing_detection_counters(self, camera_id: str, seen_types: Set[str]):
        prefix = f"{camera_id}:"
        for key in list(self._consecutive_frames.keys()):
            if key.startswith(prefix):
                alert_type = key.split(":", 1)[1]
                if alert_type not in seen_types:
                    self._consecutive_frames[key] = 0

    def _find_merge_target(self, db, camera_id: str, alert_type: str, now: datetime) -> Optional[Alert]:
        cutoff = now - timedelta(seconds=self.policy.MERGE_WINDOW_SECONDS)
        return (
            db.query(Alert)
            .filter(Alert.camera_id == camera_id)
            .filter(Alert.alert_type == alert_type)
            .filter(Alert.created_at >= cutoff)
            .order_by(Alert.created_at.desc())
            .first()
        )

    def _save_image(self, camera_id: str, alert_type: str, frame: np.ndarray) -> Optional[str]:
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            dir_path = os.path.join(settings.ALERT_IMAGE_DIR, date_str)
            os.makedirs(dir_path, exist_ok=True)
            filename = f"{camera_id}_{alert_type}_{datetime.now().strftime('%H%M%S')}.jpg"
            filepath = os.path.join(dir_path, filename)
            cv2.imwrite(filepath, frame)
            return filepath
        except Exception as exc:
            logger.error("Failed to save alert image: %s", exc)
            return None

    def process_detections(self, camera_id: str, location: str, detections: list, frame: Optional[np.ndarray] = None):
        """Create alerts from a frame's detections after applying the alert policy."""
        seen_types = {
            det.get("class_name")
            for det in detections
            if det.get("class_name") and det.get("class_name") not in COMPLIANT_BEHAVIORS
        }
        self._reset_missing_detection_counters(camera_id, seen_types)

        for alert_type in seen_types:
            candidates = [det for det in detections if det.get("class_name") == alert_type]
            confidence = max(float(det.get("confidence", 0.0)) for det in candidates)
            alert = self._create_alert_sync(
                camera_id=camera_id,
                alert_type=alert_type,
                confidence=confidence,
                frame=frame,
                detections=candidates,
            )
            if alert:
                logger.warning(
                    "ALERT | camera=%s | type=%s | confidence=%.2f | id=%s",
                    camera_id,
                    alert_type,
                    confidence,
                    alert.get("id"),
                )

    async def create_alert(
        self,
        camera_id: str,
        alert_type: str,
        confidence: float,
        frame: Optional[np.ndarray] = None,
        detections: Optional[List[Dict]] = None,
        video_clip_path: Optional[str] = None,
    ) -> Optional[Dict]:
        return self._create_alert_sync(camera_id, alert_type, confidence, frame, detections, video_clip_path)

    def _create_alert_sync(
        self,
        camera_id: str,
        alert_type: str,
        confidence: float,
        frame: Optional[np.ndarray] = None,
        detections: Optional[List[Dict]] = None,
        video_clip_path: Optional[str] = None,
    ) -> Optional[Dict]:
        now = datetime.now()
        should_alert, reason = self._check_policy(camera_id, alert_type, now)
        if not should_alert:
            logger.debug("Alert suppressed: camera=%s type=%s reason=%s", camera_id, alert_type, reason)
            return None

        db = SessionLocal()
        try:
            existing = self._find_merge_target(db, camera_id, alert_type, now)
            if existing:
                existing.confidence = max(existing.confidence or 0.0, confidence)
                existing.created_at = now
                existing.detected_at = now
                if video_clip_path:
                    existing.video_clip_path = video_clip_path
                if frame is not None:
                    existing.image_path = self._save_image(camera_id, alert_type, frame)
                db.commit()
                db.refresh(existing)
                self._stats["merged_alerts"] += 1
                self._cooldown_cache[self._key(camera_id, alert_type)] = now
                self._hourly_counts[camera_id].append(now)
                self._consecutive_frames[self._key(camera_id, alert_type)] = 0
                return self._alert_to_dict(existing)

            alert = Alert(
                alert_id=str(uuid.uuid4()),
                camera_id=camera_id,
                camera_name=self._get_camera_name(db, camera_id),
                alert_type=alert_type,
                violation_type=alert_type,
                violation_name=self._get_alert_name(alert_type),
                confidence=confidence,
                level=self._get_alert_level(alert_type),
                status=AlertStatus.PENDING,
                image_path=self._save_image(camera_id, alert_type, frame) if frame is not None else None,
                video_clip_path=video_clip_path,
                detected_at=now,
                created_at=now,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            self._stats["total_alerts"] += 1
            self._cooldown_cache[self._key(camera_id, alert_type)] = now
            self._hourly_counts[camera_id].append(now)
            self._consecutive_frames[self._key(camera_id, alert_type)] = 0

            alert_data = self._alert_to_dict(alert)

            # 记录告警生成日志
            alert_log.log_alert(camera_id, alert_type, confidence, alert.alert_id)

        except Exception as exc:
            db.rollback()
            logger.error("Failed to create alert: %s", exc)
            return None
        finally:
            db.close()

        self._dispatch_callbacks(alert_data)
        return alert_data

    def _dispatch_callbacks(self, alert_data: Dict):
        for callback in self._callbacks:
            try:
                result = callback(alert_data)
                if asyncio.iscoroutine(result):
                    asyncio.run(result)
            except RuntimeError:
                logger.debug("Skipped async alert callback because an event loop is already running")
            except Exception as exc:
                logger.error("Alert callback failed: %s", exc)

    def confirm_alert(self, alert_id: int, handled_by: str, remark: Optional[str] = None) -> bool:
        result = self._update_lifecycle(alert_id, AlertStatus.CONFIRMED, handled_by, remark)
        if result:
            alert_log.log_confirm(alert_id, handled_by)
        return result

    def resolve_alert(self, alert_id: int, handled_by: str, remark: Optional[str] = None) -> bool:
        result = self._update_lifecycle(alert_id, AlertStatus.RESOLVED, handled_by, remark)
        if result:
            alert_log.log_resolve(alert_id, handled_by)
        return result

    def mark_false_positive(self, alert_id: int, handled_by: str, remark: Optional[str] = None) -> bool:
        result = self._update_lifecycle(alert_id, AlertStatus.FALSE_POSITIVE, handled_by, remark)
        if result:
            alert_log.log_false_positive(alert_id, handled_by)
        return result

    def _update_lifecycle(
        self,
        alert_id: int,
        status: AlertStatus,
        handled_by: Optional[str],
        remark: Optional[str],
    ) -> bool:
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return False

            now = datetime.now()
            alert.status = status
            alert.handled_by = handled_by
            if remark is not None:
                alert.remark = remark
            if status == AlertStatus.CONFIRMED:
                alert.confirmed_at = now
                alert.acknowledged_at = now
            if status in (AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE):
                alert.resolved_at = now
            if status == AlertStatus.FALSE_POSITIVE:
                alert.is_false_positive = True
            db.commit()
            return True
        finally:
            db.close()

    def get_alert(self, alert_id: int) -> Optional[Dict]:
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            return self._alert_to_dict(alert) if alert else None
        finally:
            db.close()

    def get_alerts(
        self,
        camera_id: Optional[str] = None,
        status: Optional[str] = None,
        alert_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict]:
        db = SessionLocal()
        try:
            query = db.query(Alert)
            if camera_id:
                query = query.filter(Alert.camera_id == camera_id)
            if status:
                query = query.filter(Alert.status == AlertStatus(status))
            if alert_type:
                query = query.filter(Alert.alert_type == alert_type)
            alerts = query.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
            return [self._alert_to_dict(alert) for alert in alerts]
        finally:
            db.close()

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        return self.get_alerts(limit=limit)

    def get_statistics(self) -> Dict:
        db = SessionLocal()
        try:
            return {
                "total": db.query(Alert).count(),
                "pending": db.query(Alert).filter(Alert.status == AlertStatus.PENDING).count(),
                "confirmed": db.query(Alert).filter(Alert.status == AlertStatus.CONFIRMED).count(),
                "resolved": db.query(Alert).filter(Alert.status == AlertStatus.RESOLVED).count(),
                "false_positive": db.query(Alert).filter(Alert.status == AlertStatus.FALSE_POSITIVE).count(),
                "service_stats": self._stats,
            }
        finally:
            db.close()

    def get_today_count(self) -> int:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        db = SessionLocal()
        try:
            return db.query(Alert).filter(Alert.created_at >= today, Alert.created_at < tomorrow).count()
        finally:
            db.close()

    def _alert_to_dict(self, alert: Alert) -> Dict:
        return {
            "id": alert.id,
            "alert_id": alert.alert_id,
            "camera_id": alert.camera_id,
            "camera_name": alert.camera_name,
            "alert_type": alert.alert_type,
            "violation_type": alert.violation_type,
            "violation_name": alert.violation_name,
            "confidence": alert.confidence,
            "level": alert.level.value if hasattr(alert.level, "value") else alert.level,
            "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
            "image_path": alert.image_path,
            "video_clip_path": alert.video_clip_path,
            "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "confirmed_at": alert.confirmed_at.isoformat() if alert.confirmed_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "handled_by": alert.handled_by,
            "remark": alert.remark,
            "is_false_positive": bool(alert.is_false_positive),
        }


_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
