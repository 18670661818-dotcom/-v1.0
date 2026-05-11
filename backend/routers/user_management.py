"""用户管理路由（管理员功能）"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from models.database import get_db, User, UserRole
from utils.auth_utils import get_current_admin

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("/")
def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取用户列表（管理员）"""
    query = db.query(User)

    # 过滤条件
    if role:
        try:
            query = query.filter(User.role == UserRole(role))
        except ValueError:
            pass
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # 总数
    total = query.count()

    # 分页
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    # 构建响应
    items = []
    for user in users:
        items.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "company_name": user.company_name,
            "role": user.role.value if user.role else "viewer",
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": items
    }


@router.get("/{user_id}")
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取用户详情（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "company_name": user.company_name,
        "role": user.role.value if user.role else "viewer",
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    username: Optional[str] = None,
    email: Optional[str] = None,
    company_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新用户信息（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查用户名是否重复
    if username and username != user.username:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = username

    # 检查邮箱是否重复
    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="邮箱已注册")
        user.email = email

    if company_name is not None:
        user.company_name = company_name

    if role is not None:
        try:
            user.role = UserRole(role)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的用户角色")

    if is_active is not None:
        user.is_active = is_active

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return {"message": "用户信息更新成功"}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除用户（管理员）"""
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查用户是否有相关数据
    from models.database import Camera, Alert
    camera_count = db.query(Camera).filter(Camera.user_id == user_id).count()
    alert_count = db.query(Alert).filter(Alert.user_id == user_id).count()

    if camera_count > 0 or alert_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"用户有 {camera_count} 个摄像头和 {alert_count} 条告警记录，请先处理这些数据"
        )

    db.delete(user)
    db.commit()

    return {"message": "用户已删除"}


@router.post("/{user_id}/activate")
def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """激活用户（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = True
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "用户已激活"}


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """停用用户（管理员）"""
    # 不能停用自己
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能停用自己")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "用户已停用"}


@router.get("/stats/summary")
def user_stats_summary(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """用户统计摘要（管理员）"""
    from sqlalchemy import func

    total = db.query(User).count()
    active = db.query(User).filter(User.is_active == True).count()
    inactive = total - active

    # 按角色统计
    role_stats = db.query(
        User.role, func.count(User.id)
    ).group_by(User.role).all()

    by_role = {row[0].value if row[0] else "unknown": row[1] for row in role_stats}

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "by_role": by_role,
    }