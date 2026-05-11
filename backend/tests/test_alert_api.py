"""告警API集成测试"""
import pytest


def test_list_alerts(client, admin_headers, test_alert):
    """测试获取告警列表"""
    response = client.get("/api/alerts/", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_alert_stats(client, admin_headers):
    """测试获取告警统计"""
    response = client.get("/api/alerts/stats", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_status" in data
    assert "by_type" in data
    assert "pending" in data
    assert "confirmed" in data
    assert "resolved" in data
    assert "false_positive" in data


def test_acknowledge_alerts(client, admin_headers, test_alert):
    """测试确认告警"""
    response = client.post("/api/alerts/acknowledge", json={
        "alert_ids": [test_alert.alert_id]
    }, headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "已确认" in data["message"]


def test_get_alert_image(client, admin_headers, test_alert):
    """测试获取告警图片（模拟不存在）"""
    response = client.get(f"/api/alerts/image/{test_alert.alert_id}", headers=admin_headers)
    
    # 由于测试环境没有图片文件，应该返回404
    assert response.status_code == 404


def test_unauthorized_alert_access(client):
    """测试未授权访问告警"""
    response = client.get("/api/alerts/")
    
    assert response.status_code == 403  # 未提供令牌


def test_alert_pagination(client, admin_headers):
    """测试告警分页"""
    response = client.get("/api/alerts/?page=1&page_size=5", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 5


def test_alert_filtering(client, admin_headers, test_alert):
    """测试告警过滤"""
    # 按摄像头ID过滤
    response = client.get(f"/api/alerts/?camera_id={test_alert.camera_id}", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    # 应该返回该摄像头的告警


def test_alert_stats_caching(client, admin_headers):
    """测试告警统计缓存"""
    # 第一次请求
    response1 = client.get("/api/alerts/stats", headers=admin_headers)
    assert response1.status_code == 200
    
    # 第二次请求（应该从缓存返回）
    response2 = client.get("/api/alerts/stats", headers=admin_headers)
    assert response2.status_code == 200
    
    # 两次响应应该相同
    assert response1.json() == response2.json()