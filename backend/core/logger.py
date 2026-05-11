"""
日志模块
统一日志配置和管理

支持：
- 按文件输出（backend.log, camera.log, inference.log, alert.log, error.log）
- 按日期滚动（每天一个日志文件）
- 控制台输出
- 错误日志单独记录
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from typing import Optional
from datetime import datetime
from pathlib import Path


class LoggerManager:
    """日志管理器"""

    def __init__(
        self,
        log_dir: str = "storage/logs",
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 30,  # 保留30天的日志
        use_timed_rotation: bool = True  # 使用按日期滚动
    ):
        self.log_dir = os.path.abspath(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.use_timed_rotation = use_timed_rotation

        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)

        # 日志格式
        self.console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 配置各个模块的日志器
        self._setup_loggers()

    def _create_file_handler(
        self,
        filename: str,
        level: int = None,
        formatter: logging.Formatter = None
    ) -> logging.Handler:
        """创建文件处理器"""
        filepath = os.path.join(self.log_dir, filename)

        if self.use_timed_rotation:
            # 按日期滚动：每天一个文件
            handler = TimedRotatingFileHandler(
                filepath,
                when='midnight',  # 每天午夜滚动
                interval=1,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            handler.suffix = "%Y-%m-%d"  # 日志文件后缀格式
        else:
            # 按大小滚动
            handler = RotatingFileHandler(
                filepath,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )

        handler.setLevel(level or self.log_level)
        handler.setFormatter(formatter or self.file_format)

        return handler

    def _setup_loggers(self):
        """配置各个模块的日志器"""
        # 1. 根日志器 - 控制台输出
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        root_logger.handlers.clear()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(self.console_format)
        root_logger.addHandler(console_handler)

        # 2. 后端主日志器
        self._setup_module_logger(
            "backend",
            "backend.log",
            self.log_level
        )

        # 3. 摄像头日志器
        self._setup_module_logger(
            "camera",
            "camera.log",
            self.log_level
        )

        # 4. 推理日志器
        self._setup_module_logger(
            "inference",
            "inference.log",
            self.log_level
        )

        # 5. 告警日志器
        self._setup_module_logger(
            "alert",
            "alert.log",
            self.log_level
        )

        # 6. 错误日志器 - 只记录ERROR及以上级别
        self._setup_module_logger(
            "error",
            "error.log",
            logging.ERROR,
            propagate=False  # 错误日志不传播到根日志器，避免重复
        )

        # 7. WebSocket日志器
        self._setup_module_logger(
            "websocket",
            "websocket.log",
            self.log_level
        )

        # 8. API日志器
        self._setup_module_logger(
            "api",
            "api.log",
            self.log_level
        )

    def _setup_module_logger(
        self,
        name: str,
        filename: str,
        level: int,
        propagate: bool = True
    ):
        """配置模块日志器"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = propagate

        # 添加文件处理器
        file_handler = self._create_file_handler(filename, level)
        logger.addHandler(file_handler)

        # 如果是错误日志，还需要添加到根日志器，以便捕获所有模块的错误
        if name == "error":
            root_logger = logging.getLogger()
            error_handler = self._create_file_handler(filename, logging.ERROR)
            root_logger.addHandler(error_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        return logging.getLogger(name)

    def set_level(self, level: str):
        """设置日志级别"""
        new_level = getattr(logging, level.upper(), logging.INFO)
        self.log_level = new_level
        logging.getLogger().setLevel(new_level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(new_level)


# 全局日志管理器实例
logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """获取日志器的便捷函数"""
    return logger_manager.get_logger(name)


# 预定义的日志器
app_logger = get_logger("backend")
api_logger = get_logger("api")
service_logger = get_logger("backend")
camera_logger = get_logger("camera")
inference_logger = get_logger("inference")
alert_logger = get_logger("alert")
websocket_logger = get_logger("websocket")
error_logger = get_logger("error")


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
        """摄像头连接成功"""
        camera_logger.info(f"[{camera_id}] 连接成功: {rtsp_url}")

    @staticmethod
    def log_disconnect(camera_id: str, reason: str):
        """摄像头断线"""
        camera_logger.warning(f"[{camera_id}] 断开连接: {reason}")

    @staticmethod
    def log_reconnect(camera_id: str, attempt: int, max_attempts: int):
        """摄像头重连"""
        camera_logger.info(f"[{camera_id}] 尝试重连 ({attempt}/{max_attempts})")

    @staticmethod
    def log_reconnect_success(camera_id: str):
        """摄像头重连成功"""
        camera_logger.info(f"[{camera_id}] 重连成功")

    @staticmethod
    def log_reconnect_failed(camera_id: str, reason: str):
        """摄像头重连失败"""
        camera_logger.error(f"[{camera_id}] 重连失败: {reason}")

    @staticmethod
    def log_frame(camera_id: str, frame_count: int, fps: float):
        """记录帧处理"""
        camera_logger.debug(f"[{camera_id}] 已处理 {frame_count} 帧, FPS: {fps:.1f}")

    @staticmethod
    def log_error(camera_id: str, error: str):
        """摄像头错误"""
        camera_logger.error(f"[{camera_id}] 错误: {error}")


class InferenceLogger:
    """推理日志记录器"""

    @staticmethod
    def log_start(camera_id: str, model_name: str):
        """推理开始"""
        inference_logger.info(f"[{camera_id}] 开始推理 - 模型: {model_name}")

    @staticmethod
    def log_stop(camera_id: str):
        """推理停止"""
        inference_logger.info(f"[{camera_id}] 停止推理")

    @staticmethod
    def log_batch(camera_id: str, batch_size: int, duration: float):
        """处理批次"""
        inference_logger.debug(
            f"[{camera_id}] 处理批次 - 大小: {batch_size}, 耗时: {duration:.3f}s"
        )

    @staticmethod
    def log_detection(camera_id: str, detections: list):
        """检测结果"""
        if detections:
            detection_summary = {}
            for det in detections:
                class_name = det.get("class_name", "unknown")
                detection_summary[class_name] = detection_summary.get(class_name, 0) + 1
            inference_logger.info(
                f"[{camera_id}] 检测到 {len(detections)} 个对象: {detection_summary}"
            )

    @staticmethod
    def log_error(camera_id: str, error: str):
        """推理异常"""
        inference_logger.error(f"[{camera_id}] 推理异常: {error}")
        error_logger.error(f"Inference error [{camera_id}]: {error}")

    @staticmethod
    def log_model_load(model_path: str, success: bool, duration: float = 0):
        """模型加载"""
        if success:
            inference_logger.info(f"模型加载成功: {model_path} (耗时: {duration:.2f}s)")
        else:
            inference_logger.error(f"模型加载失败: {model_path}")
            error_logger.error(f"Model load failed: {model_path}")


class AlertLogger:
    """告警日志记录器"""

    @staticmethod
    def log_alert(camera_id: str, alert_type: str, confidence: float, alert_id: str = None):
        """告警生成"""
        msg = f"告警生成 | 摄像头: {camera_id} | 类型: {alert_type} | 置信度: {confidence:.2f}"
        if alert_id:
            msg += f" | ID: {alert_id}"
        alert_logger.warning(msg)

    @staticmethod
    def log_confirm(alert_id: int, handled_by: str = None):
        """告警确认"""
        msg = f"告警确认 | ID: {alert_id}"
        if handled_by:
            msg += f" | 处理人: {handled_by}"
        alert_logger.info(msg)

    @staticmethod
    def log_resolve(alert_id: int, handled_by: str = None):
        """告警解决"""
        msg = f"告警解决 | ID: {alert_id}"
        if handled_by:
            msg += f" | 处理人: {handled_by}"
        alert_logger.info(msg)

    @staticmethod
    def log_false_positive(alert_id: int, handled_by: str = None):
        """标记误报"""
        msg = f"告警标记为误报 | ID: {alert_id}"
        if handled_by:
            msg += f" | 处理人: {handled_by}"
        alert_logger.info(msg)

    @staticmethod
    def log_cooldown(camera_id: str, alert_type: str):
        """告警冷却"""
        alert_logger.debug(f"[{camera_id}] 告警冷却中: {alert_type}")

    @staticmethod
    def log_suppressed(camera_id: str, alert_type: str, reason: str):
        """告警被抑制"""
        alert_logger.debug(f"[{camera_id}] 告警被抑制: {alert_type} - 原因: {reason}")


class WebSocketLogger:
    """WebSocket日志记录器"""

    @staticmethod
    def log_connect(client_id: str, client_ip: str = None):
        """WebSocket连接"""
        msg = f"WebSocket连接 | 客户端: {client_id}"
        if client_ip:
            msg += f" | IP: {client_ip}"
        websocket_logger.info(msg)

    @staticmethod
    def log_disconnect(client_id: str, reason: str = None):
        """WebSocket断开"""
        msg = f"WebSocket断开 | 客户端: {client_id}"
        if reason:
            msg += f" | 原因: {reason}"
        websocket_logger.info(msg)

    @staticmethod
    def log_message(client_id: str, message_type: str):
        """WebSocket消息"""
        websocket_logger.debug(f"WebSocket消息 | 客户端: {client_id} | 类型: {message_type}")

    @staticmethod
    def log_error(client_id: str, error: str):
        """WebSocket错误"""
        websocket_logger.error(f"WebSocket错误 | 客户端: {client_id} | 错误: {error}")


class DatabaseLogger:
    """数据库日志记录器"""

    @staticmethod
    def log_error(operation: str, error: str):
        """数据库异常"""
        error_logger.error(f"数据库异常 | 操作: {operation} | 错误: {error}")

    @staticmethod
    def log_connection_error(error: str):
        """数据库连接异常"""
        error_logger.error(f"数据库连接异常: {error}")

    @staticmethod
    def log_migration(version: str, success: bool):
        """数据库迁移"""
        if success:
            app_logger.info(f"数据库迁移成功: {version}")
        else:
            error_logger.error(f"数据库迁移失败: {version}")


# 便捷的日志记录实例
request_logger = RequestLogger()
camera_log = CameraLogger()
inference_log = InferenceLogger()
alert_log = AlertLogger()
websocket_log = WebSocketLogger()
database_log = DatabaseLogger()
