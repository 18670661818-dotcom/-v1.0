"""Simple test for health check endpoint."""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_endpoint():
    """Test the /health endpoint."""
    print("Testing GET /health endpoint...")
    
    response = client.get("/health")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 验证响应格式
        required_fields = ["backend", "database", "camera_service", "inference_service", "websocket", "timestamp"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            print(f"\n✗ Missing required fields: {missing_fields}")
            print("Note: This might be the old endpoint from main.py")
            return False
        else:
            print("\n✓ All required fields present")
            print("✓ New health check endpoint is working!")
            return True
    else:
        print(f"✗ Request failed with status code: {response.status_code}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Health Check Endpoint Test")
    print("=" * 60)
    
    success = test_health_endpoint()
    
    print("\n" + "=" * 60)
    if success:
        print("Test passed!")
    else:
        print("Test failed - the old endpoint might still be active")
    print("=" * 60)