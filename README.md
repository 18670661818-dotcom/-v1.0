# Kitchen AI System

厨房AI监控系统 - 基于深度学习的厨房安全监控解决方案

## 📋 项目简介

Kitchen AI System 是一个完整的厨房安全监控系统，通过AI推理引擎实时分析摄像头视频流，检测潜在的安全隐患（如火灾、烟雾、刀具、液体泄漏等），并及时发出告警。

## 🚀 主要功能

- **实时监控**: 支持多路摄像头同时监控
- **AI检测**: 基于深度学习的物体检测
- **智能告警**: 多级告警机制（低、中、高、严重）
- **Web界面**: 现代化的React前端界面
- **RESTful API**: 完整的后端API接口
- **WebSocket**: 实时数据推送
- **用户认证**: JWT令牌认证
- **数据统计**: 仪表盘数据可视化

## 🏗️ 项目结构

```
kitchen_ai_system/
├── backend/                    # Python后端
│   ├── main.py                # FastAPI主入口
│   ├── config.py              # 配置文件
│   ├── requirements.txt       # Python依赖
│   ├── models/                # 数据模型
│   │   ├── database.py        # SQLAlchemy模型
│   │   └── schemas.py         # Pydantic模式
│   ├── routers/               # API路由
│   │   ├── auth.py            # 认证路由
│   │   ├── cameras.py         # 摄像头管理
│   │   ├── alerts.py          # 告警管理
│   │   └── dashboard.py       # 仪表盘
│   ├── services/              # 业务逻辑
│   │   ├── inference_service.py
│   │   └── alert_service.py
│   ├── engine/                # 推理引擎
│   │   ├── inference_engine.py
│   │   ├── camera_manager.py
│   │   └── alert_manager.py
│   └── utils/                 # 工具函数
│       ├── auth_utils.py      # JWT工具
│       └── websocket_manager.py
├── frontend/                  # React前端
│   ├── src/
│   │   ├── pages/            # 页面组件
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── LiveMonitor.tsx
│   │   │   ├── AlertList.tsx
│   │   │   └── CameraManage.tsx
│   │   ├── components/       # 通用组件
│   │   │   └── Layout.tsx
│   │   ├── services/         # API服务
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml         # Docker编排
└── README.md
```

## 🛠️ 技术栈

### 后端
- **Python 3.9+**
- **FastAPI**: 高性能Web框架
- **SQLAlchemy**: ORM框架
- **Pydantic**: 数据验证
- **PostgreSQL**: 主数据库
- **Redis**: 缓存和消息队列
- **WebSocket**: 实时通信
- **OpenCV**: 图像处理
- **PyTorch/TensorFlow**: 深度学习推理

### 前端
- **React 18**
- **TypeScript**
- **Material-UI (MUI)**: UI组件库
- **React Router**: 路由管理
- **Axios**: HTTP客户端

### 部署
- **Docker**: 容器化
- **Docker Compose**: 多容器编排
- **Nginx**: 反向代理

## 📦 安装部署

### 方式一：Docker Compose（推荐）

1. 克隆项目
```bash
git clone <repository-url>
cd kitchen_ai_system
```

2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库密码等
```

3. 启动服务
```bash
docker-compose up -d
```

4. 访问系统
- 前端: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

### 方式二：本地开发

#### 后端
```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置数据库
# 确保PostgreSQL已运行，并创建数据库

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm start
```

## 🔧 配置说明

### 环境变量

创建 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=postgresql://postgres:password@localhost:5432/kitchen_ai

# Redis配置
REDIS_URL=redis://localhost:6379/0

# JWT配置
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 推理引擎配置
INFERENCE_ENGINE_URL=http://localhost:8001
MAX_CONCURRENT_CAMERAS=10

# 告警配置
ALERT_COOLDOWN_SECONDS=60
MAX_ALERTS_PER_HOUR=100
```

## 📚 API文档

启动后端服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要API端点

#### 认证
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息

#### 摄像头
- `GET /api/cameras/` - 获取摄像头列表
- `POST /api/cameras/` - 创建摄像头
- `PUT /api/cameras/{id}` - 更新摄像头
- `DELETE /api/cameras/{id}` - 删除摄像头
- `POST /api/cameras/{id}/start` - 启动推理
- `POST /api/cameras/{id}/stop` - 停止推理

#### 告警
- `GET /api/alerts/` - 获取告警列表
- `POST /api/alerts/` - 创建告警
- `POST /api/alerts/{id}/acknowledge` - 确认告警
- `POST /api/alerts/{id}/resolve` - 解决告警

#### 仪表盘
- `GET /api/dashboard/stats` - 获取统计数据
- `GET /api/dashboard/alerts/stats` - 告警统计
- `GET /api/dashboard/cameras/stats` - 摄像头统计

## 🔒 安全说明

- 所有API端点都需要JWT认证
- 密码使用bcrypt加密存储
- 支持CORS配置
- 建议在生产环境中：
  - 修改默认密码
  - 使用HTTPS
  - 配置防火墙规则
  - 定期备份数据库

## 🐛 常见问题

### 1. 数据库连接失败
- 检查PostgreSQL是否运行
- 验证数据库连接字符串
- 确保数据库已创建

### 2. 摄像头无法连接
- 检查RTSP/RTMP地址是否正确
- 验证网络连通性
- 检查防火墙设置

### 3. 推理服务无响应
- 检查模型文件是否存在
- 验证GPU驱动和CUDA版本
- 查看推理服务日志

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 联系方式

- 项目主页: [GitHub Repository]
- 问题反馈: [Issues]
- 邮箱: [your-email@example.com]

## 🙏 致谢

感谢以下开源项目：
- FastAPI
- React
- Material-UI
- OpenCV
- PyTorch