"""配置API集成测试"""
import pytest


def test_create_config(client, admin_headers):
    """测试创建配置"""
    response = client.post("/api/config/", json={
        "key": "test_config",
        "value": "test_value",
        "value_type": "string",
        "description": "测试配置",
        "category": "test",
        "is_public": True
    }, headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "配置创建成功" in data["message"]


def test_get_config(client, admin_headers, test_config):
    """测试获取配置"""
    response = client.get(f"/api/config/{test_config.key}", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == test_config.key
    assert data["value"] == test_config.get_typed_value()


def test_update_config(client, admin_headers, test_config):
    """测试更新配置"""
    response = client.put(f"/api/config/{test_config.key}", json={
        "value": "updated_value",
        "description": "更新后的配置"
    }, headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "配置更新成功" in data["message"]


def test_delete_config(client, admin_headers, test_config):
    """测试删除配置"""
    response = client.delete(f"/api/config/{test_config.key}", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "配置已删除" in data["message"]


def test_list_configs(client, admin_headers, test_config):
    """测试获取配置列表"""
    response = client.get("/api/config/", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_configs_by_category(client, admin_headers, test_config):
    """测试按类别获取配置"""
    response = client.get(f"/api/config/category/{test_config.category}", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_unauthorized_config_access(client):
    """测试未授权访问配置"""
    response = client.get("/api/config/")
    
    assert response.status_code == 403  # 未提供令牌


def test_non_admin_config_creation(client, user_headers):
    """测试非管理员创建配置"""
    response = client.post("/api/config/", json={
        "key": "user_config",
        "value": "user_value",
        "value_type": "string",
        "description": "用户配置",
        "category": "user",
        "is_public": False
    }, headers=user_headers)
    
    assert response.status_code == 403  # 权限不足


def test_config_value_types(client, admin_headers):
    """测试配置值类型"""
    # 整数类型
    response = client.post("/api/config/", json={
        "key": "int_config",
        "value": 123,
        "value_type": "integer"
    }, headers=admin_headers)
    assert response.status_code == 200
    
    # 布尔类型
    response = client.post("/api/config/", json={
        "key": "bool_config",
        "value": True,
        "value_type": "boolean"
    }, headers=admin_headers)
    assert response.status_code == 200
    
    # JSON类型
    response = client.post("/api/config/", json={
        "key": "json_config",
        "value": {"key": "value"},
        "value_type": "json"
    }, headers=admin_headers)
    assert response.status_code == 200