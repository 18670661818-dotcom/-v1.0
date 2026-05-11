"""
摄像头服务 - 独立模块
功能：
1. 读取RTSP流
2. 缓存最新帧
3. YOLO推理
4. 推送结果
"""
import os
import sys
import time
import threading
import logging
import cv2
import numpy as np
from typing import Dict, Optional, Tuple
from collections import deque
from dataclasses import dataclass
from datetime import datetime

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """检测结果数据类"""
    camera_id: str
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    timestamp: float


class FrameCache:
    """帧缓存管理器"""
    
    def __init__(self, max_size: int = 30):
        """
        初始化帧缓存
        
        Args:
            max_size: 最大缓存帧数
        """
        self.max_size = max_size
        self._cache: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._latest_frame: Dict[str, np.ndarray] = {}
    
    def update(self, camera_id: str, frame: np.ndarray) -> None:
        """更新帧缓存"""
        with self._lock:
            if camera_id not in self._cache:
                self._cache[camera_id] = deque(maxlen=self.max_size)
            
            self._cache[camera_id].append({
                'frame': frame,
                'timestamp': time.time()
            })
            self._latest_frame[camera_id] = frame
    
    def get_latest(self, camera_id: str) -> Optional[np.ndarray]:
        """获取最新帧"""
        with self._lock:
            return self._latest_frame.get(camera_id)
    
    def get_frame_count(self, camera_id: str) -> int:
        """获取缓存帧数"""
        with self._lock:
            if camera_id in self._cache:
                return len(self._cache[camera_id])
            return 0


