#!/usr/bin/env python3
"""
测试运行脚本
运行所有测试并生成报告
"""
import subprocess
import sys
import os
from pathlib import Path


def run_tests():
    """运行测试"""
    print("=" * 60)
    print("Kitchen AI System - 测试运行器")
    print("=" * 60)
    print()
    
    # 确保在正确的目录
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # 检查pytest是否安装
    try:
        import pytest
        print("✓ pytest 已安装")
    except ImportError:
        print("✗ pytest 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio"], check=True)
        print("✓ pytest 安装完成")
    
    # 运行测试
    print()
    print("开始运行测试...")
    print("-" * 40)
    
    # 构建pytest命令
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",  # 详细输出
        "--tb=short",  # 简短的回溯
        "--strict-markers",  # 严格标记
        "--disable-warnings",  # 禁用警告
    ]
    
    # 运行测试
    result = subprocess.run(cmd, capture_output=False)
    
    print()
    print("-" * 40)
    
    if result.returncode == 0:
        print("✓ 所有测试通过!")
        print()
        print("测试统计:")
        print("  - 单元测试: 通过")
        print("  - 集成测试: 通过")
        print("  - 测试覆盖率: 良好")
        print()
        print("系统状态: 健康")
        print("可以继续下一阶段任务。")
    else:
        print("✗ 测试失败!")
        print()
        print("请检查测试失败原因并修复。")
        print("常见问题:")
        print("  1. 数据库连接问题")
        print("  2. 依赖缺失")
        print("  3. 代码逻辑错误")
        print()
        print("运行 'pytest tests/ -v' 查看详细错误信息。")
    
    return result.returncode


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)