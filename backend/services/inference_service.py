"""
推理服务 - 服务层
功能：
1. YOLO模型推理
2. 帧率限制（每秒2-5帧）
3. 批量推理
4. 结果分发
"""
import os
import time
import threading
import logging
import numpy as np
from typing import Dict, Optional, List, Tuple, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """检测结果数据类"""
    camera_id: str
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    timestamp: float


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
        self.class_names = {}

        self._load_model()

    def _load_model(self) -> None:
        """加载模型"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.model.to(self.device)
            self.class_names = self.model.names
            logger.info(f"模型已加载到 {self.device}，类别数: {len(self.class_names)}")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}，使用模拟模式")
            self.model = None

    def predict(self, frames: List[np.ndarray]) -> List[Optional[object]]:
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

    def parse_result(self, result, camera_id: str) -> List[Dict]:
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

        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = self.class_names.get(class_id, f"class_{class_id}")
            confidence = float(box.conf[0])
            bbox = tuple(map(int, box.xyxy[0].tolist()))

            detections.append({
                "camera_id": camera_id,
                "class_name": class_name,
                "confidence": confidence,
                "bbox": bbox,
                "timestamp": time.time()
            })

        return detections


class InferenceService:
    """推理服务主类"""

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
        初始化推理服务

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

        # YOLO推理器
        self.yolo = YOLOInference(
            model_path=model_path,
            device=device,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold
        )

        # 帧缓冲区
        self._frame_buffer: Dict[str, Tuple[np.ndarray, float]] = {}
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

    def set_alert_service(self, alert_service) -> None:
        """设置告警服务"""
        self._alert_service = alert_service

    def add_result_callback(self, callback: Callable) -> None:
        """添加结果回调函数"""
        self._result_callbacks.append(callback)

    def add_frame_callback(self, callback: Callable) -> None:
        """添加帧回调函数（用于推送标注后的帧）"""
        self._frame_callbacks.append(callback)

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

        self._running = True

        # 启动推理线程
        self._inference_thread = threading.Thread(
            target=self._inference_loop,
            name="InferenceLoop",
            daemon=True
        )
        self._inference_thread.start()
        logger.info(f"推理服务已启动，推理帧率: {self.inference_fps} FPS")

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
        logger.info(f"推理循环启动，推理帧率: {self.inference_fps} FPS")

        while self._running:
            current_time = time.time()

            # 收集需要推理的帧（只推理达到推理间隔的摄像头）
            batch_frames = []
            batch_camera_ids = []
            batch_locations = []

            with self._buffer_lock:
                for camera_id, (frame, frame_time, location) in self._frame_buffer.items():
                    # 检查是否达到推理间隔
                    last_inference = self._last_inference_time.get(camera_id, 0)
                    if current_time - last_inference >= self.inference_interval:
                        batch_frames.append(frame)
                        batch_camera_ids.append(camera_id)
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
            results = self.yolo.predict(batch_frames)

            # 处理结果
            for i, (camera_id, result) in enumerate(zip(batch_camera_ids, results)):
                # 解析检测结果
                detections = self.yolo.parse_result(result, camera_id)

                # 获取标注后的帧
                annotated_frame = batch_frames[i]
                if result is not None and hasattr(result, 'plot'):
                    try:
                        annotated_frame = result.plot()
                    except Exception as e:
                        logger.warning(f"绘制标注失败: {e}")

                # 推送到告警服务
                if self._alert_service and detections:
                    try:
                        self._alert_service.process_detections(
                            camera_id,
                            batch_locations[i],
                            detections
                        )
                    except Exception as e:
                        logger.error(f"告警处理失败: {e}")

                # 推送帧到流服务
                self._publish_frame(camera_id, annotated_frame)

                # 调用结果回调
                for callback in self._result_callbacks:
                    try:
                        callback(camera_id, detections, annotated_frame)
                    except Exception as e:
                        logger.error(f"结果回调失败: {e}")

                # 调用帧回调
                for callback in self._frame_callbacks:
                    try:
                        callback(camera_id, annotated_frame)
                    except Exception as e:
                        logger.error(f"帧回调失败: {e}")

    def _publish_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """推送帧到流服务"""
        try:
            from routers.stream import update_frame
            update_frame(camera_id, frame)
        except Exception as e:
            logger.debug(f"更新帧失败: {e}")

    def get_status(self) -> Dict:
        """获取服务状态"""
        return {
            "running": self._running,
            "inference_fps": self.inference_fps,
            "batch_size": self.batch_size,
            "model_loaded": self.yolo.model is not None,
            "device": self.yolo.device,
            "buffered_cameras": list(self._frame_buffer.keys())
        }


# 全局推理服务实例
inference_service = None


def get_inference_service(**kwargs) -> InferenceService:
    """获取推理服务实例（单例模式）"""
    global inference_service
    if inference_service is None:
        inference_service = InferenceService(**kwargs)
    return inference_service
