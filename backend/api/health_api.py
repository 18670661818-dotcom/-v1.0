"""
健康检查API
"""
import datetime
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("")
def health_check():
    """
    基本健康检查
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
