"""
后厨智能监测系统 - FastAPI 主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import threading
import os
import datetime

from core.config import settings
from core.logger import app_logger
from models.database import init_db

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 静态文件挂载
if os.path.exists("storage/alerts"):
    app.mount("/alert_images", StaticFiles(directory="storage/alerts"), name="alert_images")

# 注册 API 路由
from api.health_api import router as health_router
from api.camera_api import router as camera_router
from api.alert_api import router as alert_router
from api.ws_api import router as websocket_router

app.include_router(health_router)
app.include_router(camera_router)
app.include_router(alert_router)
app.include_router(websocket_router)

# 兼容旧路由
from routers import auth, cameras, alerts, rtsp_test, websocket, stream, dashboard, reports, settings as settings_router

app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(settings_router.router)
app.include_router(rtsp_test.router)
app.include_router(websocket.router)
app.include_router(stream.router)


# 全局服务管理器
service_manager = None


@app.on_event('startup')
def startup():
    """应用启动时初始化"""
    global service_manager

    try:
        # 初始化数据库
        init_db()
        app_logger.info('数据库初始化完成')

        # 初始化服务管理器
        from services.main import get_service_manager, load_camera_config

        service_manager = get_service_manager()
        service_manager.initialize(inference_fps=settings.INFERENCE_FPS)

        # 加载摄像头配置
        camera_config = load_camera_config()
        service_manager.load_cameras(camera_config)

        # 在后台线程中启动服务
        def start_services():
            try:
                service_manager.start()
                app_logger.info('服务层启动成功')
            except Exception as e:
                app_logger.error(f'服务层启动失败: {e}')

        service_thread = threading.Thread(target=start_services, daemon=True)
        service_thread.start()

        app_logger.info(f'{settings.APP_NAME} v{settings.APP_VERSION} 启动成功')

    except Exception as e:
        app_logger.error(f'启动失败: {e}')
        raise


@app.on_event('shutdown')
def shutdown():
    """应用关闭时清理资源"""
    global service_manager

    if service_manager:
        service_manager.stop()
        app_logger.info('服务层已停止')

    app_logger.info(f'{settings.APP_NAME} 正在关闭...')


@app.get('/')
def root():
    """系统根路径"""
    return {
        'name': settings.APP_NAME,
        'version': settings.APP_VERSION,
        'docs': '/docs',
        'status': 'running'
    }


@app.get('/health')
def health_check():
    """
    健康检查接口
    返回系统各组件状态
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'components': {}
    }

    # 检查数据库连接
    try:
        from models.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_status['components']['database'] = {'status': 'healthy'}
    except Exception as e:
        health_status['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'

    # 检查推理服务状态
    global service_manager
    if service_manager and service_manager.inference_service:
        try:
            inference_status = service_manager.inference_service.get_status()
            health_status['components']['inference'] = {
                'status': 'healthy' if inference_status.get('running') else 'stopped',
                'details': inference_status
            }
        except Exception as e:
            health_status['components']['inference'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
    else:
        health_status['components']['inference'] = {'status': 'not_initialized'}

    # 检查摄像头服务状态
    if service_manager and service_manager.camera_service:
        try:
            camera_status = service_manager.camera_service.get_all_status()
            online_count = sum(
                1 for c in camera_status.get('cameras', {}).values()
                if c and c.get('is_online')
            )
            health_status['components']['cameras'] = {
                'status': 'healthy' if online_count > 0 else 'warning',
                'total': camera_status.get('total_cameras', 0),
                'online': online_count
            }
        except Exception as e:
            health_status['components']['cameras'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
    else:
        health_status['components']['cameras'] = {'status': 'not_initialized'}

    return health_status


@app.get('/api/status')
def get_system_status():
    """获取系统状态"""
    global service_manager

    if service_manager:
        return service_manager.get_status()
    else:
        return {
            "running": False,
            "error": "服务未初始化"
        }


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG
    )
