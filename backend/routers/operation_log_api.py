"""操作日志路由（管理员功能）"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional

from models.database import get_db, User
from models.operation_log import OperationLog
from utils.auth_utils import get_current_admin

router = APIRouter(prefix="/api/logs", tags=["操作日志"])


@router.get("/")
def list_logs(
    user_id: Optional[int] = Query(None),
    username: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取操作日志列表（管理员）"""
    query = db.query(OperationLog)

    # 过滤条件
    if user_id:
        query = query.filter(OperationLog.user_id == user_id)
    if username:
        query = query.filter(OperationLog.username.contains(username))
    if action:
        query = query.filter(OperationLog.action == action)
    if target_type:
        query = query.filter(OperationLog.target_type == target_type)
    if target_id:
        query = query.filter(OperationLog.target_id == target_id)
    if start_time:
        query = query.filter(OperationLog.created_at >= datetime.fromisoformat(start_time))
    if end_time:
        query = query.filter(OperationLog.created_at <= datetime.fromisoformat(end_time))

    # 总数
    total = query.count()

    # 分页
    logs = query.order_by(desc(OperationLog.created_at))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    # 构建响应
    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": log.username,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": items
    }


@router.get("/{log_id}")
def get_log(
    log_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取操作日志详情（管理员）"""
    log = db.query(OperationLog).filter(OperationLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")

    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": log.username,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "detail": log.detail,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("/stats/summary")
def log_stats_summary(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """操作日志统计摘要（管理员）"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # 总数
    total = db.query(OperationLog).count()
    recent = db.query(OperationLog).filter(OperationLog.created_at >= start_date).count()

    # 按操作类型统计
    action_stats = db.query(
        OperationLog.action, func.count(OperationLog.id)
    ).filter(
        OperationLog.created_at >= start_date
    ).group_by(OperationLog.action).all()

    by_action = {row[0]: row[1] for row in action_stats}

    # 按用户统计
    user_stats = db.query(
        OperationLog.username, func.count(OperationLog.id)
    ).filter(
        OperationLog.created_at >= start_date
    ).group_by(OperationLog.username).all()

    by_user = {row[0]: row[1] for row in user_stats}

    # 按目标类型统计
    target_stats = db.query(
        OperationLog.target_type, func.count(OperationLog.id)
    ).filter(
        OperationLog.created_at >= start_date
    ).group_by(OperationLog.target_type).all()

    by_target = {row[0]: row[1] for row in target_stats}

    # 近7天趋势
    trend = []
    for i in range(days):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        count = db.query(OperationLog).filter(
            OperationLog.created_at >= day_start,
            OperationLog.created_at < day_end
        ).count()

        trend.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })

    trend.reverse()

    return {
        "total": total,
        "recent": recent,
        "by_action": by_action,
        "by_user": by_user,
        "by_target": by_target,
        "trend": trend,
    }


def log_operation(
    db: Session,
    user_id: int,
    username: str,
    action: str,
    target_type: str = None,
    target_id: str = None,
    detail: str = None,
    ip_address: str = None
):
    """记录操作日志（工具函数）"""
    log = OperationLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()
    return log