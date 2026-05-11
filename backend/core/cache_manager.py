"""缓存管理器
提供内存缓存功能，减少数据库查询次数
"""
import time
from typing import Any, Optional, Callable
from functools import wraps
from threading import Lock


class CacheManager:
    """内存缓存管理器"""

    def __init__(self, default_ttl: int = 300):
        """
        初始化缓存管理器
        :param default_ttl: 默认缓存时间（秒）
        """
        self._cache = {}
        self._lock = Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key in self._cache:
                value, expire_time = self._cache[key]
                if time.time() < expire_time:
                    return value
                else:
                    # 缓存过期，删除
                    del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        if ttl is None:
            ttl = self.default_ttl

        expire_time = time.time() + ttl

        with self._lock:
            self._cache[key] = (value, expire_time)

    def delete(self, key: str):
        """删除缓存值"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self):
        """清理过期的缓存项"""
        current_time = time.time()
        with self._lock:
            expired_keys = [
                key for key, (_, expire_time) in self._cache.items()
                if current_time >= expire_time
            ]
            for key in expired_keys:
                del self._cache[key]

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        with self._lock:
            total_items = len(self._cache)
            current_time = time.time()
            expired_items = sum(
                1 for _, expire_time in self._cache.values()
                if current_time >= expire_time
            )
            return {
                "total_items": total_items,
                "expired_items": expired_items,
                "active_items": total_items - expired_items,
            }


# 全局缓存管理器实例
cache_manager = CacheManager()


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    缓存装饰器
    :param ttl: 缓存时间（秒）
    :param key_prefix: 缓存键前缀
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # 尝试从缓存获取
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            cache_manager.set(cache_key, result, ttl)

            return result
        return wrapper
    return decorator


def cache_key_generator(*args, **kwargs) -> str:
    """生成缓存键"""
    return f"{hash(str(args) + str(kwargs))}"