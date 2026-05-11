"""监控API
提供系统监控数据接口
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timedelta

from core.database import get_db
from utils.auth_utils import get_current_admin
from core.monitoring import get_system_stats, get_metrics, system_monitor
from models.database import User

router = APIRouter(prefix="/api/monitoring", tags=["监控"])


@router.get("/stats", summary="获取系统统计信息")
async def get_system_statistics(
    current_user: User = Depends(get_current_admin)
) -> Dict[str, Any]:
    """获取系统统计信息"""
    return get_system_stats()


@router.get("/metrics", summary="获取性能指标")
async def get_performance_metrics(
    name: str = None,
    current_user: User = Depends(get_current_admin)
) -> Dict[str, Any]:
    """获取性能指标"""
    return get_metrics(name)


@router.get("/health", summary="健康检查")
async def health_check() -> Dict[str, Any]:
    """健康检查接口"""
    try:
        stats = get_system_stats()
        if "error" in stats:
            return {"status": "unhealthy", "error": stats["error"]}
        
        # 检查系统资源使用情况
        if stats.get("cpu_percent", 0) > 90:
            return {"status": "warning", "message": "CPU使用率过高"}
        if stats.get("memory_percent", 0) > 90:
            return {"status": "warning", "message": "内存使用率过高"}
        if stats.get("disk_percent", 0) > 90:
            return {"status": "warning", "message": "磁盘使用率过高"}
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "N/A"  # 可以添加运行时间计算
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/logs", summary="获取最近日志")
async def get_recent_logs(
    log_type: str = "app",
    lines: int = 50,
    current_user: User = Depends(get_current_admin)
) -> List[str]:
    """获取最近日志"""
    try:
        log_dir = Path("logs")
        log_file = log_dir / f"{log_type}_{datetime.now().strftime('%Y%m%d')}.log"
        
        if not log_file.exists():
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")


@router.post("/metrics/reset", summary="重置指标")
async def reset_metrics(
    current_user: User = Depends(get_current_admin)
) -> Dict[str, str]:
    """重置所有性能指标"""
    with system_monitor.lock:
        system_monitor.metrics.clear()
    return {"message": "指标已重置"}