class CameraWorker:
    """摄像头工作线程"""

    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        location: str,
        frame_cache: FrameCache,
        inference_callback=None,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 3.0
    ):
        """
        初始化摄像头工作线程

        Args:
            camera_id: 摄像头ID
            rtsp_url: RTSP流地址
            location: 摄像头位置
            frame_cache: 帧缓存管理器
            inference_callback: 推理回调函数
            max_reconnect_attempts: 最大重连尝试次数
            reconnect_delay: 重连延迟（秒）
        """
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.location = location
        self.frame_cache = frame_cache
        self.inference_callback = inference_callback
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None

        # 统计信息
        self.frame_count = 0
        self.last_frame_time = 0
        self.fps = 0.0

        # 连接状态
        self.is_online = False
        self.is_reconnecting = False
        self.reconnect_attempts = 0
        self._last_reconnect_time = 0
    
    def start(self) -> None:
        """启动工作线程"""
        if self._running:
            logger.warning(f"[{self.camera_id}] 已在运行")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name=f"Camera-{self.camera_id}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[{self.camera_id}] 工作线程已启动")
    
    def stop(self) -> None:
        """停止工作线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
        logger.info(f"[{self.camera_id}] 工作线程已停止")
    
    def _create_status_frame(self, status_text: str, is_error: bool = False) -> np.ndarray:
        """
        创建带状态文字的帧

        Args:
            status_text: 状态文字
            is_error: 是否为错误状态（使用红色背景）

        Returns:
            带状态文字的帧
        """
        # 创建黑色背景
        frame = np.zeros((640, 640, 3), dtype=np.uint8)

        # 根据状态选择颜色
        if is_error:
            bg_color = (0, 0, 180)  # 红色背景
            text_color = (255, 255, 255)  # 白色文字
        else:
            bg_color = (0, 120, 0)  # 绿色背景
            text_color = (255, 255, 255)  # 白色文字

        # 绘制状态栏背景
        cv2.rectangle(frame, (0, 0), (640, 80), bg_color, -1)

        # 绘制摄像头ID
        cv2.putText(
            frame,
            f"Camera: {self.camera_id}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            text_color,
            2
        )

        # 绘制状态文字
        cv2.putText(
            frame,
            status_text,
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            text_color,
            2
        )

        # 绘制位置信息
        cv2.putText(
            frame,
            f"Location: {self.location}",
            (20, 600),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (150, 150, 150),
            1
        )

        return frame

    def _run(self) -> None:
        """工作线程主循环"""
        logger.info(f"[{self.camera_id}] 连接RTSP: {self.rtsp_url}")

        # 打开RTSP流
        self._cap = cv2.VideoCapture(self.rtsp_url)

        if not self._cap.isOpened():
            logger.error(f"[{self.camera_id}] 无法打开RTSP流")
            self.is_online = False
            # 尝试重连
            if self._reconnect():
                # 重连成功，继续运行
                pass
            else:
                # 重连失败，使用离线帧
                self._run_with_offline_frames()
                return

        self.is_online = True
        self.reconnect_attempts = 0
        logger.info(f"[{self.camera_id}] RTSP流已打开")

        last_time = time.time()
        frame_interval = 0.1  # 10 FPS 读取帧率

        while self._running:
            current_time = time.time()

            # 控制读取帧率
            if current_time - last_time < frame_interval:
                time.sleep(0.01)
                continue

            # 读取帧
            ret, frame = self._cap.read()

            if not ret or frame is None:
                logger.warning(f"[{self.camera_id}] 读取帧失败")
                self.is_online = False

                # 生成离线提示帧
                offline_frame = self._create_status_frame("摄像头离线 - 准备重连...", is_error=True)
                self.frame_cache.update(self.camera_id, offline_frame)
                if self.inference_callback:
                    self.inference_callback(self.camera_id, offline_frame)

                # 尝试重连
                if self._reconnect():
                    self.is_online = True
                    continue
                else:
                    # 重连失败，切换到离线模式
                    self._run_with_offline_frames()
                    return

            # 连接正常，重置重连计数
            if self.is_reconnecting:
                self.is_reconnecting = False
                self.reconnect_attempts = 0
                logger.info(f"[{self.camera_id}] 连接已恢复")

            # 调整帧大小
            frame = cv2.resize(frame, (640, 640))

            # 更新缓存
            self.frame_cache.update(self.camera_id, frame)

            # 更新统计
            self.frame_count += 1
            self.last_frame_time = current_time
            self.fps = 1.0 / (current_time - last_time) if current_time > last_time else 0

            # 调用推理回调
            if self.inference_callback:
                self.inference_callback(self.camera_id, frame)

            last_time = current_time

            if self.frame_count % 30 == 0:
                logger.debug(f"[{self.camera_id}] 已处理 {self.frame_count} 帧, FPS: {self.fps:.1f}")

        if self._cap:
            self._cap.release()

    def _run_with_offline_frames(self) -> None:
        """使用离线提示帧运行"""
        logger.info(f"[{self.camera_id}] 进入离线模式，显示离线提示")

        last_time = time.time()
        frame_interval = 1.0  # 每秒更新一次

        while self._running:
            current_time = time.time()

            if current_time - last_time < frame_interval:
                time.sleep(0.1)
                continue

            # 尝试重连
            self.is_reconnecting = True
            reconnecting_frame = self._create_status_frame(
                f"摄像头离线 - 正在重连... ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})",
                is_error=True
            )
            self.frame_cache.update(self.camera_id, reconnecting_frame)
            if self.inference_callback:
                self.inference_callback(self.camera_id, reconnecting_frame)

            # 尝试重连
            if self._reconnect():
                # 重连成功，返回主循环
                self._run()
                return

            last_time = current_time
    
    def _run_with_mock_frames(self) -> None:
        """使用模拟帧运行（当RTSP不可用时）"""
        logger.info(f"[{self.camera_id}] 使用模拟帧模式")

        self.is_online = False
        last_time = time.time()
        frame_interval = 0.1  # 10 FPS

        while self._running:
            current_time = time.time()

            if current_time - last_time < frame_interval:
                time.sleep(0.01)
                continue

            # 生成模拟帧（带离线提示）
            frame = self._create_status_frame("模拟模式 - 无RTSP连接", is_error=False)

            # 更新缓存
            self.frame_cache.update(self.camera_id, frame)

            # 更新统计
            self.frame_count += 1
            self.last_frame_time = current_time

            # 调用推理回调
            if self.inference_callback:
                self.inference_callback(self.camera_id, frame)

            last_time = current_time

            if self.frame_count % 30 == 0:
                logger.debug(f"[{self.camera_id}] 已生成 {self.frame_count} 个模拟帧")

    def _reconnect(self) -> bool:
        """
        重连RTSP流

        Returns:
            重连是否成功
        """
        current_time = time.time()

        # 检查是否超过最大重连次数
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"[{self.camera_id}] 达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
            return False

        # 检查重连间隔
        if current_time - self._last_reconnect_time < self.reconnect_delay:
            time.sleep(self.reconnect_delay - (current_time - self._last_reconnect_time))

        self.reconnect_attempts += 1
        self._last_reconnect_time = time.time()
        self.is_reconnecting = True

        logger.info(f"[{self.camera_id}] 尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})")

        # 释放旧的VideoCapture
        if self._cap:
            self._cap.release()
            self._cap = None

        # 等待一段时间
        time.sleep(1)

        # 尝试重新连接
        self._cap = cv2.VideoCapture(self.rtsp_url)

        if self._cap.isOpened():
            logger.info(f"[{self.camera_id}] 重连成功")
            self.is_online = True
            self.is_reconnecting = False
            self.reconnect_attempts = 0
            return True
        else:
            logger.warning(f"[{self.camera_id}] 重连失败")
            self.is_online = False
            return False


class YOLOInference:
    """YOLO推理器"""
    
    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.45
    ):
        """
        初始化YOLO推理器
        
        Args:
            model_path: 模型路径
            device: 设备 (cuda:0 或 cpu)
            conf_threshold: 置信度阈值
            iou_threshold: IOU阈值
        """
        self.model_path = model_path
        self.device = device
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.model = None
        
        self._load_model()
    
    def _load_model(self) -> None:
        """加载模型"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.model.to(self.device)
            logger.info(f"模型已加载到 {self.device}，类别数: {len(self.model.names)}")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}，使用模拟模式")
            self.model = None
    
    def predict(self, frames: list) -> list:
        """
        批量推理
        
        Args:
            frames: 帧列表
            
        Returns:
            检测结果列表
        """
        if self.model is None:
            return [None] * len(frames)
        
        try:
            results = self.model.predict(
                frames,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
                device=self.device,
            )
            return results
        except Exception as e:
            logger.error(f"推理异常: {e}")
            return [None] * len(frames)


