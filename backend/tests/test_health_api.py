"""Test health check API."""
import os
import sys
import requests
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000"


def test_health_check():
    """Test simple health check endpoint."""
    print("Testing GET /health endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nResponse:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 验证响应格式
            required_fields = ["backend", "database", "camera_service", "inference_service", "websocket", "timestamp"]
            for field in required_fields:
                if field not in data:
                    print(f"✗ Missing required field: {field}")
                    return False
            
            print("\n✓ All required fields present")
            
            # 验证数据库状态
            if data["database"] == "ok":
                print("✓ Database is healthy")
            else:
                print(f"✗ Database issue: {data['database']}")
            
            # 验证时间戳格式
            try:
                from datetime import datetime
                datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
                print("✓ Timestamp format is correct")
            except ValueError:
                print(f"✗ Invalid timestamp format: {data['timestamp']}")
            
            return True
        else:
            print(f"✗ Request failed with status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Make sure the backend is running.")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_health_detailed():
    """Test detailed health check endpoint."""
    print("\nTesting GET /health/detailed endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/health/detailed")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nResponse:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 验证响应格式
            if "status" in data and "timestamp" in data and "components" in data:
                print("✓ Response format is correct")
                return True
            else:
                print("✗ Missing required fields in response")
                return False
        else:
            print(f"✗ Request failed with status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Make sure the backend is running.")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Health Check API Test")
    print("=" * 60)
    
    # 测试简单健康检查
    simple_ok = test_health_check()
    
    # 测试详细健康检查
    detailed_ok = test_health_detailed()
    
    print("\n" + "=" * 60)
    if simple_ok and detailed_ok:
        print("All tests passed!")
    else:
        print("Some tests failed!")
    print("=" * 60)