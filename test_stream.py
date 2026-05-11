"""测试视频流API"""
import requests
import time

def test_stream():
    base_url = "http://localhost:8000"

    # 首先获取token
    print("1. 尝试登录获取token...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }

    try:
        response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"   ✅ 登录成功，获取到token")

            # 获取摄像头列表
            print("\n2. 获取摄像头列表...")
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{base_url}/api/cameras/", headers=headers)
            if response.status_code == 200:
                cameras = response.json()
                print(f"   ✅ 获取到 {len(cameras)} 个摄像头")
                for cam in cameras:
                    print(f"      - {cam['camera_id']}: {cam['name']} ({cam['status']})")

                # 测试视频流
                if cameras:
                    print("\n3. 测试视频流API...")
                    cam_id = cameras[0]['camera_id']
                    print(f"   尝试获取摄像头 {cam_id} 的视频流...")
                    try:
                        response = requests.get(
                            f"{base_url}/api/stream/{cam_id}",
                            headers=headers,
                            stream=True,
                            timeout=5
                        )
                        if response.status_code == 200:
                            print(f"   ✅ 视频流API响应成功")
                            print(f"      Content-Type: {response.headers.get('Content-Type')}")
                        else:
                            print(f"   ❌ 视频流API返回状态码: {response.status_code}")
                    except requests.exceptions.Timeout:
                        print(f"   ⚠️ 视频流API超时（可能没有视频数据）")
                    except Exception as e:
                        print(f"   ❌ 视频流API错误: {e}")
                else:
                    print("   ⚠️ 没有摄像头配置")
            else:
                print(f"   ❌ 获取摄像头列表失败: {response.status_code}")
        else:
            print(f"   ❌ 登录失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")

if __name__ == "__main__":
    test_stream()
