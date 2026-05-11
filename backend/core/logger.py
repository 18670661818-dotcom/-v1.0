"""
日志模块
统一日志配置和管理
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional
from datetime import datetime


class LoggerManager:
    """日志管理器"""

    def __init__(
        self,
        log_dir: str = "storage/logs",
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        self.log_dir = log_dir
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)

        # 配置根日志器
        self._setup_root_logger()

    def _setup_root_logger(self):
        """配置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # 清除现有处理器
        root_logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # 文件处理器 - 所有日志
        all_log_file = os.path.join(self.log_dir, "app.log")
        file_handler = RotatingFileHandler(
            all_log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # 错误日志处理器
        error_log_file = os.path.join(self.log_dir, "error.log")
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        return logging.getLogger(name)

    def set_level(self, level: str):
        """设置日志级别"""
        new_level = getattr(logging.level.upper(), logging.INFO)
        logging.getLogger().setLevel(new_level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(new_level)


# 全局日志管理器实例
logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """获取日志器的便捷函数"""
    return logger_manager.get_logger(name)


# 预定义的日志器
app_logger = get_logger("app")
api_logger = get_logger("api")
service_logger = get_logger("service")
camera_logger = get_logger("camera")
inference_logger = get_logger("inference")
alert_logger = get_logger("alert")
websocket_logger = get_logger("websocket")


class RequestLogger:
    """请求日志记录器"""

    @staticmethod
    def log_request(method: str, path: str, client_ip: str, status_code: int, duration: float):
        """记录HTTP请求日志"""
        api_logger.info(
            f"{method} {path} - IP: {client_ip} - Status: {status_code} - Duration: {duration:.3f}s"
        )

    @staticmethod
    def log_error(method: str, path: str, client_ip: str, error: str):
        """记录请求错误日志"""
        api_logger.error(
            f"{method} {path} - IP: {client_ip} - Error: {error}"
        )


class CameraLogger:
    """摄像头日志记录器"""

    @staticmethod
    def log_connect(camera_id: str, rtsp_url: str):
        camera_logger.info(f"[{camera_id}] 连接RTSP: {rtsp_url}")

    @staticmethod
    def log_disconnect(camera_id: str, reason: str):
        camera_logger.warning(f"[{camera_id}] 断开连接: {reason}")

    @staticmethod
    def log_reconnect(camera_id: str, attempt: int, max_attempts: int):
        camera_logger.info(f"[{camera_id}] 尝试重连 ({attempt}/{max_attempts})")

    @staticmethod
    def log_frame(camera_id: str, frame_count: int, fps: float):
        camera_logger.debug(f"[{camera_id}] 已处理 {frame_count} 帧, FPS: {fps:.1f}")


class InferenceLogger:
    """推理日志记录器"""

    @staticmethod
    def log_batch(batch_ids: list, batch_size: int):
        inference_logger.debug(f"处理批次: {batch_ids}, 大小: {batch_size}")

    @staticmethod
    def log_detection(camera_id: str, detections: list):
        if detections:
            inference_logger.info(f"[{camera_id}] 检测到 {len(detections)} 个对象")

    @staticmethod
    def log_error(camera_id: str, error: str):
        inference_logger.error(f"[{camera_id}] 推理错误: {error}")


class AlertLogger:
    """告警日志记录器"""

    @staticmethod
    def log_alert(camera_id: str, alert_type: str, confidence: float):
        alert_logger.warning(f"ALERT | {camera_id} | {alert_type} | conf={confidence:.2f}")

    @staticmethod
    def log_cooldown(camera_id: str, alert_type: str):
        alert_logger.debug(f"[{camera_id}] 告警冷却中: {alert_type}")
