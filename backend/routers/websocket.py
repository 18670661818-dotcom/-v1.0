"""WebSocket路由"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import json
import logging

from utils.websocket_manager import manager
from utils.auth_utils import verify_token_ws  # WebSocket版本的身份验证

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/alerts")
async def websocket_alerts(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket端点：实时告警推送
    客户端连接：ws://localhost:8000/ws/alerts?token=your_jwt_token
    
    接收的消息格式（客户端→服务端）：
    {
        "action": "subscribe",      # subscribe / unsubscribe / ping
        "camera_ids": ["cam_001"]   # 可选，订阅特定摄像头的告警
    }
    
    推送的消息格式（服务端→客户端）：
    {
        "type": "alert",
        "data": {
            "alert_id": "xxx",
            "camera_id": "cam_001",
            "violation_type": "no_hat",
            "confidence": 0.95,
            ...
        }
    }
    """
    # 验证Token
    try:
        user = await verify_token_ws(token)
        if not user:
            await websocket.close(code=4001, reason="认证失败")
            return
    except Exception:
        await websocket.close(code=4001, reason="认证失败")
        return

    # 建立连接
    await manager.connect(websocket, user_id=user.id)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action", "")
                
                if action == "ping":
                    # 心跳响应
                    await websocket.send_json({"type": "pong"})
                
                elif action == "subscribe":
                    # 可以在这里处理订阅逻辑
                    camera_ids = message.get("camera_ids", [])
                    # TODO: 记录用户订阅的摄像头
                    await websocket.send_json({
                        "type": "subscribed",
                        "camera_ids": camera_ids
                    })
                
                elif action == "get_status":
                    # 返回连接状态
                    await websocket.send_json({
                        "type": "status",
                        "connections": manager.get_connection_count()
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "无效的JSON格式"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开: user_id={user.id}")
    except Exception as e:
        logger.error(f"WebSocket异常: {e}")
    finally:
        manager.disconnect(websocket, user_id=user.id)


@router.websocket("/ws/monitor/{camera_id}")
async def websocket_monitor(
    websocket: WebSocket,
    camera_id: str,
    token: str = Query(...),
):
    """
    WebSocket端点：单路实时画面推送（可选）
    用于前端实时显示检测画面
    """
    try:
        user = await verify_token_ws(token)
        if not user:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user_id=user.id)

    try:
        while True:
            # 接收心跳
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id=user.id)