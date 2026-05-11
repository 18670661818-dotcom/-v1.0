"""认证API集成测试"""
import pytest


def test_register_user(client):
    """测试用户注册"""
    response = client.post("/api/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123",
        "company_name": "New Company"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user_info"]["username"] == "newuser"


def test_register_duplicate_username(client, test_user):
    """测试重复用户名注册"""
    response = client.post("/api/auth/register", json={
        "username": "testuser",  # 已存在的用户名
        "email": "different@example.com",
        "password": "password123",
        "company_name": "Different Company"
    })
    
    assert response.status_code == 400
    assert "用户名已存在" in response.json()["detail"]


def test_register_duplicate_email(client, test_user):
    """测试重复邮箱注册"""
    response = client.post("/api/auth/register", json={
        "username": "differentuser",
        "email": "test@example.com",  # 已存在的邮箱
        "password": "password123",
        "company_name": "Different Company"
    })
    
    assert response.status_code == 400
    assert "邮箱已注册" in response.json()["detail"]


def test_login_success(client, test_user):
    """测试登录成功"""
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    """测试错误密码登录"""
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


def test_login_nonexistent_user(client):
    """测试不存在用户登录"""
    response = client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "password123"
    })
    
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


def test_get_current_user(client, user_headers):
    """测试获取当前用户信息"""
    response = client.get("/api/auth/me", headers=user_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_get_current_user_without_token(client):
    """测试未认证获取用户信息"""
    response = client.get("/api/auth/me")
    
    assert response.status_code == 403  # 未提供令牌


def test_change_password(client, user_headers):
    """测试修改密码"""
    response = client.post(
        "/api/auth/change-password",
        params={"old_password": "testpass", "new_password": "newpass123"},
        headers=user_headers
    )
    
    assert response.status_code == 200
    assert "密码修改成功" in response.json()["message"]


def test_change_password_wrong_old(client, user_headers):
    """测试错误旧密码修改密码"""
    response = client.post(
        "/api/auth/change-password",
        params={"old_password": "wrongpass", "new_password": "newpass123"},
        headers=user_headers
    )
    
    assert response.status_code == 400
    assert "原密码错误" in response.json()["detail"]