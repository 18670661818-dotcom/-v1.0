"""
WebSocket连接管理 - 用于实时推送告警
"""
from typing import Dict, Set, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # 全局广播频道（管理员等）
        self.broadcast_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """建立WebSocket连接"""
        await websocket.accept()

        if user_id:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        else:
            self.broadcast_connections.add(websocket)

        logger.info(f"WebSocket连接建立: user_id={user_id}, 总连接数={len(self.active_connections)}")

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

    async def broadcast_alert(self, alert_data: dict, user_ids: List[int]):
        """
        广播告警消息给指定用户列表
        alert_data: 告警详情
        user_ids: 需要接收告警的用户ID列表
        """
        message = {
            "type": "alert",
            "data": alert_data,
        }

        for user_id in user_ids:
            await self.send_to_user(user_id, message)

        # 同时发送给所有广播连接（管理员等）
        await self.broadcast(message)

    async def send_to_all_users(self, message: dict):
        """向所有已连接的用户发送消息"""
        all_user_ids = list(self.active_connections.keys())
        for user_id in all_user_ids:
            await self.send_to_user(user_id, message)

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
        }

    def is_user_connected(self, user_id: int) -> bool:
        """检查用户是否在线"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


# 全局单例
manager = ConnectionManager()