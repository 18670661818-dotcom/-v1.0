"""
服务层主入口 - 整合摄像头、推理、告警、WebSocket服务
"""
import os
import sys
import time
import signal
import logging
import asyncio
from typing import Dict

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_camera_config() -> dict:
    """从数据库或配置文件加载摄像头配置"""
    config = {}

    # 尝试从数据库加载
    try:
        from backend.models.database import SessionLocal, Camera
        db = SessionLocal()
        cameras = db.query(Camera).filter(Camera.enabled == True).all()
        for cam in cameras:
            config[cam.camera_id] = {
                "rtsp_url": cam.rtsp_url,
                "location": cam.location or cam.name,
                "enabled": cam.enabled
            }
        db.close()
        logger.info(f"从数据库加载了 {len(config)} 个摄像头")
    except Exception as e:
        logger.warning(f"无法从数据库加载摄像头: {e}")

    # 如果数据库没有配置，尝试从JSON文件加载
    if not config:
        try:
            import json
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'rtsp_config.json'
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
        self.alert_manager = None
        self.websocket_service = None
        self._running = False

    def initialize(self, inference_fps: float = 3.0):
        """
        初始化所有服务

        Args:
            inference_fps: 推理帧率（每秒帧数）
        """
        logger.info("正在初始化服务...")

        # 初始化摄像头服务
        from backend.services.camera_service import CameraService
        self.camera_service = CameraService()
        logger.info("摄像头服务已初始化")

        # 初始化推理服务
        from backend.services.inference_service import InferenceService
        self.inference_service = InferenceService(inference_fps=inference_fps)
        logger.info("推理服务已初始化")

        # 初始化告警管理器
        try:
            from backend.engine.alert_manager import AlertManager
            self.alert_manager = AlertManager()
            self.inference_service.set_alert_service(self.alert_manager)
            logger.info("告警管理器已初始化")
        except Exception as e:
            logger.warning(f"无法初始化告警管理器: {e}")

        # 初始化WebSocket服务
        from backend.services.websocket_service import WebSocketService
        self.websocket_service = WebSocketService()
        logger.info("WebSocket服务已初始化")

        # 连接摄像头服务和推理服务
        self.camera_service.set_frame_callback(self._on_frame_received)

        # 添加推理结果回调
        self.inference_service.add_result_callback(self._on_detection_result)

        logger.info("所有服务初始化完成")

    def _on_frame_received(self, camera_id: str, frame):
        """帧接收回调 - 从摄像头服务到推理服务"""
        location = ""
        if camera_id in self.camera_service._cameras:
            location = self.camera_service._cameras[camera_id].location
        self.inference_service.submit_frame(camera_id, frame, location)

    def _on_detection_result(self, camera_id: str, detections: list, frame):
        """检测结果回调 - 推送到WebSocket"""
        try:
            # 异步推送检测结果
            asyncio.create_task(
                self.websocket_service.broadcast_detection(camera_id, detections)
            )
        except Exception as e:
            logger.debug(f"WebSocket推送失败: {e}")

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

    def get_status(self) -> Dict:
        """获取所有服务状态"""
        status = {
            "running": self._running,
            "camera_service": self.camera_service.get_all_status() if self.camera_service else None,
            "inference_service": self.inference_service.get_status() if self.inference_service else None,
            "websocket_service": self.websocket_service.get_connection_count() if self.websocket_service else None
        }
        return status


# 全局服务管理器实例
service_manager = ServiceManager()


def main():
    """主函数"""
    # 加载摄像头配置
    camera_config = load_camera_config()

    # 初始化服务
    service_manager.initialize(inference_fps=3.0)

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
    service_manager.start()

    logger.info("=" * 50)
    logger.info("厨房AI系统服务层已启动")
    logger.info("=" * 50)
    logger.info("服务架构:")
    logger.info("  ├── camera_service   (摄像头服务)")
    logger.info("  ├── inference_service (推理服务)")
    logger.info("  ├── alert_service    (告警服务)")
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
                cameras = status["camera_service"]["cameras"]
                online_count = sum(1 for c in cameras.values() if c and c.get("is_online"))
                logger.debug(f"摄像头状态: {online_count}/{len(cameras)} 在线")
    except KeyboardInterrupt:
        pass
    finally:
        service_manager.stop()


if __name__ == "__main__":
    main()