class ResultPublisher:
    """结果推送器"""
    
    def __init__(self):
        """初始化结果推送器"""
        self._callbacks = []
    
    def add_callback(self, callback) -> None:
        """添加回调函数"""
        self._callbacks.append(callback)
    
    def publish(self, camera_id: str, detections: list, frame: np.ndarray) -> None:
        """
        推送检测结果
        
        Args:
            camera_id: 摄像头ID
            detections: 检测结果列表
            frame: 原始帧
        """
        for callback in self._callbacks:
            try:
                callback(camera_id, detections, frame)
            except Exception as e:
                logger.error(f"推送结果失败: {e}")


class CameraService:
    """摄像头服务主类"""

    def __init__(
        self,
        model_path: str = None,
        device: str = "cuda:0",
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.45,
        batch_size: int = 16,
        inference_fps: float = 3.0  # 每秒推理帧数，默认3帧
    ):
        """
        初始化摄像头服务

        Args:
            model_path: YOLO模型路径
            device: 设备
            conf_threshold: 置信度阈值
            iou_threshold: IOU阈值
            batch_size: 批处理大小
            inference_fps: 每秒推理帧数（2-5帧推荐）
        """
        # 配置
        if model_path is None:
            model_path = os.getenv(
                "MODEL_PATH",
                r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt"
            )

        self.batch_size = batch_size
        self.inference_fps = max(1.0, min(10.0, inference_fps))  # 限制在1-10帧之间
        self.inference_interval = 1.0 / self.inference_fps  # 推理间隔时间

        # 组件
        self.frame_cache = FrameCache(max_size=30)
        self.inference = YOLOInference(
            model_path=model_path,
            device=device,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold
        )
        self.publisher = ResultPublisher()

        # 摄像头管理
        self._cameras: Dict[str, CameraWorker] = {}
        self._running = False

        # 推理线程
        self._inference_thread: Optional[threading.Thread] = None
        self._frame_buffer: Dict[str, Tuple[np.ndarray, float]] = {}
        self._last_inference_time: Dict[str, float] = {}  # 每个摄像头的上次推理时间
        self._buffer_lock = threading.Lock()

        # 告警管理器
        self._alert_manager = None
    
    def set_alert_manager(self, alert_manager) -> None:
        """设置告警管理器"""
        self._alert_manager = alert_manager
    
    def add_camera(self, camera_id: str, rtsp_url: str, location: str = "") -> None:
        """
        添加摄像头
        
        Args:
            camera_id: 摄像头ID
            rtsp_url: RTSP流地址
            location: 摄像头位置
        """
        if camera_id in self._cameras:
            logger.warning(f"摄像头 {camera_id} 已存在")
            return
        
        worker = CameraWorker(
            camera_id=camera_id,
            rtsp_url=rtsp_url,
            location=location,
            frame_cache=self.frame_cache,
            inference_callback=self._on_frame_received
        )
        
        self._cameras[camera_id] = worker
        logger.info(f"添加摄像头: {camera_id} ({location})")
    
    def remove_camera(self, camera_id: str) -> None:
        """移除摄像头"""
        if camera_id in self._cameras:
            self._cameras[camera_id].stop()
            del self._cameras[camera_id]
            logger.info(f"移除摄像头: {camera_id}")
    
    def start(self) -> None:
        """启动服务"""
        if self._running:
            logger.warning("服务已在运行")
            return
        
        self._running = True
        
        # 启动推理线程
        self._inference_thread = threading.Thread(
            target=self._inference_loop,
            name="InferenceLoop",
            daemon=True
        )
        self._inference_thread.start()
        logger.info("推理线程已启动")
        
        # 启动所有摄像头
        for camera_id, worker in self._cameras.items():
            worker.start()
        
        logger.info(f"服务已启动，共 {len(self._cameras)} 路摄像头")
    
    def stop(self) -> None:
        """停止服务"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止所有摄像头
        for worker in self._cameras.values():
            worker.stop()
        
        # 等待推理线程结束
        if self._inference_thread:
            self._inference_thread.join(timeout=5)
        
        logger.info("服务已停止")
    
    def _on_frame_received(self, camera_id: str, frame: np.ndarray) -> None:
        """帧接收回调"""
        with self._buffer_lock:
            self._frame_buffer[camera_id] = (frame, time.time())
    
    def _inference_loop(self) -> None:
        """推理主循环（带帧率限制）"""
        logger.info(f"推理循环启动，推理帧率: {self.inference_fps} FPS")

        while self._running:
            current_time = time.time()

            # 收集需要推理的帧（只推理达到推理间隔的摄像头）
            batch_frames = []
            batch_camera_ids = []
            batch_locations = []

            with self._buffer_lock:
                for camera_id, (frame, frame_time) in self._frame_buffer.items():
                    # 检查是否达到推理间隔
                    last_inference = self._last_inference_time.get(camera_id, 0)
                    if current_time - last_inference >= self.inference_interval:
                        batch_frames.append(frame)
                        batch_camera_ids.append(camera_id)
                        # 获取位置信息
                        location = ""
                        if camera_id in self._cameras:
                            location = self._cameras[camera_id].location
                        batch_locations.append(location)

                        # 更新推理时间
                        self._last_inference_time[camera_id] = current_time

                        # 限制批次大小
                        if len(batch_frames) >= self.batch_size:
                            break

            if len(batch_frames) == 0:
                time.sleep(0.01)
                continue

            logger.debug(f"处理批次: {batch_camera_ids}")

            # 执行推理
            results = self.inference.predict(batch_frames)

            # 处理结果
            for i, (camera_id, result) in enumerate(zip(batch_camera_ids, results)):
                detections = []
                annotated_frame = batch_frames[i]

                if result is not None and result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        class_name = self.inference.model.names[class_id] if self.inference.model else f"class_{class_id}"
                        confidence = float(box.conf[0])
                        bbox = tuple(map(int, box.xyxy[0].tolist()))

                        detections.append({
                            "class_name": class_name,
                            "confidence": confidence,
                            "bbox": bbox
                        })

                    # 绘制检测框
                    if hasattr(result, 'plot'):
                        annotated_frame = result.plot()

                # 推送结果到告警管理器
                if self._alert_manager and detections:
                    self._alert_manager.process_detections(
                        camera_id,
                        batch_locations[i],
                        detections
                    )

                # 推送帧到流服务
                self._publish_frame(camera_id, annotated_frame)

                # 调用发布回调
                self.publisher.publish(camera_id, detections, annotated_frame)
    
    def _publish_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """推送帧到流服务"""
        try:
            from backend.routers.stream import update_frame
            update_frame(camera_id, frame)
        except Exception as e:
            logger.debug(f"更新帧失败: {e}")
    
    def get_status(self) -> dict:
        """获取服务状态"""
        camera_stats = {}
        for camera_id, worker in self._cameras.items():
            camera_stats[camera_id] = {
                "location": worker.location,
                "frame_count": worker.frame_count,
                "fps": round(worker.fps, 2),
                "cache_size": self.frame_cache.get_frame_count(camera_id),
                "is_online": worker.is_online,
                "is_reconnecting": worker.is_reconnecting,
                "reconnect_attempts": worker.reconnect_attempts
            }

        return {
            "running": self._running,
            "cameras": camera_stats,
            "total_cameras": len(self._cameras),
            "inference_fps": self.inference_fps
        }


def load_camera_config() -> dict:
    """从数据库或配置文件加载摄像头配置"""
    config = {}
    
    # 尝试从数据库加载
    try:
        from backend.models.database import SessionLocal, Camera
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
            config_path = os.path.join(os.path.dirname(__file__), 'database_only_disabled.json')
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


def main():
    """主函数"""
    import signal
    
    # 加载配置
    camera_config = load_camera_config()
    
    # 创建服务
    service = CameraService()
    
    # 设置告警管理器
    try:
        from backend.engine.alert_manager import AlertManager
        alert_manager = AlertManager()
        service.set_alert_manager(alert_manager)
        logger.info("告警管理器已初始化")
    except Exception as e:
        logger.warning(f"无法初始化告警管理器: {e}")
    
    # 添加摄像头
    for camera_id, config in camera_config.items():
        if config.get("enabled", True):
            service.add_camera(
                camera_id=camera_id,
                rtsp_url=config.get("rtsp_url", ""),
                location=config.get("location", "")
            )
    
    # 信号处理
    def signal_handler(sig, frame):
        logger.info("收到停止信号，正在关闭服务...")
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动服务
    service.start()
    
    logger.info("摄像头服务运行中，按 Ctrl+C 停止...")
    
    # 主循环
    try:
        while True:
            time.sleep(1)
            # 定期打印状态
            status = service.get_status()
            logger.debug(f"服务状态: {status}")
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
