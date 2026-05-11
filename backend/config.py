"""全局配置文件"""
import os
import secrets
from typing import Dict, Any

# ==================== 服务器配置 ====================
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# ==================== 数据库配置 ====================
# 使用SQLite快速启动，生产环境改用PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///kitchen_ai.db"
)

# ==================== JWT认证配置 ====================
# 安全的 SECRET_KEY 生成
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    print("Warning: SECRET_KEY environment variable not set, using randomly generated key")
    print("Please set SECRET_KEY environment variable to ensure tokens remain valid after restart")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))  # 1小时

# ==================== CORS 配置 ====================
# 生产环境应限制允许的来源
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",")

# ==================== YOLO模型配置 ====================
MODEL_PATH = os.getenv("MODEL_PATH", r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt")
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
CAMERA_CONFIG: Dict[str, Dict[str, Any]] = {
    "cam_001": {"rtsp_url": "rtsp://127.0.0.1:8554/kitchen_01", "location": "食堂1号-A区", "enabled": True},
    "cam_002": {"rtsp_url": "rtsp://127.0.0.1:8554/kitchen_02", "location": "食堂1号-B区", "enabled": True},
    "cam_003": {"rtsp_url": "rtsp://127.0.0.1:8554/kitchen_03", "location": "食堂1号-C区", "enabled": True},
}