"""更新告警记录的alert_id字段"""
import sys
import os
import uuid
import sqlite3

def update_alert_ids():
    """为所有没有alert_id的告警记录生成UUID"""
    # 直接连接数据库文件
    db_path = 'backend/kitchen_ai.db'

    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 查找所有没有alert_id的告警记录
        cursor.execute("SELECT id FROM alerts WHERE alert_id IS NULL")
        alerts_without_id = cursor.fetchall()

        if not alerts_without_id:
            print("所有告警记录都已有alert_id")
            return

        print(f"找到 {len(alerts_without_id)} 条没有alert_id的告警记录")

        # 为每条记录生成UUID
        for alert_id_tuple in alerts_without_id:
            alert_id = alert_id_tuple[0]
            new_uuid = str(uuid.uuid4())
            cursor.execute("UPDATE alerts SET alert_id = ? WHERE id = ?", (new_uuid, alert_id))
            print(f"已更新告警 ID={alert_id}, alert_id={new_uuid}")

        # 提交更改
        conn.commit()
        print(f"成功更新 {len(alerts_without_id)} 条告警记录")

        # 验证更新结果
        cursor.execute("SELECT id, alert_id FROM alerts LIMIT 5")
        updated_alerts = cursor.fetchall()
        print("\n验证更新结果:")
        for alert in updated_alerts:
            print(f"  - id={alert[0]}, alert_id={alert[1]}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_alert_ids()