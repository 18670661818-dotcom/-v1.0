from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import threading

from config import ALLOWED_ORIGINS
from models.database import init_db
from routers import auth, cameras, alerts, rtsp_test, websocket, stream, dashboard, reports, settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='后厨智能监测系统', 
    version='2.0.0',
    description='基于YOLO的后厨安全智能监测系统'
)

# CORS 配置 - 生产环境应限制允许的来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(settings.router)
app.include_router(rtsp_test.router)
app.include_router(websocket.router)
app.include_router(stream.router)


# 全局推理服务实例
inference_service = None

@app.on_event('startup')
def startup():
    """应用启动时初始化"""
    global inference_service
    try:
        init_db()
        logger.info('数据库初始化完成')

        # 启动推理服务
        from services.inference_service import InferenceService
        inference_service = InferenceService()

        # 在后台线程中启动推理服务
        def start_inference():
            try:
                inference_service.start()
                logger.info('推理服务启动成功')
            except Exception as e:
                logger.error(f'推理服务启动失败: {e}')

        inference_thread = threading.Thread(target=start_inference, daemon=True)
        inference_thread.start()

        logger.info('后厨智能监测系统启动成功')
    except Exception as e:
        logger.error(f'启动失败: {e}')
        raise


@app.on_event('shutdown')
def shutdown():
    """应用关闭时清理资源"""
    global inference_service
    if inference_service:
        inference_service.stop()
        logger.info('推理服务已停止')
    logger.info('后厨智能监测系统正在关闭...')


@app.get('/')
def root():
    """系统根路径"""
    return {
        'name': '后厨智能监测系统', 
        'version': '2.0.0', 
        'docs': '/docs',
        'status': 'running'
    }


@app.get('/health')
def health_check():
    """健康检查接口"""
    return {'status': 'healthy', 'timestamp': __import__('datetime').datetime.utcnow().isoformat()}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app, 
        host='0.0.0.0', 
        port=8000,
        log_level='info',
        access_log=True
    )