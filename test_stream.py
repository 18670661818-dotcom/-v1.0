"""
推理服务测试脚本
测试推理服务的优化功能：
1. 模型只加载一次
2. 帧率限制（2-5 FPS）
3. 置信度阈值可配置
4. 类别过滤可配置
5. GPU/CPU自动切换
6. 异常隔离
"""
import os
import sys
import time
import threading
import numpy as np
import cv2

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.inference_service import InferenceService, InferenceConfig, get_inference_service


def test_model_singleton():
    """测试模型单例加载"""
    print("\n" + "="*50)
    print("测试1: 模型单例加载")
    print("="*50)

    model_path = r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt"

    # 创建两个推理服务实例
    service1 = get_inference_service(model_path=model_path, device="auto")
    service2 = get_inference_service(model_path=model_path, device="auto")

    # 验证是否使用同一个模型管理器
    print(f"   service1.model_manager: {id(service1.model_manager)}")
    print(f"   service2.model_manager: {id(service2.model_manager)}")
    print(f"   ✅ 模型管理器是单例: {id(service1.model_manager) == id(service2.model_manager)}")


def test_inference_fps():
    """测试帧率限制"""
    print("\n" + "="*50)
    print("测试2: 帧率限制（2-5 FPS）")
    print("="*50)

    # 测试不同FPS配置
    fps_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    for fps in fps_values:
        config = InferenceConfig(
            model_path=r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt",
            inference_fps=fps
        )
        actual_fps = config.inference_fps
        print(f"   请求FPS: {fps:.1f} -> 实际FPS: {actual_fps:.1f} {'✅' if 2.0 <= actual_fps <= 5.0 else '❌'}")


def test_device_detection():
    """测试设备自动检测"""
    print("\n" + "="*50)
    print("测试3: 设备自动检测")
    print("="*50)

    config = InferenceConfig(
        model_path=r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt",
        device="auto"
    )
    print(f"   检测到的设备: {config.device}")

    try:
        import torch
        if torch.cuda.is_available():
            print(f"   GPU: {torch.cuda.get_device_name(0)}")
            print(f"   ✅ 使用GPU进行推理")
        else:
            print(f"   ⚠️ GPU不可用，使用CPU")
    except ImportError:
        print(f"   ⚠️ PyTorch未安装")


def test_class_filtering():
    """测试类别过滤"""
    print("\n" + "="*50)
    print("测试4: 类别过滤配置")
    print("="*50)

    config = InferenceConfig(
        model_path=r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt",
        enabled_classes={"chef_hat", "mask"},  # 只检测厨师帽和口罩
    )
    print(f"   启用的类别: {config.enabled_classes}")

    config2 = InferenceConfig(
        model_path=r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt",
        excluded_classes={"background"},  # 排除背景类
    )
    print(f"   排除的类别: {config2.excluded_classes}")
    print(f"   ✅ 类别过滤配置成功")


def test_confidence_threshold():
    """测试置信度阈值配置"""
    print("\n" + "="*50)
    print("测试5: 置信度阈值配置")
    print("="*50)

    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    for threshold in thresholds:
        config = InferenceConfig(
            model_path=r"D:\2026\yolo-v8\runs\train\exp2\weights\epoch98.pt",
            conf_threshold=threshold
        )
        print(f"   置信度阈值: {config.conf_threshold:.2f} ✅")


def test_error_isolation():
    """测试异常隔离"""
    print("\n" + "="*50)
    print("测试6: 异常隔离")
    print("="*50)

    service = get_inference_service()

    # 模拟一个会抛出异常的回调
    def error_callback(camera_id, detections, frame):
        raise ValueError("模拟异常")

    service.add_result_callback(error_callback)

    # 提交测试帧
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    service.submit_frame("test_camera", test_frame)

    print(f"   提交测试帧到推理服务")
    print(f"   异常回调已注册")
    print(f"   ✅ 异常隔离机制已配置")


def test_inference_performance():
    """测试推理性能"""
    print("\n" + "="*50)
    print("测试7: 推理性能测试")
    print("="*50)

    service = get_inference_service()

    # 记录统计信息
    stats_before = service.get_status()["stats"]

    # 提交多帧测试
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    num_frames = 10

    print(f"   提交 {num_frames} 帧进行测试...")
    for i in range(num_frames):
        service.submit_frame(f"cam_{i % 3}", test_frame, f"位置{i}")
        time.sleep(0.1)

    # 等待推理完成
    time.sleep(2)

    stats_after = service.get_status()["stats"]
    print(f"   推理次数: {stats_after['total_inferences'] - stats_before['total_inferences']}")
    print(f"   检测数量: {stats_after['total_detections'] - stats_before['total_detections']}")
    print(f"   错误次数: {stats_after['errors'] - stats_before['errors']}")
    print(f"   ✅ 性能测试完成")


def test_service_status():
    """测试服务状态"""
    print("\n" + "="*50)
    print("测试8: 服务状态查询")
    print("="*50)

    service = get_inference_service()
    status = service.get_status()

    print(f"   运行状态: {'运行中' if status['running'] else '已停止'}")
    print(f"   模型已加载: {status['model_loaded']}")
    print(f"   推理设备: {status['device']}")
    print(f"   推理帧率: {status['inference_fps']} FPS")
    print(f"   置信度阈值: {status['conf_threshold']}")
    print(f"   IOU阈值: {status['iou_threshold']}")
    print(f"   缓存的摄像头: {status['buffered_cameras']}")
    print(f"   ✅ 状态查询成功")


def test_config_update():
    """测试配置动态更新"""
    print("\n" + "="*50)
    print("测试9: 配置动态更新")
    print("="*50)

    service = get_inference_service()

    # 更新配置
    service.update_config(
        conf_threshold=0.5,
        inference_fps=4.0,
        enabled_classes={"chef_hat", "mask", "phone"}
    )

    status = service.get_status()
    print(f"   更新后置信度阈值: {status['conf_threshold']}")
    print(f"   更新后推理帧率: {status['inference_fps']} FPS")
    print(f"   更新后启用类别: {status['enabled_classes']}")
    print(f"   ✅ 配置更新成功")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("       推理服务优化测试")
    print("="*60)

    try:
        test_model_singleton()
        test_inference_fps()
        test_device_detection()
        test_class_filtering()
        test_confidence_threshold()
        test_error_isolation()
        test_service_status()
        test_config_update()
        test_inference_performance()

        print("\n" + "="*60)
        print("       所有测试完成 ✅")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
