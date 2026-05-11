"""
推理服务管理 - 独立运行或集成到API
"""
import sys
import os
import threading
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.inference_engine import BatchInferenceEngine
from engine.camera_manager import CameraManager
from engine.alert_manager import AlertManager
from config import MODEL_PATH, BATCH_SIZE, SAMPLE_INTERVAL, CAMERA_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局推理服务实例
inference_service = None


class InferenceService:
    """推理服务封装"""

    def __init__(self):
        self.engine = None
        self.camera_manager = None
        self.alert_manager = None
        self.inference_thread = None
        self.running = False

    def start(self, camera_configs: dict = None):
        """启动推理服务"""
        if self.running:
            logger.warning("推理服务已在运行")
            return

        logger.info("正在启动推理引擎...")

        # 初始化告警管理器
        self.alert_manager = AlertManager()
        logger.info("告警管理器已初始化")

        # 初始化推理引擎
        self.engine = BatchInferenceEngine(MODEL_PATH, batch_size=BATCH_SIZE)
        logger.info("推理引擎已初始化")

        # 启动推理线程
        self.inference_thread = threading.Thread(
            target=self.engine.inference_loop,
            args=(self.alert_manager,),
            daemon=True,
        )
        self.inference_thread.start()
        logger.info("推理线程已启动")

        # 启动摄像头管理器
        configs = camera_configs or CAMERA_CONFIG
        logger.info(f"摄像头配置: {list(configs.keys())}")
        self.camera_manager = CameraManager(self.engine)
        self.camera_manager.start_all()
        logger.info("摄像头管理器已启动")

        self.running = True
        logger.info("推理服务启动完成")

    def stop(self):
        """停止推理服务"""
        if not self.running:
            return

        logger.info("正在停止推理服务...")

        if self.camera_manager:
            self.camera_manager.stop_all()

        self.running = False

        if self.inference_thread:
            self.inference_thread.join(timeout=5)

        logger.info("推理服务已停止")

    def get_alerts(self, limit=50):
        """获取最近的告警"""
        if self.alert_manager:
            return self.alert_manager._alert_history[-limit:]
        return []

    def get_status(self):
        """获取服务状态"""
        return {
            "running": self.running,
            "cameras_total": len(self.camera_manager._streams) if self.camera_manager else 0,
            "alerts_total": len(self.alert_manager._alert_history) if self.alert_manager else 0,
        }


# 启动入口
if __name__ == "__main__":
    import json

    # 从数据库加载摄像头配置
    try:
        from models.database import SessionLocal, Camera
        db = SessionLocal()
        cameras = db.query(Camera).filter(Camera.enabled == True).all()
        camera_configs = {}
        for cam in cameras:
            camera_configs[cam.camera_id] = {
                "rtsp_url": cam.rtsp_url,
                "location": cam.location or cam.name,
                "enabled": cam.enabled,
            }
        db.close()
        logger.info(f"从数据库加载了 {len(camera_configs)} 个摄像头")
    except Exception as e:
        logger.warning(f"无法从数据库加载摄像头: {e}")
        # 使用模拟配置
        camera_configs = {
            "cam_001": {
                "rtsp_url": "rtsp://127.0.0.1:8554/kitchen_01",
                "location": "食堂1号后厨-A区",
                "enabled": True,
            },
            "cam_002": {
                "rtsp_url": "rtsp://127.0.0.1:8554/kitchen_02",
                "location": "食堂1号后厨-B区",
                "enabled": True,
            },
            "cam_003": {
                "rtsp_url": "rtsp://127.0.0.1:8554/kitchen_03",
                "location": "食堂1号后厨-C区",
                "enabled": True,
            },
        }

    service = InferenceService()
    inference_service = service

    try:
        service.start(camera_configs)
        logger.info("推理服务运行中，按 Ctrl+C 停止...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()
        logger.info("推理服务已退出")
