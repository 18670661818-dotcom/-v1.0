"""报表数据路由"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, extract
from typing import List, Optional
import csv
import io

from models.database import get_db, User, Alert, AlertLevel, Camera
from utils.auth_utils import get_current_user

router = APIRouter(prefix="/api/reports", tags=["报表管理"])


@router.get("/summary")
def get_report_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取报表汇总数据"""
    # 默认查询最近7天
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)

    # 基础查询
    base_query = db.query(Alert).filter(
        Alert.detected_at >= start_dt,
        Alert.detected_at < end_dt
    )

    # 按用户过滤
    if current_user.role.value != "admin":
        base_query = base_query.filter(Alert.user_id == current_user.id)

    # 按摄像头过滤
    if camera_id:
        base_query = base_query.filter(Alert.camera_id == camera_id)

    # 总告警数
    total_alerts = base_query.count()

    # 严重告警数
    critical_alerts = base_query.filter(Alert.level == AlertLevel.CRITICAL).count()

    # 警告告警数
    warning_alerts = base_query.filter(Alert.level == AlertLevel.WARNING).count()

    # 处理率
    acknowledged_count = base_query.filter(Alert.acknowledged_at.isnot(None)).count()
    acknowledged_rate = (acknowledged_count / total_alerts * 100) if total_alerts > 0 else 0

    # 平均响应时间（分钟）
    avg_response_time = 0
    acknowledged_alerts = base_query.filter(
        Alert.acknowledged_at.isnot(None)
    ).all()

    if acknowledged_alerts:
        total_minutes = sum(
            (alert.acknowledged_at - alert.detected_at).total_seconds() / 60
            for alert in acknowledged_alerts
        )
        avg_response_time = total_minutes / len(acknowledged_alerts)

    # 按类型统计
    type_stats = db.query(
        Alert.violation_type, func.count(Alert.id)
    ).filter(
        Alert.detected_at >= start_dt,
        Alert.detected_at < end_dt
    )
    if current_user.role.value != "admin":
        type_stats = type_stats.filter(Alert.user_id == current_user.id)
    if camera_id:
        type_stats = type_stats.filter(Alert.camera_id == camera_id)
    type_stats = type_stats.group_by(Alert.violation_type).all()

    by_type = {row[0]: row[1] for row in type_stats}

    # 按摄像头统计
    cam_stats = db.query(
        Alert.camera_id, Alert.camera_name, func.count(Alert.id)
    ).filter(
        Alert.detected_at >= start_dt,
        Alert.detected_at < end_dt
    )
    if current_user.role.value != "admin":
        cam_stats = cam_stats.filter(Alert.user_id == current_user.id)
    if camera_id:
        cam_stats = cam_stats.filter(Alert.camera_id == camera_id)
    cam_stats = cam_stats.group_by(Alert.camera_id, Alert.camera_name).all()

    by_camera = {f"{row[0]} ({row[1] or row[0]})": row[2] for row in cam_stats}

    # 按小时统计
    hour_stats = []
    for hour in range(24):
        count = base_query.filter(
            extract('hour', Alert.detected_at) == hour
        ).count()
        hour_stats.append({"hour": hour, "count": count})

    # 趋势数据
    trend = []
    current_date = start_dt
    while current_date < end_dt:
        next_date = current_date + timedelta(days=1)
        count = base_query.filter(
            Alert.detected_at >= current_date,
            Alert.detected_at < next_date
        ).count()
        trend.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "count": count
        })
        current_date = next_date

    # 违规类型排行
    top_violations = []
    for vtype, count in type_stats:
        percentage = (count / total_alerts * 100) if total_alerts > 0 else 0
        top_violations.append({
            "type": vtype,
            "count": count,
            "percentage": percentage
        })
    top_violations.sort(key=lambda x: x["count"], reverse=True)

    # 摄像头统计
    camera_stats = []
    cameras = db.query(Camera).all()
    for camera in cameras:
        cam_alerts = base_query.filter(Alert.camera_id == camera.camera_id)
        total = cam_alerts.count()
        critical = cam_alerts.filter(Alert.level == AlertLevel.CRITICAL).count()

        # 计算在线率（简化处理）
        online_rate = 100.0 if camera.status.value == "online" else 0.0

        camera_stats.append({
            "camera_id": camera.camera_id,
            "name": camera.name,
            "total": total,
            "critical": critical,
            "online_rate": online_rate
        })
    camera_stats.sort(key=lambda x: x["total"], reverse=True)

    return {
        "total_alerts": total_alerts,
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
        "acknowledged_rate": round(acknowledged_rate, 1),
        "avg_response_time": round(avg_response_time, 1),
        "by_type": by_type,
        "by_camera": by_camera,
        "by_hour": hour_stats,
        "trend": trend,
        "top_violations": top_violations,
        "camera_stats": camera_stats
    }


@router.get("/export")
def export_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    format: str = Query("csv"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出报表"""
    # 默认查询最近7天
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)

    # 查询告警数据
    query = db.query(Alert).filter(
        Alert.detected_at >= start_dt,
        Alert.detected_at < end_dt
    )

    if current_user.role.value != "admin":
        query = query.filter(Alert.user_id == current_user.id)
    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)

    alerts = query.order_by(desc(Alert.detected_at)).all()

    # 生成CSV内容
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow([
        "告警ID", "摄像头ID", "摄像头名称", "违规类型", "违规名称",
        "置信度", "告警级别", "检测时间", "确认时间"
    ])

    # 写入数据
    for alert in alerts:
        writer.writerow([
            alert.alert_id or str(alert.id),
            alert.camera_id,
            alert.camera_name or alert.camera_id,
            alert.violation_type,
            alert.violation_name or alert.violation_type,
            f"{alert.confidence:.2f}" if alert.confidence else "0.00",
            alert.level.value if alert.level else "warning",
            alert.detected_at.strftime("%Y-%m-%d %H:%M:%S") if alert.detected_at else "",
            alert.acknowledged_at.strftime("%Y-%m-%d %H:%M:%S") if alert.acknowledged_at else ""
        ])

    output.seek(0)

    # 返回文件流
    filename = f"report_{start_date}_{end_date}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )