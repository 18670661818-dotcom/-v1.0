"""
批量推理引擎 - 多路帧收集 + 动态批处理 + 结果分发
"""
import time
import threading
import logging
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class BatchInferenceEngine:
    """批量推理引擎"""

    def __init__(self, model_path: str, batch_size: int = 16, device: str = "cuda:0"):
        self.batch_size = batch_size
        self.device = device

        # 加载YOLO模型
        try:
            self.model = YOLO(model_path)
            self.model.to(device)
            logger.info(f"模型已加载到 {device}，类别数: {len(self.model.names)}")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}，使用模拟模式")
            self.model = None

        # 帧缓冲区
        self._frame_buffers = {}
        self._lock = threading.Lock()
        self._running = True

    def submit_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """接收一帧到缓冲区"""
        with self._lock:
            self._frame_buffers[camera_id] = (frame, time.time())

    def inference_loop(self, alert_manager):
        """主推理循环"""
        logger.info("推理循环启动")

        while self._running:
            batch_frames = []
            batch_camera_ids = []

            with self._lock:
                sorted_cams = sorted(
                    self._frame_buffers.items(),
                    key=lambda x: x[1][1]
                )
                selected = sorted_cams[:self.batch_size]

                for cam_id, (frame, ts) in selected:
                    batch_frames.append(frame)
                    batch_camera_ids.append(cam_id)
                    del self._frame_buffers[cam_id]

            if len(batch_frames) == 0:
                time.sleep(0.01)
                continue

            try:
                if self.model:
                    results = self.model.predict(
                        batch_frames,
                        conf=0.4,
                        iou=0.45,
                        verbose=False,
                        device=self.device,
                    )
                else:
                    results = [type('obj', (object,), {'boxes': None})() for _ in batch_frames]

                for i, (cam_id, result) in enumerate(zip(batch_camera_ids, results)):
                    detections = []
                    if result.boxes is not None:
                        for box in result.boxes:
                            class_id = int(box.cls[0])
                            class_name = self.model.names[class_id] if self.model else f"class_{class_id}"
                            confidence = float(box.conf[0])
                            detections.append({
                                "class_name": class_name,
                                "confidence": confidence,
                            })

                    if detections:
                        alert_manager.process_detections(cam_id, "unknown", detections)

                    # 推送检测画面到流服务
                    try:
                        from routers.stream import update_frame
                        annotated = result.plot() if self.model and hasattr(result, 'plot') else batch_frames[i]
                        update_frame(cam_id, annotated)
                    except:
                        pass
            except Exception as e:
                logger.error(f"推理异常: {e}")

    def stop(self):
        """停止推理"""
        self._running = False
        logger.info("推理循环停止")