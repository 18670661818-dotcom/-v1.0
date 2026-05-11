# 后厨智能监测系统 - 后端架构

## 目录结构

```
backend/
├── api/                    # API 路由层
│   ├── health_api.py      # 健康检查接口
│   ├── camera_api.py      # 摄像头管理接口
│   ├── alert_api.py       # 告警管理接口
│   └── ws_api.py          # WebSocket 接口
│
├── services/              # 服务层（业务逻辑）
│   ├── camera_service.py  # 摄像头服务
│   ├── inference_service.py # 推理服务
│   ├── alert_service.py   # 告警服务
│   ├── websocket_service.py # WebSocket 服务
│   └── main.py            # 服务管理入口
│
├── core/                  # 核心模块
│   ├── config.py          # 配置管理
│   ├── logger.py          # 日志管理
│   └── security.py        # 安全认证
│
├── models/                # 数据模型
│   ├── database.py        # 数据库模型
│   └── schemas.py         # Pydantic 模式
│
├── routers/               # 旧路由（兼容层）
│   ├── auth.py
│   ├── cameras.py
│   ├── alerts.py
│   └── ...
│
├── engine/                # 推理引擎
│   └── detector.py        # YOLO 检测器
│
├── storage/               # 存储目录
│   ├── alerts/            # 告警图像
│   └── logs/              # 日志文件
│
├── utils/                 # 工具函数
│
├── main.py                # FastAPI 主入口
├── config.py              # 旧配置（兼容层）
├── requirements.txt       # 依赖列表
└── kitchen_ai.db          # SQLite 数据库
```

## 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│                          API Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Health   │  │  Camera  │  │  Alert   │  │   WS     │   │
│  │   API     │  │   API    │  │   API    │  │   API    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│                        Service Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Camera   │→│ Inference │→│  Alert   │→│   WS     │   │
│  │  Service  │  │  Service │  │  Service │  │  Service │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│                         Core Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Config   │  │  Logger  │  │ Security │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
├─────────────────────────────────────────────────────────────┤
│                       Storage Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  SQLite   │  │  Images  │  │   Logs   │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 数据流

```
RTSP Camera
    │
    ▼
┌─────────────┐    Frame     ┌─────────────┐
│   Camera    │────────────→│  Inference  │
│   Service   │             │   Service   │
└─────────────┘             └──────┬──────┘
                                   │
                                   │ Detection
                                   ▼
                            ┌─────────────┐
                            │   Alert     │
                            │   Service   │
                            └──────┬──────┘
                                   │
                                   │ Notification
                                   ▼
                            ┌─────────────┐
                            │   WebSocket │
                            │   Service   │
                            └──────┬──────┘
                                   │
                                   ▼
                              Frontend
```

## API 端点

### 健康检查
- `GET /health` - 基本健康检查
- `GET /health/detailed` - 详细健康检查
- `GET /health/ready` - 就绪检查
- `GET /health/live` - 存活检查

### 摄像头管理
- `GET /api/cameras` - 获取摄像头列表
- `GET /api/cameras/status` - 获取所有摄像头状态
- `GET /api/cameras/{id}` - 获取单个摄像头
- `POST /api/cameras` - 创建摄像头
- `PUT /api/cameras/{id}` - 更新摄像头
- `DELETE /api/cameras/{id}` - 删除摄像头
- `POST /api/cameras/{id}/restart` - 重启摄像头

### 告警管理
- `GET /api/alerts` - 获取告警列表
- `GET /api/alerts/stats` - 获取告警统计
- `GET /api/alerts/{id}` - 获取单个告警
- `PUT /api/alerts/{id}/status` - 更新告警状态
- `DELETE /api/alerts/{id}` - 删除告警
- `POST /api/alerts/batch-delete` - 批量删除告警
- `GET /api/alerts/today/count` - 获取今日告警数量

### WebSocket
- `WS /ws/{user_id}` - 用户 WebSocket 连接
- `WS /ws/camera/{camera_id}` - 摄像头流 WebSocket
- `GET /ws/stats` - WebSocket 连接统计

## 启动方式

### 方式一：启动所有服务（推荐）
```bash
cd backend
python main.py
```

### 方式二：启动服务层
```bash
cd backend
python -m services.main
```

### 方式三：启动单个服务
```bash
# 只启动摄像头服务
python -m services.main --service camera

# 只启动推理服务
python -m services.main --service inference --fps 3.0
```

## 配置

配置通过 `core/config.py` 管理，支持环境变量和 `.env` 文件。

### 主要配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite:///kitchen_ai.db` | 数据库连接 |
| `MODEL_PATH` | - | YOLO 模型路径 |
| `CONF_THRESHOLD` | `0.4` | 置信度阈值 |
| `IOU_THRESHOLD` | `0.45` | IoU 阈值 |
| `DEVICE` | `cuda:0` | 推理设备 |
| `INFERENCE_FPS` | `3.0` | 推理帧率 |
| `ALERT_COOLDOWN_SECONDS` | `30` | 告警冷却时间 |
| `SERVER_HOST` | `0.0.0.0` | 服务器地址 |
| `SERVER_PORT` | `8000` | 服务器端口 |

## 日志

日志通过 `core/logger.py` 管理，支持：
- 控制台输出
- 文件输出（`storage/logs/app.log`）
- 错误日志（`storage/logs/error.log`）

日志级别：`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
