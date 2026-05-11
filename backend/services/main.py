"""
服务层主入口 - 整合摄像头、推理、告警、WebSocket服务
"""
import os
import sys
import time
import signal
import asyncio
from typing import Dict

from core.logger import app_logger, get_logger

logger = get_logger("services.main")


def load_camera_config() -> dict:
    """从数据库或配置文件加载摄像头配置"""
    config = {}

    # 尝试从数据库加载
    try:
        from models.database import SessionLocal, Camera
        db = SessionLocal()
        cameras = db.query(Camera).filter(Camera.is_active == True).all()
        for cam in cameras:
            config[cam.camera_id] = {
                "rtsp_url": cam.rtsp_url,
                "location": cam.location or cam.name,
                "enabled": cam.is_active
            }
        db.close()
        logger.info(f"从数据库加载了 {len(config)} 个摄像头")
    except Exception as e:
        logger.warning(f"无法从数据库加载摄像头: {e}")

    # 如果数据库没有配置，尝试从JSON文件加载
    return config

    if False and not config:
        try:
            import json
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'database_only_disabled.json'
            )
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    rtsp_urls = json.load(f)
                for cam_id, rtsp_url in rtsp_urls.items():
                    config[cam_id] = {
                        "rtsp_url": rtsp_url,
                        "location": f"摄像头 {cam_id}",
                        "enabled": True
                    }
                logger.info(f"从配置文件加载了 {len(config)} 个摄像头")
        except Exception as e:
            logger.warning(f"无法从配置文件加载摄像头: {e}")

    # 使用默认配置
    if not config:
        config = {
            "cam_001": {
                "rtsp_url": "rtsp://127.0.0.1:8554/kitchen_01",
                "location": "食堂1号后厨-A区",
                "enabled": True
            },
            "cam_002": {
                "rtsp_url": "rtsp://127.0.0.1:8554/kitchen_02",
                "location": "食堂1号后厨-B区",
                "enabled": True
            },
            "cam_003": {
                "rtsp_url": "rtsp://127.0.0.1:8554/kitchen_03",
                "location": "食堂1号后厨-C区",
                "enabled": True
            }
        }
        logger.info("使用默认摄像头配置")

    return config


