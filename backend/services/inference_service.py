"""
推理服务 - 服务层
功能：
1. YOLO模型推理（模型只加载一次）
2. 帧率限制（每秒2-5帧）
3. 批量推理
4. 结果分发
5. 类别过滤
6. 异常隔离
"""
import os
import time
import threading
import logging
import numpy as np
from typing import Dict, Optional, List, Tuple, Callable, Set
from dataclasses import dataclass, field
from queue import Queue, Empty
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """检测结果数据类"""
    camera_id: str
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    timestamp: float


@dataclass
class InferenceConfig:
    """推理配置"""
    model_path: str
    device: str = "auto"  # auto, cuda:0, cpu
    conf_threshold: float = 0.4
    iou_threshold: float = 0.45
    inference_fps: float = 3.0  # 每秒推理帧数（2-5帧推荐）
    batch_size: int = 16
    enabled_classes: Set[str] = field(default_factory=set)  # 空集合表示所有类别
    excluded_classes: Set[str] = field(default_factory=set)  # 排除的类别

    def __post_init__(self):
        # 限制FPS在2-5之间
        self.inference_fps = max(2.0, min(5.0, self.inference_fps))
        # 自动检测设备
        if self.device == "auto":
            self.device = self._detect_device()

    @classmethod
    def from_json(cls, config_path: str) -> 'InferenceConfig':
        """
        从JSON配置文件加载

        Args:
            config_path: 配置文件路径

        Returns:
            InferenceConfig: 配置对象
        """
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        return cls(
            model_path=config_data.get('model_path', ''),
            device=config_data.get('device', 'auto'),
            conf_threshold=config_data.get('conf_threshold', 0.4),
            iou_threshold=config_data.get('iou_threshold', 0.45),
            inference_fps=config_data.get('inference_fps', 3.0),
            batch_size=config_data.get('batch_size', 16),
            enabled_classes=set(config_data.get('enabled_classes', [])),
            excluded_classes=set(config_data.get('excluded_classes', []))
        )

    def _detect_device(self) -> str:
        """自动检测最佳设备"""
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                logger.info(f"检测到GPU: {device_name}")
                return "cuda:0"
            else:
                logger.info("未检测到GPU，使用CPU")
                return "cpu"
        except ImportError:
            logger.warning("PyTorch未安装，使用CPU")
            return "cpu"


class ModelManager:
    """模型管理器（单例模式）"""

    _instance = None
    _lock = threading.Lock()
    _model = None
    _model_path = None
    _device = None
    _class_names = {}

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load_model(self, model_path: str, device: str) -> bool:
        """
        加载模型（只加载一次）

        Args:
            model_path: 模型路径
            device: 设备

        Returns:
            bool: 是否加载成功
        """
        with self._lock:
            # 如果模型已加载且路径和设备相同，直接返回
            if (self._model is not None and
                self._model_path == model_path and
                self._device == device):
                logger.info("模型已加载，复用现有模型")
                return True

            # 加载新模型
            try:
                from ultralytics import YOLO
                logger.info(f"正在加载模型: {model_path}")
                self._model = YOLO(model_path)
                self._model.to(device)
                self._model_path = model_path
                self._device = device
                self._class_names = self._model.names
                logger.info(f"模型加载成功，设备: {device}，类别数: {len(self._class_names)}")
                return True
            except Exception as e:
                logger.error(f"模型加载失败: {e}")
                self._model = None
                return False

    @property
    def model(self):
        """获取模型"""
        return self._model

    @property
    def class_names(self) -> Dict[int, str]:
        """获取类别名称"""
        return self._class_names

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._model is not None

    def get_class_id(self, class_name: str) -> Optional[int]:
        """根据类别名称获取类别ID"""
        for cid, cname in self._class_names.items():
            if cname == class_name:
                return cid
        return None


