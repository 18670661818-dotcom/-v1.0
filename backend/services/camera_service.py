"""
摄像头服务 - 服务层
功能：
1. 读取RTSP流
2. 缓存最新帧
3. 帧推送到推理服务
4. 断流自动重连
"""
import os
import time
import threading
import logging
import cv2
import numpy as np
from typing import Dict, Optional, Callable
from collections import deque

logger = logging.getLogger(__name__)


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
        frame_callback: Optional[Callable] = None,
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
            frame_callback: 帧回调函数（推送到推理服务）
            max_reconnect_attempts: 最大重连尝试次数
            reconnect_delay: 重连延迟（秒）
        """
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.location = location
        self.frame_cache = frame_cache
        self.frame_callback = frame_callback
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
                if self.frame_callback:
                    self.frame_callback(self.camera_id, offline_frame)

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

            # 调用帧回调（推送到推理服务）
            if self.frame_callback:
                self.frame_callback(self.camera_id, frame)

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
            if self.frame_callback:
                self.frame_callback(self.camera_id, reconnecting_frame)

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

            # 调用帧回调
            if self.frame_callback:
                self.frame_callback(self.camera_id, frame)

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


class CameraService:
    """摄像头服务主类"""

    def __init__(self):
        """初始化摄像头服务"""
        self.frame_cache = FrameCache(max_size=30)
        self._cameras: Dict[str, CameraWorker] = {}
        self._running = False
        self._frame_callback: Optional[Callable] = None

    def set_frame_callback(self, callback: Callable) -> None:
        """设置帧回调函数（推送到推理服务）"""
        self._frame_callback = callback

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
            frame_callback=self._frame_callback
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

        # 启动所有摄像头
        for camera_id, worker in self._cameras.items():
            worker.start()

        logger.info(f"摄像头服务已启动，共 {len(self._cameras)} 路摄像头")

    def stop(self) -> None:
        """停止服务"""
        if not self._running:
            return

        self._running = False

        # 停止所有摄像头
        for worker in self._cameras.values():
            worker.stop()

        logger.info("摄像头服务已停止")

    def get_camera_status(self, camera_id: str) -> Optional[Dict]:
        """获取摄像头状态"""
        if camera_id not in self._cameras:
            return None

        worker = self._cameras[camera_id]
        return {
            "camera_id": camera_id,
            "location": worker.location,
            "frame_count": worker.frame_count,
            "fps": round(worker.fps, 2),
            "cache_size": self.frame_cache.get_frame_count(camera_id),
            "is_online": worker.is_online,
            "is_reconnecting": worker.is_reconnecting,
            "reconnect_attempts": worker.reconnect_attempts
        }

    def get_all_status(self) -> Dict:
        """获取所有摄像头状态"""
        camera_stats = {}
        for camera_id in self._cameras:
            camera_stats[camera_id] = self.get_camera_status(camera_id)

        return {
            "running": self._running,
            "cameras": camera_stats,
            "total_cameras": len(self._cameras)
        }


# 全局摄像头服务实例
camera_service = CameraService()
