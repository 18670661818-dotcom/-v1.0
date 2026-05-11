"""配置管理路由"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
import json
from pydantic import BaseModel

from models.database import get_db, User
from models.config import Config
from utils.auth_utils import get_current_user, get_current_admin


class ConfigCreate(BaseModel):
    key: str
    value: Any
    value_type: str = "string"
    description: Optional[str] = None
    category: Optional[str] = "system"
    is_public: bool = False


class ConfigUpdate(BaseModel):
    value: Optional[Any] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None

router = APIRouter(prefix="/api/config", tags=["配置管理"])


@router.get("/")
def list_configs(
    category: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取配置列表"""
    query = db.query(Config)

    # 过滤条件
    if category:
        query = query.filter(Config.category == category)
    if is_public is not None:
        query = query.filter(Config.is_public == is_public)

    # 非管理员只能查看公开配置
    if current_user.role.value not in ["admin", "manager"]:
        query = query.filter(Config.is_public == True)

    configs = query.all()

    # 构建响应
    items = []
    for config in configs:
        items.append({
            "id": config.id,
            "key": config.key,
            "value": config.get_typed_value(),
            "value_type": config.value_type,
            "description": config.description,
            "category": config.category,
            "is_public": config.is_public,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        })

    return items


@router.get("/{key}")
def get_config(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取配置值"""
    config = db.query(Config).filter(Config.key == key).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 非管理员只能查看公开配置
    if current_user.role.value not in ["admin", "manager"] and not config.is_public:
        raise HTTPException(status_code=403, detail="权限不足")

    return {
        "key": config.key,
        "value": config.get_typed_value(),
        "value_type": config.value_type,
        "description": config.description,
        "category": config.category,
        "is_public": config.is_public,
    }


@router.post("/")
def create_config(
    config_data: ConfigCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """创建配置（管理员）"""
    # 检查key是否重复
    existing = db.query(Config).filter(Config.key == config_data.key).first()
    if existing:
        raise HTTPException(status_code=400, detail="配置键已存在")

    # 验证value_type
    valid_types = ["string", "integer", "float", "boolean", "json"]
    if config_data.value_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效的值类型，支持: {valid_types}")

    # 创建配置
    config = Config(
        key=config_data.key,
        value_type=config_data.value_type,
        description=config_data.description,
        category=config_data.category,
        is_public=config_data.is_public,
    )
    config.set_typed_value(config_data.value)

    db.add(config)
    db.commit()
    db.refresh(config)

    return {"message": "配置创建成功", "id": config.id}


@router.put("/{key}")
def update_config(
    key: str,
    config_data: ConfigUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新配置（管理员）"""
    config = db.query(Config).filter(Config.key == key).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    if config_data.value is not None:
        config.set_typed_value(config_data.value)

    if config_data.description is not None:
        config.description = config_data.description

    if config_data.category is not None:
        config.category = config_data.category

    if config_data.is_public is not None:
        config.is_public = config_data.is_public

    config.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "配置更新成功"}


@router.delete("/{key}")
def delete_config(
    key: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除配置（管理员）"""
    config = db.query(Config).filter(Config.key == key).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    db.delete(config)
    db.commit()

    return {"message": "配置已删除"}


@router.get("/category/{category}")
def get_configs_by_category(
    category: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """按类别获取配置"""
    query = db.query(Config).filter(Config.category == category)

    # 非管理员只能查看公开配置
    if current_user.role.value not in ["admin", "manager"]:
        query = query.filter(Config.is_public == True)

    configs = query.all()

    # 构建响应
    items = []
    for config in configs:
        items.append({
            "key": config.key,
            "value": config.get_typed_value(),
            "value_type": config.value_type,
            "description": config.description,
            "is_public": config.is_public,
        })

    return items


def get_config_value(db: Session, key: str, default: Any = None) -> Any:
    """获取配置值（工具函数）"""
    config = db.query(Config).filter(Config.key == key).first()
    if config:
        return config.get_typed_value()
    return default


def set_config_value(db: Session, key: str, value: Any, value_type: str = "string"):
    """设置配置值（工具函数）"""
    config = db.query(Config).filter(Config.key == key).first()
    if config:
        config.set_typed_value(value)
        config.updated_at = datetime.utcnow()
    else:
        config = Config(key=key, value_type=value_type)
        config.set_typed_value(value)
        db.add(config)
    db.commit()
    return config