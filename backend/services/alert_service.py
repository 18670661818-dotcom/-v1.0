"""
告警服务
处理告警生成、冷却、存储和推送
"""
import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import cv2
import numpy as np

from core.config import settings, ALERT_COOLDOWN_RULES, ALERT_MIN_FRAMES, COMPLIANT_BEHAVIORS
from core.logger import alert_logger, AlertLogger


class AlertService:
    """告警服务类"""

    def __init__(self):
        self.alert_cooldowns: Dict[str, datetime] = {}  # camera_id:type -> 最后告警时间
        self.recent_detections: Dict[str, List[datetime]] = defaultdict(list)  # 检测计数
        self.alert_callbacks: List[Any] = []

    def register_callback(self, callback):
        """注册告警回调函数"""
        self.alert_callbacks.append(callback)

    def get_cooldown_key(self, camera_id: str, alert_type: str) -> str:
        """生成冷却键"""
        return f"{camera_id}:{alert_type}"

    def is_in_cooldown(self, camera_id: str, alert_type: str) -> bool:
        """检查是否在告警冷却期"""
        key = self.get_cooldown_key(camera_id, alert_type)

        if key not in self.alert_cooldowns:
            return False

        last_alert = self.alert_cooldowns[key]
        cooldown = ALERT_COOLDOWN_RULES.get(
            alert_type,
            ALERT_COOLDOWN_RULES["default"]
        )

        return (datetime.now() - last_alert).total_seconds() < cooldown

    def get_min_frames(self, alert_type: str) -> int:
        """获取最小检测帧数"""
        return ALERT_MIN_FRAMES.get(alert_type, ALERT_MIN_FRAMES["default"])

    def should_alert(
        self,
        camera_id: str,
        alert_type: str,
        detections: List[Dict]
    ) -> bool:
        """
        判断是否应该生成告警

        Args:
            camera_id: 摄像头ID
            alert_type: 告警类型
            detections: 检测结果

        Returns:
            bool: 是否应该告警
        """
        # 检查冷却期
        if self.is_in_cooldown(camera_id, alert_type):
            AlertLogger.log_cooldown(camera_id, alert_type)
            return False

        # 检查是否是合规行为
        if alert_type in COMPLIANT_BEHAVIORS:
            return False

        # 检查检测帧数
        min_frames = self.get_min_frames(alert_type)
        key = self.get_cooldown_key(camera_id, alert_type)

        # 记录检测时间
        now = datetime.now()
        self.recent_detections[key].append(now)

        # 清理5秒前的记录
        cutoff = now - timedelta(seconds=5)
        self.recent_detections[key] = [
            t for t in self.recent_detections[key] if t > cutoff
        ]

        # 检查是否达到最小帧数
        if len(self.recent_detections[key]) < min_frames:
            return False

        return True

    async def create_alert(
        self,
        camera_id: str,
        alert_type: str,
        detections: List[Dict],
        frame: Optional[np.ndarray] = None,
        extra_info: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        创建告警

        Args:
            camera_id: 摄像头ID
            alert_type: 告警类型
            detections: 检测结果
            frame: 原始帧（用于保存图像）
            extra_info: 额外信息

        Returns:
            Optional[Dict]: 告警信息
        """
        if not self.should_alert(camera_id, alert_type, detections):
            return None

        # 计算最高置信度
        max_conf = max(d.get('conf', 0) for d in detections) if detections else 0

        # 确定告警级别
        level = self._determine_level(alert_type, max_conf)

        # 保存告警图像
        image_url = None
        if frame is not None:
            image_url = self._save_alert_image(camera_id, alert_type, frame)

        # 更新冷却时间
        key = self.get_cooldown_key(camera_id, alert_type)
        self.alert_cooldowns[key] = datetime.now()

        # 清理检测计数
        self.recent_detections[key].clear()

        # 获取摄像头名称
        camera_name = self._get_camera_name(camera_id)

        # 构建告警数据
        alert_data = {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "violation_type": alert_type,
            "confidence": max_conf,
            "level": level,
            "status": "pending",
            "detected_at": datetime.now().isoformat(),
            "image_url": image_url,
            "detections": detections,
            "extra_info": extra_info
        }

        # 保存到数据库
        alert_id = self._save_to_database(alert_data)
        alert_data["id"] = alert_id

        # 记录日志
        AlertLogger.log_alert(camera_id, alert_type, max_conf)

        # 触发回调
        for callback in self.alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                alert_logger.error(f"告警回调失败: {e}")

        return alert_data

    def _determine_level(self, alert_type: str, confidence: float) -> str:
        """确定告警级别"""
        # 紧急告警类型
        critical_types = ["fire", "smoke", "fight"]
        if alert_type in critical_types:
            return "critical"

        # 基于置信度
        if confidence >= 0.9:
            return "critical"
        elif confidence >= 0.7:
            return "warning"
        else:
            return "info"

    def _save_alert_image(
        self,
        camera_id: str,
        alert_type: str,
        frame: np.ndarray
    ) -> Optional[str]:
        """保存告警图像"""
        try:
            # 创建目录
            date_str = datetime.now().strftime("%Y-%m-%d")
            dir_path = os.path.join(settings.ALERT_IMAGE_DIR, date_str)
            os.makedirs(dir_path, exist_ok=True)

            # 生成文件名
            time_str = datetime.now().strftime("%H%M%S")
            filename = f"{camera_id}_{alert_type}_{time_str}.jpg"
            filepath = os.path.join(dir_path, filename)

            # 保存图像
            cv2.imwrite(filepath, frame)

            # 返回相对URL
            return f"/alert_images/{date_str}/{filename}"
        except Exception as e:
            alert_logger.error(f"保存告警图像失败: {e}")
            return None

    def _get_camera_name(self, camera_id: str) -> str:
        """获取摄像头名称"""
        try:
            from models.database import SessionLocal, Camera
            db = SessionLocal()
            camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
            db.close()
            return camera.name if camera else f"Camera {camera_id}"
        except Exception:
            return f"Camera {camera_id}"

    def _save_to_database(self, alert_data: Dict) -> Optional[int]:
        """保存告警到数据库"""
        try:
            from models.database import SessionLocal, Alert

            db = SessionLocal()
            alert = Alert(
                camera_id=alert_data["camera_id"],
                camera_name=alert_data["camera_name"],
                violation_type=alert_data["violation_type"],
                confidence=alert_data["confidence"],
                level=alert_data["level"],
                status=alert_data["status"],
                image_url=alert_data.get("image_url"),
                notes=json.dumps(alert_data.get("detections", []))
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            alert_id = alert.id
            db.close()
            return alert_id
        except Exception as e:
            alert_logger.error(f"保存告警到数据库失败: {e}")
            return None

    def get_recent_alerts(
        self,
        camera_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """获取最近的告警"""
        try:
            from models.database import SessionLocal, Alert

            db = SessionLocal()
            query = db.query(Alert)

            if camera_id:
                query = query.filter(Alert.camera_id == camera_id)

            alerts = query.order_by(Alert.detected_at.desc()).limit(limit).all()
            db.close()

            return [
                {
                    "id": alert.id,
                    "camera_id": alert.camera_id,
                    "camera_name": alert.camera_name,
                    "violation_type": alert.violation_type,
                    "confidence": alert.confidence,
                    "level": alert.level,
                    "status": alert.status,
                    "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
                    "image_url": alert.image_url
                }
                for alert in alerts
            ]
        except Exception as e:
            alert_logger.error(f"获取告警列表失败: {e}")
            return []

    def get_alert_stats(
        self,
        camera_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """获取告警统计"""
        try:
            from models.database import SessionLocal, Alert

            db = SessionLocal()
            query = db.query(Alert)

            if camera_id:
                query = query.filter(Alert.camera_id == camera_id)
            if start_date:
                query = query.filter(Alert.detected_at >= start_date)
            if end_date:
                query = query.filter(Alert.detected_at <= end_date)

            total = query.count()
            pending = query.filter(Alert.status == "pending").count()
            confirmed = query.filter(Alert.status == "confirmed").count()
            resolved = query.filter(Alert.status == "resolved").count()
            false_positive = query.filter(Alert.status == "false_positive").count()

            db.close()

            return {
                "total": total,
                "pending": pending,
                "confirmed": confirmed,
                "resolved": resolved,
                "false_positive": false_positive
            }
        except Exception as e:
            alert_logger.error(f"获取告警统计失败: {e}")
            return {"total": 0, "pending": 0, "confirmed": 0, "resolved": 0, "false_positive": 0}


# 全局告警服务实例
alert_service = AlertService()


def get_alert_service() -> AlertService:
    """获取告警服务实例"""
    return alert_service
