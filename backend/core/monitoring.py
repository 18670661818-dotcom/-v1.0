"""监控模块
收集系统性能指标和错误日志
"""
import time
import psutil
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
from threading import Lock

from core.config import settings


class SystemMonitor:
    """系统监控器"""

    def __init__(self):
        self.metrics = {}
        self.lock = Lock()
        self.logger = logging.getLogger("monitor")

    def record_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录指标"""
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = []
            
            metric = {
                "value": value,
                "timestamp": datetime.utcnow().isoformat(),
                "tags": tags or {}
            }
            
            self.metrics[name].append(metric)
            
            # 只保留最近1000条记录
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]

    def get_metrics(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取指标"""
        with self.lock:
            if name:
                return {name: self.metrics.get(name, [])}
            return self.metrics.copy()

    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used / (1024**3),
                "disk_total_gb": disk.total / (1024**3),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"获取系统统计信息失败: {e}")
            return {"error": str(e)}

    def monitor_function(self, name: str, tags: Optional[Dict[str, str]] = None):
        """函数监控装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    self.record_metric(f"{name}_duration", duration, tags)
                    self.record_metric(f"{name}_success", 1, tags)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.record_metric(f"{name}_duration", duration, tags)
                    self.record_metric(f"{name}_error", 1, tags)
                    self.logger.error(f"函数 {name} 执行失败: {e}")
                    raise
            return wrapper
        return decorator


# 全局监控器实例
system_monitor = SystemMonitor()


def monitor_performance(name: str, tags: Optional[Dict[str, str]] = None):
    """性能监控装饰器"""
    return system_monitor.monitor_function(name, tags)


def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """记录指标"""
    system_monitor.record_metric(name, value, tags)


def get_system_stats() -> Dict[str, Any]:
    """获取系统统计信息"""
    return system_monitor.get_system_stats()


def get_metrics(name: Optional[str] = None) -> Dict[str, Any]:
    """获取指标"""
    return system_monitor.get_metrics(name)