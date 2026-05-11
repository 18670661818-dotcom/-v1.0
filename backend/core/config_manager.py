"""配置管理器
统一管理配置，优先从数据库加载，回退到环境变量和默认值
"""
from typing import Any, Optional
from functools import lru_cache

from core.config import settings
from core.database import SessionLocal


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        self._db_session = None

    def _get_db_session(self):
        """获取数据库会话"""
        if self._db_session is None:
            self._db_session = SessionLocal()
        return self._db_session

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        # 首先尝试从数据库加载
        try:
            from models.config import Config
            db = self._get_db_session()
            config = db.query(Config).filter(Config.key == key).first()
            if config:
                return config.get_typed_value()
        except Exception:
            # 如果数据库查询失败，回退到环境变量
            pass

        # 回退到环境变量
        import os
        env_value = os.getenv(key.upper())
        if env_value is not None:
            # 尝试转换类型
            if isinstance(default, bool):
                return env_value.lower() in ("true", "1", "yes")
            elif isinstance(default, int):
                return int(env_value)
            elif isinstance(default, float):
                return float(env_value)
            else:
                return env_value

        # 使用默认值
        return default

    def set(self, key: str, value: Any, value_type: str = "string"):
        """设置配置值"""
        try:
            from models.config import Config
            from datetime import datetime
            db = self._get_db_session()
            config = db.query(Config).filter(Config.key == key).first()
            if config:
                config.set_typed_value(value)
                config.updated_at = datetime.utcnow()
            else:
                config = Config(key=key, value_type=value_type)
                config.set_typed_value(value)
                db.add(config)
            db.commit()
        except Exception as e:
            # 如果数据库操作失败，记录日志但不抛出异常
            import logging
            logging.error(f"Failed to set config {key}: {e}")

    def get_settings(self) -> dict:
        """获取所有配置"""
        config_dict = {}

        # 从数据库加载
        try:
            from models.config import Config
            db = self._get_db_session()
            configs = db.query(Config).all()
            for config in configs:
                config_dict[config.key] = config.get_typed_value()
        except Exception:
            pass

        # 从环境变量加载
        import os
        for key, value in os.environ.items():
            if key not in config_dict:
                config_dict[key] = value

        return config_dict

    def close(self):
        """关闭数据库会话"""
        if self._db_session:
            self._db_session.close()
            self._db_session = None


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config(key: str, default: Any = None) -> Any:
    """获取配置值"""
    return config_manager.get(key, default)


def set_config(key: str, value: Any, value_type: str = "string"):
    """设置配置值"""
    config_manager.set(key, value, value_type)