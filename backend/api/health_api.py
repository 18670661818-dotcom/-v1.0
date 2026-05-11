"""
健康检查API
"""
import datetime
from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("")
def health_check_simple():
    """
    简单健康检查
    返回系统各组件状态（简化格式）
    """
    from models.database import SessionLocal
    from services.camera_service import camera_service
    from services.inference_service import get_inference_service
    
    health_status = {
        "backend": "running",
        "database": "ok",
        "camera_service": "running",
        "inference_service": "running",
        "websocket": "running",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 检查数据库健康状态（真实执行查询）
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
    
    # 检查摄像头服务状态
    try:
        camera_status = camera_service.get_all_status()
        if camera_status.get("total_cameras", 0) > 0:
            health_status["camera_service"] = "running"
        else:
            health_status["camera_service"] = "no_cameras"
    except Exception as e:
        health_status["camera_service"] = f"error: {str(e)}"
    
    # 检查推理服务状态
    try:
        inference_service = get_inference_service()
        inference_status = inference_service.get_status()
        if inference_status.get("running"):
            health_status["inference_service"] = "running"
        else:
            health_status["inference_service"] = "stopped"
    except Exception as e:
        health_status["inference_service"] = f"error: {str(e)}"
    
    # 检查WebSocket服务状态
    try:
        from services.websocket_service import websocket_service
        ws_count = websocket_service.get_connection_count()
        health_status["websocket"] = "running"
    except Exception as e:
        health_status["websocket"] = f"error: {str(e)}"
    
    return health_status


@router.get("/detailed")
def health_check_detailed():
    """
    详细健康检查
    返回系统完整状态信息
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'system': {},
        'components': {}
    }

    # 系统资源信息
    try:
        import psutil
        import os
        health_status['system'] = {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'pid': os.getpid()
        }
    except Exception as e:
        health_status['system'] = {'error': str(e)}

    # 检查数据库连接
    try:
        from models.database import SessionLocal, Camera, Alert
        db = SessionLocal()
        camera_count = db.query(Camera).count()
        alert_count = db.query(Alert).count()
        db.close()
        health_status['components']['database'] = {
            'status': 'healthy',
            'cameras': camera_count,
            'alerts': alert_count
        }
    except Exception as e:
        health_status['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'

    # 检查推理服务状态
    try:
        from services.inference_service import get_inference_service
        inference_service = get_inference_service()
        inference_status = inference_service.get_status()
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

    # 检查摄像头服务状态
    try:
        from services.camera_service import camera_service
        camera_status = camera_service.get_all_status()
        health_status['components']['cameras'] = {
            'status': 'healthy',
            'details': camera_status
        }
    except Exception as e:
        health_status['components']['cameras'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'

    # 检查WebSocket连接
    try:
        from services.websocket_service import websocket_service
        ws_status = websocket_service.get_connection_count()
        health_status['components']['websocket'] = {
            'status': 'healthy',
            'connections': ws_status
        }
    except Exception as e:
        health_status['components']['websocket'] = {
            'status': 'unhealthy',
            'error': str(e)
        }

    return health_status


@router.get("/ready")
def readiness_check():
    """
    就绪检查（用于Kubernetes等）
    """
    try:
        # 检查数据库
        from models.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()

        return {"status": "ready"}
    except Exception as e:
        return {"status": "not ready", "error": str(e)}


@router.get("/live")
def liveness_check():
    """
    存活检查（用于Kubernetes等）
    """
    return {"status": "alive"}
