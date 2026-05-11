"""
WebSocket API
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Optional
import json

from services.websocket_service import websocket_service
from core.logger import get_logger

logger = get_logger("api.websocket")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    camera_id: Optional[str] = None
):
    """
    WebSocket连接端点

    - **user_id**: 用户ID
    - **camera_id**: 可选，订阅的摄像头ID
    """
    await websocket_service.connect(websocket, user_id)
    logger.info(f"WebSocket连接: user={user_id}, camera={camera_id}")

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            # 处理不同类型的消息
            msg_type = message.get("type")

            if msg_type == "subscribe":
                # 订阅摄像头
                cam_id = message.get("camera_id", camera_id)
                if cam_id:
                    websocket_service.subscribe_camera(user_id, cam_id)
                    await websocket.send_json({
                        "type": "subscribed",
                        "camera_id": cam_id
                    })

            elif msg_type == "unsubscribe":
                # 取消订阅
                cam_id = message.get("camera_id")
                if cam_id:
                    websocket_service.unsubscribe_camera(user_id, cam_id)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "camera_id": cam_id
                    })

            elif msg_type == "ping":
                # 心跳
                await websocket.send_json({"type": "pong"})

            else:
                # 转发消息到服务处理
                await websocket_service.handle_message(user_id, message)

    except WebSocketDisconnect:
        logger.info(f"WebSocket断开: user={user_id}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        await websocket_service.disconnect(user_id)


@router.websocket("/ws/camera/{camera_id}")
async def camera_stream_endpoint(
    websocket: WebSocket,
    camera_id: str
):
    """
    摄像头流WebSocket端点
    实时推送摄像头画面

    - **camera_id**: 摄像头ID
    """
    await websocket_service.connect(websocket, f"camera_{camera_id}")
    logger.info(f"摄像头流连接: camera={camera_id}")

    try:
        # 订阅该摄像头
        websocket_service.subscribe_camera(f"camera_{camera_id}", camera_id)

        while True:
            # 接收客户端消息（主要是心跳）
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"摄像头流断开: camera={camera_id}")
    except Exception as e:
        logger.error(f"摄像头流错误: {e}")
    finally:
        await websocket_service.disconnect(f"camera_{camera_id}")


@router.get("/ws/stats")
def get_websocket_stats():
    """获取WebSocket连接统计"""
    return websocket_service.get_connection_count()
