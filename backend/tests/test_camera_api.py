"""摄像头API集成测试"""
import pytest


def test_list_cameras(client, admin_headers, test_camera):
    """测试获取摄像头列表"""
    response = client.get("/api/cameras/", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_camera(client, admin_headers, test_camera):
    """测试获取摄像头详情"""
    response = client.get(f"/api/cameras/{test_camera.camera_id}", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == test_camera.camera_id
    assert data["name"] == test_camera.name


def test_create_camera(client, admin_headers):
    """测试创建摄像头"""
    response = client.post("/api/cameras/", json={
        "camera_id": "new_cam",
        "name": "新摄像头",
        "rtsp_url": "rtsp://test.com/new",
        "location": "新位置",
        "enabled": True
    }, headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "new_cam"
    assert data["name"] == "新摄像头"


def test_update_camera(client, admin_headers, test_camera):
    """测试更新摄像头"""
    response = client.put(f"/api/cameras/{test_camera.camera_id}", json={
        "name": "更新后的摄像头",
        "location": "更新后的位置"
    }, headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "更新后的摄像头"


def test_delete_camera(client, admin_headers, test_camera):
    """测试删除摄像头"""
    response = client.delete(f"/api/cameras/{test_camera.camera_id}", headers=admin_headers)
    
    assert response.status_code == 200
    assert "摄像头已删除" in response.json()["message"]


def test_get_camera_status_summary(client, admin_headers):
    """测试获取摄像头状态汇总"""
    response = client.get("/api/cameras/status/summary", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "online" in data
    assert "offline" in data


def test_unauthorized_camera_access(client):
    """测试未授权访问摄像头"""
    response = client.get("/api/cameras/")
    
    assert response.status_code == 403  # 未提供令牌


def test_non_admin_camera_creation(client, user_headers):
    """测试非管理员创建摄像头"""
    response = client.post("/api/cameras/", json={
        "camera_id": "user_cam",
        "name": "用户摄像头",
        "rtsp_url": "rtsp://test.com/user",
        "location": "用户位置",
        "enabled": True
    }, headers=user_headers)
    
    assert response.status_code == 403  # 权限不足