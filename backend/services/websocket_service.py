"""
WebSocket服务 - 服务层
功能：
1. 管理WebSocket连接
2. 推送告警通知
3. 推送摄像头状态
4. 推送检测结果
"""
import asyncio
import logging
from typing import Dict, Set, Optional, List
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketService:
    """WebSocket服务类"""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # 全局广播频道（管理员等）
        self.broadcast_connections: Set[WebSocket] = set()
        # 摄像头订阅: camera_id -> set of user_ids
        self.camera_subscriptions: Dict[str, Set[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """建立WebSocket连接"""
        await websocket.accept()

        if user_id:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        else:
            self.broadcast_connections.add(websocket)

        logger.info(f"WebSocket连接建立: user_id={user_id}")

    def disconnect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """断开WebSocket连接"""
        if user_id and user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        self.broadcast_connections.discard(websocket)
        logger.info(f"WebSocket连接断开: user_id={user_id}")

    async def send_to_user(self, user_id: int, message: dict):
        """向特定用户发送消息"""
        if user_id not in self.active_connections:
            return

        dead_connections = set()
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket发送失败 (user_id={user_id}): {e}")
                dead_connections.add(websocket)

        # 清理死连接
        for ws in dead_connections:
            self.active_connections[user_id].discard(ws)
        if not self.active_connections.get(user_id):
            self.active_connections.pop(user_id, None)

    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        dead_connections = set()
        for websocket in self.broadcast_connections:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.add(websocket)

        self.broadcast_connections -= dead_connections

    async def send_to_all_users(self, message: dict):
        """向所有已连接的用户发送消息"""
        all_user_ids = list(self.active_connections.keys())
        for user_id in all_user_ids:
            await self.send_to_user(user_id, message)

    def subscribe_camera(self, camera_id: str, user_id: int):
        """订阅摄像头"""
        if camera_id not in self.camera_subscriptions:
            self.camera_subscriptions[camera_id] = set()
        self.camera_subscriptions[camera_id].add(user_id)
        logger.info(f"用户 {user_id} 订阅摄像头 {camera_id}")

    def unsubscribe_camera(self, camera_id: str, user_id: int):
        """取消订阅摄像头"""
        if camera_id in self.camera_subscriptions:
            self.camera_subscriptions[camera_id].discard(user_id)
            if not self.camera_subscriptions[camera_id]:
                del self.camera_subscriptions[camera_id]
        logger.info(f"用户 {user_id} 取消订阅摄像头 {camera_id}")

    async def send_to_camera_subscribers(self, camera_id: str, message: dict):
        """向摄像头订阅者发送消息"""
        if camera_id not in self.camera_subscriptions:
            return

        user_ids = list(self.camera_subscriptions[camera_id])
        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    async def broadcast_alert(self, alert_data: dict, user_ids: List[int] = None):
        """
        广播告警消息

        Args:
            alert_data: 告警详情
            user_ids: 需要接收告警的用户ID列表，None则广播给所有人
        """
        message = {
            "type": "alert",
            "data": alert_data,
            "timestamp": datetime.now().isoformat()
        }

        if user_ids:
            for user_id in user_ids:
                await self.send_to_user(user_id, message)
        else:
            # 广播给所有连接
            await self.send_to_all_users(message)
            await self.broadcast(message)

    async def broadcast_camera_status(self, camera_id: str, status: dict):
        """
        广播摄像头状态

        Args:
            camera_id: 摄像头ID
            status: 状态信息
        """
        message = {
            "type": "camera_status",
            "camera_id": camera_id,
            "data": status,
            "timestamp": datetime.now().isoformat()
        }

        # 发送给摄像头订阅者
        await self.send_to_camera_subscribers(camera_id, message)

        # 广播给所有人
        await self.broadcast(message)

    async def broadcast_detection(self, camera_id: str, detections: list):
        """
        广播检测结果

        Args:
            camera_id: 摄像头ID
            detections: 检测结果列表
        """
        message = {
            "type": "detection",
            "camera_id": camera_id,
            "data": detections,
            "timestamp": datetime.now().isoformat()
        }

        # 发送给摄像头订阅者
        await self.send_to_camera_subscribers(camera_id, message)

    async def broadcast_system_status(self, status: dict):
        """
        广播系统状态

        Args:
            status: 系统状态信息
        """
        message = {
            "type": "system_status",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }

        await self.send_to_all_users(message)
        await self.broadcast(message)

    def get_connection_count(self) -> dict:
        """获取当前连接数统计"""
        user_count = len(self.active_connections)
        total_connections = sum(
            len(conns) for conns in self.active_connections.values()
        ) + len(self.broadcast_connections)

        return {
            "users": user_count,
            "total_connections": total_connections,
            "broadcast_only": len(self.broadcast_connections),
            "camera_subscriptions": {
                cam_id: len(user_ids)
                for cam_id, user_ids in self.camera_subscriptions.items()
            }
        }

    def is_user_connected(self, user_id: int) -> bool:
        """检查用户是否在线"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_subscribed_users(self, camera_id: str) -> Set[int]:
        """获取订阅了特定摄像头的用户列表"""
        return self.camera_subscriptions.get(camera_id, set())


# 全局WebSocket服务实例
websocket_service = WebSocketService()
