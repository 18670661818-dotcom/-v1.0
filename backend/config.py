"""全局配置文件"""
import os
import secrets
from typing import Dict, Any
from core.config import settings

# ==================== 服务器配置 ====================
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# ==================== 数据库配置 ====================
# 使用SQLite快速启动，生产环境改用PostgreSQL
DATABASE_URL = settings.DATABASE_URL

# ==================== JWT认证配置 ====================
# 安全的 SECRET_KEY 生成
SECRET_KEY = settings.SECRET_KEY

ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# ==================== CORS 配置 ====================
# 生产环境应限制允许的来源
ALLOWED_ORIGINS = settings.ALLOWED_ORIGINS

# ==================== YOLO模型配置 ====================
MODEL_PATH = settings.MODEL_PATH
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", 0.4))
IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", 0.45))

# ==================== 设备配置 ====================
try:
    import torch
    DEVICE = os.getenv("DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")
except ImportError:
    DEVICE = os.getenv("DEVICE", "cpu")
    print("⚠️  PyTorch 未安装，使用 CPU 模式")

# ==================== 推理引擎配置 ====================
SAMPLE_INTERVAL = float(os.getenv("SAMPLE_INTERVAL", 2.0))  # 每路抽帧间隔
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 16))
BATCH_TIMEOUT = float(os.getenv("BATCH_TIMEOUT", 0.1))

# ==================== 告警配置 ====================
ALERT_COOLDOWN_SECONDS: Dict[str, int] = {
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

# 存储告警截图的目录
ALERT_IMAGE_DIR = os.getenv("ALERT_IMAGE_DIR", "alert_images")
os.makedirs(ALERT_IMAGE_DIR, exist_ok=True)

# ==================== 摄像头默认配置 ====================
# 从环境变量或配置文件加载
DEFAULT_CAMERA_CONFIG: Dict[str, Dict[str, Any]] = {
    # 示例配置，实际从数据库加载
}

# 摄像头配置（可从环境变量或配置文件加载）
CAMERA_CONFIG: Dict[str, Dict[str, Any]] = {}
_DISABLED_CAMERA_CONFIG: Dict[str, Dict[str, Any]] = {
    "cam_001": {"rtsp_url": "rtsp://127.0.0.1:8554/kitchen_01", "location": "食堂1号-A区", "enabled": True},
    "cam_002": {"rtsp_url": "rtsp://127.0.0.1:8554/kitchen_02", "location": "食堂1号-B区", "enabled": True},
    "cam_003": {"rtsp_url": "rtsp://127.0.0.1:8554/kitchen_03", "location": "食堂1号-C区", "enabled": True},
}