class InferenceService:
    """推理服务主类"""

    def __init__(self, config: Optional[InferenceConfig] = None):
        """
        初始化推理服务

        Args:
            config: 推理配置
        """
        # 配置
        if config is None:
            config = InferenceConfig(
                model_path=os.getenv(
                    "MODEL_PATH",
                    r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt"
                )
            )
        self.config = config

        # 模型管理器（单例）
        self.model_manager = ModelManager.get_instance()

        # 帧缓冲区：camera_id -> (frame, timestamp, location)
        self._frame_buffer: Dict[str, Tuple[np.ndarray, float, str]] = {}
        self._last_inference_time: Dict[str, float] = {}
        self._buffer_lock = threading.Lock()

        # 线程控制
        self._running = False
        self._inference_thread: Optional[threading.Thread] = None

        # 回调函数
        self._result_callbacks: List[Callable] = []
        self._frame_callbacks: List[Callable] = []

        # 告警服务
        self._alert_service = None

        # 统计信息
        self._stats = {
            "total_inferences": 0,
            "total_detections": 0,
            "errors": 0,
            "last_error": None
        }
        self._stats_lock = threading.Lock()

    def set_alert_service(self, alert_service) -> None:
        """设置告警服务"""
        self._alert_service = alert_service

    def add_result_callback(self, callback: Callable) -> None:
        """添加结果回调函数"""
        self._result_callbacks.append(callback)

    def add_frame_callback(self, callback: Callable) -> None:
        """添加帧回调函数（用于推送标注后的帧）"""
        self._frame_callbacks.append(callback)

    def initialize(self) -> bool:
        """
        初始化模型

        Returns:
            bool: 是否初始化成功
        """
        return self.model_manager.load_model(
            self.config.model_path,
            self.config.device
        )

    def submit_frame(self, camera_id: str, frame: np.ndarray, location: str = "") -> None:
        """
        提交帧进行推理

        Args:
            camera_id: 摄像头ID
            frame: 帧数据
            location: 摄像头位置
        """
        with self._buffer_lock:
            self._frame_buffer[camera_id] = (frame, time.time(), location)

    def start(self) -> None:
        """启动推理服务"""
        if self._running:
            logger.warning("推理服务已在运行")
            return

        # 初始化模型
        if not self.initialize():
            logger.error("模型初始化失败，推理服务无法启动")
            return

        self._running = True

        # 启动推理线程
        self._inference_thread = threading.Thread(
            target=self._inference_loop,
            name="InferenceLoop",
            daemon=True
        )
        self._inference_thread.start()
        logger.info(f"推理服务已启动，推理帧率: {self.config.inference_fps} FPS，设备: {self.config.device}")

    def stop(self) -> None:
        """停止推理服务"""
        if not self._running:
            return

        self._running = False

        if self._inference_thread:
            self._inference_thread.join(timeout=5)

        logger.info("推理服务已停止")

    def _inference_loop(self) -> None:
        """推理主循环（带帧率限制）"""
        logger.info(f"推理循环启动，推理帧率: {self.config.inference_fps} FPS")
        inference_interval = 1.0 / self.config.inference_fps

        while self._running:
            try:
                current_time = time.time()

                # 收集需要推理的帧（只推理达到推理间隔的摄像头）
                batch_frames = []
                batch_camera_ids = []
                batch_locations = []

                with self._buffer_lock:
                    for camera_id, (frame, frame_time, location) in self._frame_buffer.items():
                        # 检查是否达到推理间隔
                        last_inference = self._last_inference_time.get(camera_id, 0)
                        if current_time - last_inference >= inference_interval:
                            batch_frames.append(frame)
                            batch_camera_ids.append(camera_id)
                            batch_locations.append(location)

                            # 更新推理时间
                            self._last_inference_time[camera_id] = current_time

                            # 限制批次大小
                            if len(batch_frames) >= self.config.batch_size:
                                break

                if len(batch_frames) == 0:
                    time.sleep(0.01)
                    continue

                logger.debug(f"处理批次: {batch_camera_ids}")

                # 执行推理（异常隔离）
                self._process_batch(batch_frames, batch_camera_ids, batch_locations)

            except Exception as e:
                logger.error(f"推理循环异常: {e}")
                with self._stats_lock:
                    self._stats["errors"] += 1
                    self._stats["last_error"] = str(e)
                time.sleep(0.1)  # 异常后短暂休眠

    @contextmanager
    def _error_isolation(self):
        """异常隔离上下文管理器"""
        try:
            yield
        except Exception as e:
            logger.error(f"推理异常（已隔离）: {e}")
            with self._stats_lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)

    def _process_batch(
        self,
        frames: List[np.ndarray],
        camera_ids: List[str],
        locations: List[str]
    ) -> None:
        """
        处理批次推理

        Args:
            frames: 帧列表
            camera_ids: 摄像头ID列表
            locations: 位置列表
        """
        with self._error_isolation():
            # 执行推理
            results = self._predict(frames)

            # 处理结果
            for i, (camera_id, result) in enumerate(zip(camera_ids, results)):
                with self._error_isolation():
                    # 解析检测结果
                    detections = self._parse_result(result, camera_id)

                    # 类别过滤
                    detections = self._filter_detections(detections)

                    # 更新统计
                    with self._stats_lock:
                        self._stats["total_inferences"] += 1
                        self._stats["total_detections"] += len(detections)

                    # 获取标注后的帧
                    annotated_frame = self._get_annotated_frame(result, frames[i])

                    # 推送到告警服务
                    if self._alert_service and detections:
                        with self._error_isolation():
                            if hasattr(self._alert_service, 'process_detections'):
                                self._alert_service.process_detections(
                                    camera_id,
                                    locations[i],
                                    detections
                                )

                    # 推送帧到流服务
                    self._publish_frame(camera_id, annotated_frame)

                    # 调用结果回调
                    for callback in self._result_callbacks:
                        with self._error_isolation():
                            callback(camera_id, detections, annotated_frame)

                    # 调用帧回调
                    for callback in self._frame_callbacks:
                        with self._error_isolation():
                            callback(camera_id, annotated_frame)

    def _predict(self, frames: List[np.ndarray]) -> List[Optional[object]]:
        """
        批量推理

        Args:
            frames: 帧列表

        Returns:
            检测结果列表
        """
        model = self.model_manager.model
        if model is None:
            return [None] * len(frames)

        try:
            results = model.predict(
                frames,
                conf=self.config.conf_threshold,
                iou=self.config.iou_threshold,
                verbose=False,
                device=self.config.device,
            )
            return results
        except Exception as e:
            logger.error(f"推理异常: {e}")
            return [None] * len(frames)

    def _parse_result(self, result, camera_id: str) -> List[Dict]:
        """
        解析推理结果

        Args:
            result: YOLO推理结果
            camera_id: 摄像头ID

        Returns:
            检测结果字典列表
        """
        detections = []

        if result is None or result.boxes is None:
            return detections

        class_names = self.model_manager.class_names

        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = class_names.get(class_id, f"class_{class_id}")
            confidence = float(box.conf[0])
            bbox = tuple(map(int, box.xyxy[0].tolist()))

            detections.append({
                "camera_id": camera_id,
                "class_id": class_id,
                "class_name": class_name,
                "confidence": confidence,
                "bbox": bbox,
                "timestamp": time.time()
            })

        return detections

    def _filter_detections(self, detections: List[Dict]) -> List[Dict]:
        """
        过滤检测结果

        Args:
            detections: 检测结果列表

        Returns:
            过滤后的检测结果列表
        """
        if not detections:
            return detections

        filtered = []

        for det in detections:
            class_name = det["class_name"]

            # 如果指定了启用的类别，只保留这些类别
            if self.config.enabled_classes:
                if class_name not in self.config.enabled_classes:
                    continue

            # 如果指定了排除的类别，排除这些类别
            if self.config.excluded_classes:
                if class_name in self.config.excluded_classes:
                    continue

            filtered.append(det)

        return filtered

    def _get_annotated_frame(self, result, original_frame: np.ndarray) -> np.ndarray:
        """
        获取标注后的帧

        Args:
            result: YOLO推理结果
            original_frame: 原始帧

        Returns:
            标注后的帧
        """
        if result is not None and hasattr(result, 'plot'):
            try:
                return result.plot()
            except Exception as e:
                logger.warning(f"绘制标注失败: {e}")
        return original_frame

    def _publish_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """推送帧到流服务"""
        try:
            from routers.stream import update_frame
            update_frame(camera_id, frame)
        except Exception as e:
            logger.debug(f"更新帧失败: {e}")

    def get_status(self) -> Dict:
        """获取服务状态"""
        with self._stats_lock:
            stats = self._stats.copy()

        return {
            "running": self._running,
            "model_loaded": self.model_manager.is_loaded,
            "device": self.config.device,
            "inference_fps": self.config.inference_fps,
            "conf_threshold": self.config.conf_threshold,
            "iou_threshold": self.config.iou_threshold,
            "enabled_classes": list(self.config.enabled_classes),
            "excluded_classes": list(self.config.excluded_classes),
            "buffered_cameras": list(self._frame_buffer.keys()),
            "stats": stats
        }

    def update_config(self, **kwargs) -> None:
        """
        更新配置

        Args:
            **kwargs: 配置参数
        """
        if "conf_threshold" in kwargs:
            self.config.conf_threshold = max(0.1, min(1.0, kwargs["conf_threshold"]))
            logger.info(f"更新置信度阈值: {self.config.conf_threshold}")

        if "iou_threshold" in kwargs:
            self.config.iou_threshold = max(0.1, min(1.0, kwargs["iou_threshold"]))
            logger.info(f"更新IOU阈值: {self.config.iou_threshold}")

        if "inference_fps" in kwargs:
            self.config.inference_fps = max(2.0, min(5.0, kwargs["inference_fps"]))
            logger.info(f"更新推理帧率: {self.config.inference_fps} FPS")

        if "enabled_classes" in kwargs:
            self.config.enabled_classes = set(kwargs["enabled_classes"])
            logger.info(f"更新启用类别: {self.config.enabled_classes}")

        if "excluded_classes" in kwargs:
            self.config.excluded_classes = set(kwargs["excluded_classes"])
            logger.info(f"更新排除类别: {self.config.excluded_classes}")


# 全局推理服务实例
_inference_service: Optional[InferenceService] = None
_service_lock = threading.Lock()


def get_inference_service(**kwargs) -> InferenceService:
    """
    获取推理服务实例（单例模式）

    Args:
        **kwargs: 配置参数

    Returns:
        InferenceService: 推理服务实例
    """
    global _inference_service

    if _inference_service is None:
        with _service_lock:
            if _inference_service is None:
                config = InferenceConfig(**kwargs) if kwargs else None
                _inference_service = InferenceService(config)

    return _inference_service
