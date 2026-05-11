"""Database models and lightweight SQLite schema migration."""
from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from core.config import settings
from core.database import engine, SessionLocal, Base, get_db
from core.logger import database_log

# 从新模型文件导入
from .user import User, UserRole
from .camera import Camera, CameraStatus
from .alert import Alert, AlertLevel, AlertStatus
from .config import Config

DATABASE_URL = settings.DATABASE_URL










class DetectionLog(Base):
    __tablename__ = "detection_logs"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(100), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    class_name = Column(String(100), index=True)
    count = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_detection_camera_timestamp", "camera_id", "timestamp"),
        Index("idx_detection_class_timestamp", "class_name", "timestamp"),
    )


def _execute_ddl(conn, sql: str):
    try:
        conn.exec_driver_sql(sql)
    except AttributeError:
        conn.execute(sql)


def _ensure_alert_schema():
    """Add lifecycle columns to existing SQLite alert tables."""
    if "sqlite" not in DATABASE_URL:
        return

    required_columns = {
        "alert_type": "VARCHAR(100)",
        "status": "VARCHAR(20) DEFAULT 'PENDING'",
        "video_clip_path": "VARCHAR(500)",
        "confirmed_at": "DATETIME",
        "resolved_at": "DATETIME",
        "handled_by": "VARCHAR(100)",
        "remark": "TEXT",
        "is_false_positive": "BOOLEAN DEFAULT 0",
        "acknowledged_at": "DATETIME",
        "acknowledged_by": "INTEGER",
    }

    with engine.begin() as conn:
        try:
            rows = conn.exec_driver_sql("PRAGMA table_info(alerts)").fetchall()
        except AttributeError:
            rows = conn.execute("PRAGMA table_info(alerts)").fetchall()
        existing = {row[1] for row in rows}
        for column_name, ddl in required_columns.items():
            if column_name not in existing:
                _execute_ddl(conn, f"ALTER TABLE alerts ADD COLUMN {column_name} {ddl}")

        _execute_ddl(conn, "UPDATE alerts SET alert_type = violation_type WHERE alert_type IS NULL")
        _execute_ddl(conn, "UPDATE alerts SET status = 'PENDING' WHERE status IS NULL OR status = 'pending'")
        _execute_ddl(conn, "UPDATE alerts SET status = 'CONFIRMED' WHERE status = 'confirmed'")
        _execute_ddl(conn, "UPDATE alerts SET status = 'RESOLVED' WHERE status = 'resolved'")
        _execute_ddl(conn, "UPDATE alerts SET status = 'FALSE_POSITIVE' WHERE status = 'false_positive'")
        _execute_ddl(conn, "UPDATE alerts SET is_false_positive = 0 WHERE is_false_positive IS NULL")


def _ensure_schema_updates():
    """Add new columns to existing tables."""
    if "sqlite" not in DATABASE_URL:
        return
    
    # 更新users表
    required_columns_users = {
        "updated_at": "DATETIME",
    }
    
    with engine.begin() as conn:
        try:
            rows = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        except AttributeError:
            rows = conn.execute("PRAGMA table_info(users)").fetchall()
        existing = {row[1] for row in rows}
        for column_name, ddl in required_columns_users.items():
            if column_name not in existing:
                _execute_ddl(conn, f"ALTER TABLE users ADD COLUMN {column_name} {ddl}")
    
    # 更新cameras表
    required_columns_cameras = {
        "description": "VARCHAR(500)",
        "detection_enabled": "BOOLEAN DEFAULT 1",
        "last_online_at": "DATETIME",
        "last_offline_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    
    with engine.begin() as conn:
        try:
            rows = conn.exec_driver_sql("PRAGMA table_info(cameras)").fetchall()
        except AttributeError:
            rows = conn.execute("PRAGMA table_info(cameras)").fetchall()
        existing = {row[1] for row in rows}
        for column_name, ddl in required_columns_cameras.items():
            if column_name not in existing:
                _execute_ddl(conn, f"ALTER TABLE cameras ADD COLUMN {column_name} {ddl}")
    
    # 更新alerts表
    required_columns_alerts = {
        "updated_at": "DATETIME",
    }
    
    with engine.begin() as conn:
        try:
            rows = conn.exec_driver_sql("PRAGMA table_info(alerts)").fetchall()
        except AttributeError:
            rows = conn.execute("PRAGMA table_info(alerts)").fetchall()
        existing = {row[1] for row in rows}
        for column_name, ddl in required_columns_alerts.items():
            if column_name not in existing:
                _execute_ddl(conn, f"ALTER TABLE alerts ADD COLUMN {column_name} {ddl}")


def init_db():
    try:
        database_log.info("开始初始化数据库表...")
        Base.metadata.create_all(bind=engine)
        database_log.info("数据库表创建完成")
        
        database_log.info("开始确保告警表结构完整...")
        _ensure_alert_schema()
        database_log.info("告警表结构检查完成")
        
        database_log.info("开始确保其他表结构完整...")
        _ensure_schema_updates()
        database_log.info("其他表结构检查完成")
    except Exception as e:
        database_log.error(f"数据库表创建/迁移失败: {e}")
        raise

    db = SessionLocal()
    try:
        from utils.auth_utils import get_password_hash

        database_log.info("检查管理员账号是否存在...")
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            database_log.info("创建默认管理员账号...")
            admin = User(
                username="admin",
                email="admin@kitchen-ai.com",
                hashed_password=get_password_hash("admin123"),
                company_name="Kitchen AI",
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            database_log.info("默认管理员账号创建成功")
        else:
            database_log.info("管理员账号已存在")
    except Exception as e:
        database_log.error(f"初始化管理员账号失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()




def optimize_database():
    if "sqlite" in DATABASE_URL:
        with engine.connect() as conn:
            _execute_ddl(conn, "PRAGMA optimize")
            _execute_ddl(conn, "PRAGMA analysis_limit=1000")
            _execute_ddl(conn, "PRAGMA cache_size=-2000")
