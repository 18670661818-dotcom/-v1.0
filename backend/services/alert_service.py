"""
Kitchen AI System - Alert Service
厨房AI系统告警业务逻辑
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.database import Alert, Camera, User, AlertSeverity, AlertStatus
from ..models.schemas import AlertCreate
from ..config import settings
from ..utils.websocket_manager import websocket_manager


class AlertService:
    """告警服务类"""
    
    def __init__(self):
        self.alert_cooldowns: Dict[int, datetime] = {}  # 摄像头ID -> 最后告警时间
        self.alert_counts: Dict[int, List[datetime]] = {}  # 摄像头ID -> 告警时间列表
    
    async def create_alert(
        self, 
        db: Session, 
        camera: Camera, 
        alert_data: AlertCreate
    ) -> Optional[Alert]:
        """
        创建告警
        
        Args:
            db: 数据库会话
            camera: 摄像头对象
            alert_data: 告警数据
            
        Returns:
            Optional[Alert]: 创建的告警对象，如果被限流则返回None
        """
        # 检查告警冷却
        if self._is_in_cooldown(camera.id):
            return None
        
        # 检查告警频率限制
        if self._is_rate_limited(camera.id):
            return None
        
        # 创建告警
        db_alert = Alert(
            title=alert_data.title,
            message=alert_data.message,
            severity=alert_data.severity,
            camera_id=camera.id,
            user_id=camera.owner_id,
            confidence=alert_data.confidence,
            detection_data=alert_data.detection_data,
            image_url=alert_data.image_url,
            status=AlertStatus.PENDING
        )
        
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        
        # 更新冷却和计数
        self._update_cooldown(camera.id)
        self._update_rate_limit(camera.id)
        
        # 发送WebSocket通知
        await self._send_alert_notification(db_alert)
        
        return db_alert
    
    def _is_in_cooldown(self, camera_id: int) -> bool:
        """
        检查是否在告警冷却期
        
        Args:
            camera_id: 摄像头ID
            
        Returns:
            bool: 是否在冷却期
        """
        if camera_id not in self.alert_cooldowns:
            return False
        
        last_alert_time = self.alert_cooldowns[camera_id]
        cooldown_period = timedelta(seconds=settings.ALERT_COOLDOWN_SECONDS)
        
        return datetime.now() - last_alert_time < cooldown_period
    
    def _is_rate_limited(self, camera_id: int) -> bool:
        """
        检查是否超过告警频率限制
        
        Args:
            camera_id: 摄像头ID
            
        Returns:
            bool: 是否被限流
        """
        if camera_id not in self.alert_counts:
            return False
        
        # 清理一小时前的记录
        one_hour_ago = datetime.now() - timedelta(hours=1)
        self.alert_counts[camera_id] = [
            t for t in self.alert_counts[camera_id] if t > one_hour_ago
        ]
        
        # 检查是否超过限制
        return len(self.alert_counts[camera_id]) >= settings.MAX_ALERTS_PER_HOUR
    
    def _update_cooldown(self, camera_id: int):
        """
        更新告警冷却时间
        
        Args:
            camera_id: 摄像头ID
        """
        self.alert_cooldowns[camera_id] = datetime.now()
    
    def _update_rate_limit(self, camera_id: int):
        """
        更新告警频率计数
        
        Args:
            camera_id: 摄像头ID
        """
        if camera_id not in self.alert_counts:
            self.alert_counts[camera_id] = []
        
        self.alert_counts[camera_id].append(datetime.now())
    
    async def _send_alert_notification(self, alert: Alert):
        """
        发送告警通知
        
        Args:
            alert: 告警对象
        """
        try:
            notification_data = {
                "alert_id": alert.id,
                "camera_id": alert.camera_id,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.created_at.isoformat() if alert.created_at else datetime.now().isoformat()
            }
            
            await websocket_manager.broadcast_alert(notification_data)
            
        except Exception as e:
            print(f"Failed to send alert notification: {e}")
    
    async def process_inference_result(
        self,
        db: Session,
        camera: Camera,
        detections: List[Dict],
        confidence: float,
        image_url: Optional[str] = None
    ) -> Optional[Alert]:
        """
        处理推理结果并生成告警
        
        Args:
            db: 数据库会话
            camera: 摄像头对象
            detections: 检测结果列表
            confidence: 置信度
            image_url: 图像URL
            
        Returns:
            Optional[Alert]: 生成的告警对象
        """
        if not detections:
            return None
        
        # 检查是否有高置信度的检测结果
        high_confidence_detections = [
            d for d in detections 
            if d.get("confidence", 0) >= camera.confidence_threshold
        ]
        
        if not high_confidence_detections:
            return None
        
        # 确定告警严重程度
        max_confidence = max([d.get("confidence", 0) for d in high_confidence_detections])
        severity = self._determine_severity(max_confidence, high_confidence_detections)
        
        # 生成告警标题和消息
        detection_types = set([d.get("class", "unknown") for d in high_confidence_detections])
        title = f"检测到异常: {', '.join(detection_types)}"
        message = f"摄像头 {camera.name} 检测到 {len(high_confidence_detections)} 个异常对象"
        
        # 创建告警数据
        alert_data = AlertCreate(
            title=title,
            message=message,
            severity=severity,
            camera_id=camera.id,
            confidence=max_confidence,
            detection_data=str(high_confidence_detections),
            image_url=image_url
        )
        
        # 创建告警
        return await self.create_alert(db, camera, alert_data)
    
    def _determine_severity(
        self, 
        confidence: float, 
        detections: List[Dict]
    ) -> str:
        """
        确定告警严重程度
        
        Args:
            confidence: 置信度
            detections: 检测结果
            
        Returns:
            str: 严重程度
        """
        # 基于置信度确定严重程度
        if confidence >= 0.9:
            return AlertSeverity.CRITICAL
        elif confidence >= 0.8:
            return AlertSeverity.HIGH
        elif confidence >= 0.7:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW
    
    def get_alert_statistics(
        self,
        db: Session,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        获取告警统计信息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict: 统计信息
        """
        query = db.query(Alert).join(Camera).filter(Camera.owner_id == user_id)
        
        if start_date:
            query = query.filter(Alert.created_at >= start_date)
        if end_date:
            query = query.filter(Alert.created_at <= end_date)
        
        # 按状态统计
        status_stats = {}
        for status in AlertStatus:
            count = query.filter(Alert.status == status).count()
            status_stats[status.value] = count
        
        # 按严重程度统计
        severity_stats = {}
        for severity in AlertSeverity:
            count = query.filter(Alert.severity == severity).count()
            severity_stats[severity.value] = count
        
        # 按摄像头统计
        camera_stats = {}
        cameras = db.query(Camera).filter(Camera.owner_id == user_id).all()
        for camera in cameras:
            count = query.filter(Alert.camera_id == camera.id).count()
            camera_stats[camera.name] = count
        
        return {
            "total": query.count(),
            "by_status": status_stats,
            "by_severity": severity_stats,
            "by_camera": camera_stats
        }
    
    def cleanup_old_alerts(self, db: Session, days: int = 30):
        """
        清理旧告警
        
        Args:
            db: 数据库会话
            days: 保留天数
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 删除已解决的旧告警
        deleted_count = db.query(Alert).filter(
            and_(
                Alert.status == AlertStatus.RESOLVED,
                Alert.created_at < cutoff_date
            )
        ).delete()
        
        db.commit()
        
        print(f"Cleaned up {deleted_count} old alerts")
        return deleted_count


# 全局告警服务实例
alert_service = AlertService()