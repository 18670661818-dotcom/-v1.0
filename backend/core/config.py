"""
核心配置模块
统一管理系统配置
"""
import os
from typing import List, Dict, Any
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # ==================== 应用配置 ====================
    APP_NAME: str = "后厨智能监测系统"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "基于YOLO的后厨安全智能监测系统"
    DEBUG: bool = False

    # ==================== 服务器配置 ====================
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # ==================== 数据库配置 ====================
    DATABASE_URL: str = "sqlite:///./kitchen_ai.db"
    APP_ENV: str = "dev"
    DETECTION_FPS: float = 3.0

    # ==================== JWT认证配置 ====================
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ==================== CORS 配置 ====================
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173"
    ]

    # ==================== YOLO模型配置 ====================
    MODEL_PATH: str = r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt"
    CONF_THRESHOLD: float = 0.4
    IOU_THRESHOLD: float = 0.45
    DEVICE: str = "cuda:0"

    # ==================== 推理引擎配置 ====================
    SAMPLE_INTERVAL: float = 2.0
    BATCH_SIZE: int = 16
    BATCH_TIMEOUT: float = 0.1
    INFERENCE_FPS: float = 3.0

    # ==================== 告警配置 ====================
    ALERT_COOLDOWN_SECONDS: int = 30
    MAX_ALERTS_PER_HOUR: int = 100

    # ==================== 存储配置 ====================
    ALERT_IMAGE_DIR: str = "storage/alerts"
    LOG_DIR: str = "storage/logs"

    # ==================== WebSocket配置 ====================
    WS_HEARTBEAT_INTERVAL: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __init__(self, **kwargs):
        # 处理 DEBUG 环境变量，将 'release' 视为 false
        import os
        debug_env = os.getenv('DEBUG', 'false')
        if debug_env.lower() == 'release':
            kwargs['DEBUG'] = False
        super().__init__(**kwargs)
        # 自动生成 SECRET_KEY（如果未设置）
        if not self.SECRET_KEY:
            import secrets
            self.SECRET_KEY = secrets.token_urlsafe(32)

        # 自动检测设备
        try:
            import torch
            if not torch.cuda.is_available() and self.DEVICE == "cuda:0":
                self.DEVICE = "cpu"
        except ImportError:
            self.DEVICE = "cpu"

        # 创建必要的目录
        os.makedirs(self.ALERT_IMAGE_DIR, exist_ok=True)
        os.makedirs(self.LOG_DIR, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    return Settings()


# 全局配置实例
settings = get_settings()


# ==================== 告警配置（保持向后兼容） ====================
ALERT_COOLDOWN_RULES: Dict[str, int] = {
    "default": 30,
    "smoke": 15,
    "phone": 15,
    "cockroach": 60,
    "rat": 60,
}

ALERT_MIN_FRAMES: Dict[str, int] = {
    "default": 1,
    "smoke": 2,
    "phone": 2,
}

# 合规行为（不生成告警）
COMPLIANT_BEHAVIORS: Dict[str, str] = {
    "chef_uniform": "穿工作服",
    "chef_hat": "戴厨师帽",
    "with_mask": "佩戴口罩",
}