class ServiceManager:
    """服务管理器 - 统一管理所有服务"""

    def __init__(self):
        self.camera_service = None
        self.inference_service = None
        self.alert_service = None
        self.websocket_service = None
        self._running = False

    def initialize(self, inference_fps: float = 3.0):
        """
        初始化所有服务

        Args:
            inference_fps: 推理帧率（每秒帧数）
        """
        logger.info("正在初始化服务...")

        # 延迟导入，避免循环导入
        from services.camera_service import camera_service
        from services.inference_service import get_inference_service
        from services.alert_service import get_alert_service
        from services.websocket_service import websocket_service

        # 初始化摄像头服务
        self.camera_service = camera_service
        logger.info("摄像头服务已初始化")

        # 初始化推理服务
        self.inference_service = get_inference_service()
        logger.info("推理服务已初始化")

        # 初始化告警服务
        self.alert_service = get_alert_service()
        logger.info("告警服务已初始化")

        # 初始化WebSocket服务
        self.websocket_service = websocket_service
        logger.info("WebSocket服务已初始化")

        # 连接服务
        self._connect_services()

        logger.info("所有服务初始化完成")

    def _connect_services(self):
        """连接服务之间的回调"""
        # 摄像头 -> 推理服务
        self.camera_service.set_frame_callback(self._on_frame_received)

        # 推理服务 -> 告警服务
        if hasattr(self.inference_service, 'set_alert_service'):
            self.inference_service.set_alert_service(self.alert_service)

        # 注册告警回调 -> WebSocket推送
        self.alert_service.register_callback(self._on_alert_created)

    def _on_frame_received(self, camera_id: str, frame):
        """帧接收回调 - 从摄像头服务到推理服务"""
        location = ""
        if camera_id in self.camera_service._cameras:
            location = self.camera_service._cameras[camera_id].location
        self.inference_service.submit_frame(camera_id, frame, location)

    async def _on_alert_created(self, alert_data: dict):
        """告警创建回调 - 推送到WebSocket"""
        try:
            await self.websocket_service.broadcast_alert(alert_data)
        except Exception as e:
            logger.error(f"WebSocket告警推送失败: {e}")

    def load_cameras(self, camera_config: dict):
        """加载摄像头配置"""
        for camera_id, config in camera_config.items():
            if config.get("enabled", True):
                self.camera_service.add_camera(
                    camera_id=camera_id,
                    rtsp_url=config.get("rtsp_url", ""),
                    location=config.get("location", "")
                )

    def start(self):
        """启动所有服务"""
        if self._running:
            logger.warning("服务已在运行")
            return

        self._running = True

        # 启动推理服务
        self.inference_service.start()

        # 启动摄像头服务
        self.camera_service.start()

        logger.info("所有服务已启动")

    def stop(self):
        """停止所有服务"""
        if not self._running:
            return

        self._running = False

        # 停止摄像头服务
        if self.camera_service:
            self.camera_service.stop()

        # 停止推理服务
        if self.inference_service:
            self.inference_service.stop()

        logger.info("所有服务已停止")

    def restart(self):
        """重启所有服务"""
        logger.info("重启服务...")
        self.stop()
        time.sleep(1)
        self.start()
        logger.info("服务重启完成")

    def get_status(self) -> Dict:
        """获取所有服务状态"""
        status = {
            "running": self._running,
            "camera_service": self.camera_service.get_all_status() if self.camera_service else None,
            "inference_service": self.inference_service.get_status() if self.inference_service else None,
            "alert_service": self.alert_service.get_recent_alerts(limit=1) if self.alert_service else None,
            "websocket_service": self.websocket_service.get_connection_count() if self.websocket_service else None
        }
        return status


# 全局服务管理器实例
service_manager = ServiceManager()


def get_service_manager() -> ServiceManager:
    """获取服务管理器实例"""
    return service_manager


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='后厨智能监测系统服务')
    parser.add_argument('--service', choices=['camera', 'inference', 'all'],
                       default='all', help='要启动的服务')
    parser.add_argument('--fps', type=float, default=3.0, help='推理帧率')

    args = parser.parse_args()

    # 加载摄像头配置
    camera_config = load_camera_config()

    # 初始化服务
    service_manager.initialize(inference_fps=args.fps)

    # 加载摄像头
    service_manager.load_cameras(camera_config)

    # 信号处理
    def signal_handler(sig, frame):
        logger.info("收到停止信号，正在关闭服务...")
        service_manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动服务
    if args.service == 'all':
        service_manager.start()
    elif args.service == 'camera':
        service_manager.camera_service.start()
    elif args.service == 'inference':
        service_manager.inference_service.start()

    logger.info("=" * 50)
    logger.info("厨房AI系统服务层已启动")
    logger.info("=" * 50)
    logger.info("服务架构:")
    logger.info("  ├── camera_service    (摄像头服务)")
    logger.info("  ├── inference_service (推理服务)")
    logger.info("  ├── alert_service     (告警服务)")
    logger.info("  └── websocket_service (WebSocket服务)")
    logger.info("=" * 50)
    logger.info("按 Ctrl+C 停止服务...")

    # 主循环
    try:
        while True:
            time.sleep(1)
            # 定期打印状态
            status = service_manager.get_status()
            if status["camera_service"]:
                cameras = status["camera_service"].get("cameras", {})
                online_count = sum(1 for c in cameras.values() if c and c.get("is_online"))
                logger.debug(f"摄像头状态: {online_count}/{len(cameras)} 在线")
    except KeyboardInterrupt:
        pass
    finally:
        service_manager.stop()


if __name__ == "__main__":
    main()
