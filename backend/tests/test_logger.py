"""Test logger system functionality."""
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import (
    camera_log,
    inference_log,
    alert_log,
    database_log,
    request_logger,
    websocket_log,
    get_logger,
)


def test_logger_creation():
    """Test logger creation and basic functionality."""
    print("Testing logger creation...")
    
    # Test that all loggers are created
    assert camera_log is not None
    assert inference_log is not None
    assert alert_log is not None
    assert database_log is not None
    assert request_logger is not None
    assert websocket_log is not None
    
    # Test get_logger function
    test_logger = get_logger("test")
    assert test_logger is not None
    
    print("✓ All loggers created successfully")


def test_logger_writing():
    """Test logger writing to files."""
    print("\nTesting logger writing...")
    
    # Write test messages to each logger using their static methods
    test_camera_id = "test_camera_001"
    
    # Test camera logger
    camera_log.log_connect(test_camera_id, "rtsp://test.url/stream")
    camera_log.log_frame(test_camera_id, 100, 30.0)
    
    # Test inference logger
    inference_log.log_start(test_camera_id, "yolov8n.pt")
    inference_log.log_detection(test_camera_id, [{"class_name": "person"}])
    
    # Test alert logger
    alert_log.log_alert(test_camera_id, "no_helmet", 0.95, "alert_001")
    alert_log.log_confirm(1, "admin")
    
    # Test websocket logger
    websocket_log.log_connect("test_client_001", "127.0.0.1")
    websocket_log.log_message("test_client_001", "subscribe")
    
    # Test request logger
    request_logger.log_request("GET", "/api/cameras", "127.0.0.1", 200, 0.05)
    
    print("✓ Test messages written to all loggers")


def test_log_files_exist():
    """Test that log files are created."""
    print("\nTesting log file creation...")
    
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "logs")
    
    expected_files = [
        "camera.log",
        "inference.log",
        "alert.log",
        "error.log",
        "websocket.log",
        "requests.log",
    ]
    
    for filename in expected_files:
        filepath = os.path.join(log_dir, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"✓ {filename} exists ({size} bytes)")
        else:
            print(f"✗ {filename} does not exist")


def test_logger_levels():
    """Test different log levels."""
    print("\nTesting log levels...")
    
    # 使用get_logger获取一个测试logger
    test_logger = get_logger("test_levels")
    
    test_logger.debug("Debug level test")
    test_logger.info("Info level test")
    test_logger.warning("Warning level test")
    test_logger.error("Error level test")
    
    print("✓ All log levels tested")


if __name__ == "__main__":
    print("=" * 50)
    print("Logger System Test")
    print("=" * 50)
    
    test_logger_creation()
    test_logger_writing()
    test_log_files_exist()
    test_logger_levels()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)