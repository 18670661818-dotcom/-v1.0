"""
RTSP流批量测试工具
功能：
1. 单路/批量测试RTSP流连通性
2. 获取流信息（分辨率、帧率、编码格式）
3. 导出测试报告
"""
import os
import sys
import json
import time
import subprocess
import threading
import queue
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class RTSPTestResult:
    """单路测试结果"""
    camera_id: str
    rtsp_url: str
    success: bool
    # 流信息
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    bitrate: Optional[str] = None
    # 性能指标
    connect_time_ms: float = 0
    first_frame_time_ms: float = 0
    # 错误信息
    error_message: str = ""
    # 测试时间
    test_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class RTSPTester:
    """RTSP流测试器"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True, timeout=5
            )
            print("✅ FFmpeg 可用")
        except Exception as e:
            print(f"❌ FFmpeg 不可用: {e}")
            print("请确保FFmpeg已安装并添加到PATH")
            sys.exit(1)
    
    def test_single_rtsp(
        self, 
        camera_id: str, 
        rtsp_url: str, 
        timeout: int = 10,
        capture_frame: bool = True
    ) -> RTSPTestResult:
        """
        测试单个RTSP流
        
        Args:
            camera_id: 摄像头ID
            rtsp_url: RTSP流地址
            timeout: 超时时间(秒)
            capture_frame: 是否抓取一帧验证
        
        Returns:
            RTSPTestResult: 测试结果
        """
        result = RTSPTestResult(camera_id=camera_id, rtsp_url=rtsp_url, success=False)
        
        start_time = time.time()
        
        try:
            # ========== 步骤1：使用ffprobe探测流信息 ==========
            stream_info = self._probe_stream(rtsp_url, timeout)
            
            if stream_info is None:
                result.error_message = "无法获取流信息（可能是RTSP地址错误或摄像头离线）"
                return result
            
            # 解析流信息
            video_stream = None
            for stream in stream_info.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break
            
            if video_stream is None:
                result.error_message = "未找到视频流"
                return result
            
            result.width = video_stream.get("width")
            result.height = video_stream.get("height")
            result.codec = video_stream.get("codec_name")
            
            # 解析帧率（可能是分数形式 "30/1"）
            fps_str = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = fps_str.split("/")
                result.fps = round(float(num) / float(den), 2) if int(den) > 0 else 0
            except:
                result.fps = 0
            
            # 比特率
            bitrate = stream_info.get("format", {}).get("bit_rate")
            if bitrate:
                result.bitrate = f"{int(bitrate) / 1000:.0f} kbps"
            
            # 计算连接时间
            result.connect_time_ms = round((time.time() - start_time) * 1000, 1)
            
            # ========== 步骤2：尝试抓取一帧验证可播放 ==========
            if capture_frame:
                frame_result = self._capture_frame(rtsp_url, timeout)
                if frame_result:
                    result.first_frame_time_ms = frame_result
                    result.success = True
                else:
                    result.error_message = "流信息正常但无法抓取帧（可能是权限问题或网络延迟高）"
            else:
                result.success = True
            
        except subprocess.TimeoutExpired:
            result.error_message = f"连接超时（>{timeout}秒）"
            result.connect_time_ms = timeout * 1000
        
        except Exception as e:
            result.error_message = f"测试异常: {str(e)}"
        
        return result
    
    def _probe_stream(self, rtsp_url: str, timeout: int) -> Optional[dict]:
        """使用ffprobe探测流信息"""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            "-rtsp_transport", "tcp",  # TCP更稳定
            "-timeout", str(timeout * 1000000),  # 微秒
            rtsp_url
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout + 5,
                text=True
            )
            
            if proc.returncode != 0:
                # 尝试UDP传输
                cmd.remove("-rtsp_transport")
                cmd.remove("tcp")
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=timeout + 5,
                    text=True
                )
                
                if proc.returncode != 0:
                    return None
            
            return json.loads(proc.stdout)
            
        except Exception:
            return None
    
    def _capture_frame(self, rtsp_url: str, timeout: int) -> Optional[float]:
        """抓取一帧并计算首帧时间"""
        start_time = time.time()
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-vframes", "1",
            "-f", "null",
            "-"
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout + 5,
                text=True
            )
            
            if proc.returncode == 0:
                return round((time.time() - start_time) * 1000, 1)
            
        except subprocess.TimeoutExpired:
            pass
        
        return None
    
    def test_batch(
        self,
        camera_configs: Dict[str, str],
        max_workers: int = 10,
        timeout: int = 10,
        capture_frame: bool = True,
        progress_callback=None
    ) -> List[RTSPTestResult]:
        """
        批量测试RTSP流（多线程并发）
        
        Args:
            camera_configs: {camera_id: rtsp_url, ...}
            max_workers: 最大并发数
            timeout: 单路超时时间
            capture_frame: 是否抓帧验证
            progress_callback: 进度回调函数
        
        Returns:
            List[RTSPTestResult]: 所有测试结果
        """
        results = []
        total = len(camera_configs)
        completed = 0
        
        print(f"\n🔍 开始批量测试 {total} 路RTSP流...")
        print(f"   并发数: {max_workers}")
        print(f"   超时时间: {timeout}秒")
        print(f"   抓帧验证: {'是' if capture_frame else '否'}")
        print("-" * 80)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_camera = {}
            for camera_id, rtsp_url in camera_configs.items():
                future = executor.submit(
                    self.test_single_rtsp, 
                    camera_id, 
                    rtsp_url, 
                    timeout,
                    capture_frame
                )
                future_to_camera[future] = camera_id
            
            # 处理完成的任务
            for future in as_completed(future_to_camera):
                camera_id = future_to_camera[future]
                completed += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # 打印进度
                    status = "✅" if result.success else "❌"
                    info = ""
                    if result.success:
                        info = f"| {result.width}x{result.height} | {result.fps}fps | {result.codec}"
                    print(f"[{completed:3d}/{total}] {status} {camera_id} {info}")
                    
                    if progress_callback:
                        progress_callback(completed, total, result)
                        
                except Exception as e:
                    failed_result = RTSPTestResult(
                        camera_id=camera_id,
                        rtsp_url=camera_configs[camera_id],
                        success=False,
                        error_message=str(e)
                    )
                    results.append(failed_result)
                    print(f"[{completed:3d}/{total}] ❌ {camera_id} | 异常: {e}")
        
        return results
    
    def generate_report(
        self, 
        results: List[RTSPTestResult], 
        output_dir: str = "test_reports"
    ) -> str:
        """生成测试报告"""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 统计信息
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        
        # 成功的流信息
        success_results = [r for r in results if r.success]
        resolutions = {}
        codecs = {}
        avg_connect_time = 0
        avg_first_frame_time = 0
        
        if success_results:
            for r in success_results:
                res = f"{r.width}x{r.height}"
                resolutions[res] = resolutions.get(res, 0) + 1
                codecs[r.codec] = codecs.get(r.codec, 0) + 1
            avg_connect_time = sum(r.connect_time_ms for r in success_results) / len(success_results)
            avg_first_frame_time = sum(r.first_frame_time_ms for r in success_results) / len(success_results)
        
        # 失败的流
        failed_results = [r for r in results if not r.success]
        error_types = {}
        for r in failed_results:
            error_key = r.error_message[:50] if r.error_message else "未知错误"
            error_types[error_key] = error_types.get(error_key, 0) + 1
        
        # ========== 生成JSON报告 ==========
        json_report = {
            "test_time": timestamp,
            "summary": {
                "total": total,
                "success": success,
                "failed": failed,
                "success_rate": f"{success/total*100:.1f}%",
                "avg_connect_time_ms": round(avg_connect_time, 1),
                "avg_first_frame_time_ms": round(avg_first_frame_time, 1),
                "resolutions": resolutions,
                "codecs": codecs,
                "error_types": error_types,
            },
            "details": [asdict(r) for r in results]
        }
        
        json_path = os.path.join(output_dir, f"rtsp_test_report_{timestamp}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_report, f, ensure_ascii=False, indent=2)
        
        # ========== 生成HTML报告 ==========
        html_content = self._generate_html_report(json_report, timestamp)
        html_path = os.path.join(output_dir, f"rtsp_test_report_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"\n📊 报告已生成:")
        print(f"   JSON: {json_path}")
        print(f"   HTML: {html_path}")
        
        return html_path
    
    def _generate_html_report(self, report: dict, timestamp: str) -> str:
        """生成HTML格式报告"""
        summary = report["summary"]
        details = report["details"]
        
        # 构建详情表格
        table_rows = ""
        for r in details:
            status_color = "#4CAF50" if r["success"] else "#f44336"
            status_text = "✅ 正常" if r["success"] else "❌ 失败"
            
            resolution = f"{r['width']}x{r['height']}" if r["success"] else "-"
            fps = f"{r['fps']}fps" if r["success"] else "-"
            codec = r["codec"] or "-"
            connect_time = f"{r['connect_time_ms']}ms" if r["connect_time_ms"] else "-"
            error = r["error_message"] or "-"
            
            table_rows += f"""
            <tr>
                <td>{r['camera_id']}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;" title="{r['rtsp_url']}">{r['rtsp_url'][:50]}...</td>
                <td style="color:{status_color};font-weight:bold;">{status_text}</td>
                <td>{resolution}</td>
                <td>{fps}</td>
                <td>{codec}</td>
                <td>{connect_time}</td>
                <td style="color:#f44336;font-size:12px;">{error}</td>
            </tr>
            """
        
        # 错误类型统计
        error_stats = ""
        for error_type, count in summary["error_types"].items():
            error_stats += f"<li>{error_type}: <b>{count}</b>个</li>"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>RTSP流测试报告 - {timestamp}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; }}
                .container {{ max-width: 1400px; margin: 20px auto; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
                .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
                .header p {{ opacity: 0.9; }}
                .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; padding: 20px; background: white; }}
                .summary-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #667eea; }}
                .summary-card h3 {{ font-size: 14px; color: #666; margin-bottom: 8px; }}
                .summary-card .value {{ font-size: 32px; font-weight: bold; color: #333; }}
                .summary-card.success {{ border-left-color: #4CAF50; }}
                .summary-card.failed {{ border-left-color: #f44336; }}
                .stats {{ background: white; padding: 20px; margin-top: 1px; }}
                .stats h3 {{ margin-bottom: 15px; color: #333; }}
                .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .stats-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; }}
                .stats-box h4 {{ margin-bottom: 10px; color: #555; }}
                table {{ width: 100%; border-collapse: collapse; background: white; margin-top: 1px; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }}
                th {{ background: #f8f9fa; font-weight: bold; color: #555; position: sticky; top: 0; }}
                tr:hover {{ background: #f8f9fa; }}
                .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 RTSP流批量测试报告</h1>
                    <p>测试时间: {timestamp} | 后厨智能监测系统</p>
                </div>
                
                <div class="summary">
                    <div class="summary-card">
                        <h3>总计</h3>
                        <div class="value">{summary['total']}</div>
                    </div>
                    <div class="summary-card success">
                        <h3>成功</h3>
                        <div class="value" style="color:#4CAF50;">{summary['success']}</div>
                    </div>
                    <div class="summary-card failed">
                        <h3>失败</h3>
                        <div class="value" style="color:#f44336;">{summary['failed']}</div>
                    </div>
                    <div class="summary-card">
                        <h3>成功率</h3>
                        <div class="value">{summary['success_rate']}</div>
                    </div>
                </div>
                
                <div class="stats">
                    <div class="stats-grid">
                        <div class="stats-box">
                            <h4>📹 分辨率分布</h4>
                            <ul style="list-style:none;padding:0;">
                                {''.join(f'<li>• {k}: <b>{v}</b>路</li>' for k,v in summary.get('resolutions', {}).items()) or '<li>无数据</li>'}
                            </ul>
                        </div>
                        <div class="stats-box">
                            <h4>📊 平均耗时</h4>
                            <p>连接时间: <b>{summary.get('avg_connect_time_ms', 0)}ms</b></p>
                            <p>首帧时间: <b>{summary.get('avg_first_frame_time_ms', 0)}ms</b></p>
                        </div>
                        <div class="stats-box">
                            <h4>🎬 编码格式</h4>
                            <ul style="list-style:none;padding:0;">
                                {''.join(f'<li>• {k}: <b>{v}</b>路</li>' for k,v in summary.get('codecs', {}).items()) or '<li>无数据</li>'}
                            </ul>
                        </div>
                        <div class="stats-box">
                            <h4>⚠️ 错误类型</h4>
                            <ul style="list-style:none;padding:0;">
                                {error_stats or '<li>无错误</li>'}
                            </ul>
                        </div>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>摄像头ID</th>
                            <th>RTSP地址</th>
                            <th>状态</th>
                            <th>分辨率</th>
                            <th>帧率</th>
                            <th>编码</th>
                            <th>连接耗时</th>
                            <th>错误信息</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
                
                <div class="footer">
                    <p>后厨智能监测系统 | RTSP流测试工具 | 报告生成时间: {timestamp}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html


# ==================== 命令行入口 ====================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RTSP流批量测试工具")
    parser.add_argument(
        "-c", "--config", 
        type=str, 
        default="rtsp_config.json",
        help="RTSP配置文件路径（JSON格式）"
    )
    parser.add_argument(
        "-u", "--url",
        type=str,
        help="测试单个RTSP地址"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=10,
        help="并发测试线程数（默认10）"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=10,
        help="单路超时时间（秒，默认10）"
    )
    parser.add_argument(
        "--no-capture",
        action="store_true",
        help="不抓取帧验证（仅检查流信息）"
    )
    
    args = parser.parse_args()
    
    tester = RTSPTester()
    
    # 单路测试
    if args.url:
        print(f"\n🔍 测试单个RTSP流: {args.url}")
        result = tester.test_single_rtsp(
            "manual_test", 
            args.url, 
            timeout=args.timeout,
            capture_frame=not args.no_capture
        )
        
        print("\n" + "=" * 60)
        print(f"摄像头ID: {result.camera_id}")
        print(f"RTSP地址: {result.rtsp_url}")
        print(f"状态: {'✅ 正常' if result.success else '❌ 失败'}")
        if result.success:
            print(f"分辨率: {result.width}x{result.height}")
            print(f"帧率: {result.fps}fps")
            print(f"编码: {result.codec}")
            print(f"比特率: {result.bitrate}")
            print(f"连接耗时: {result.connect_time_ms}ms")
            print(f"首帧耗时: {result.first_frame_time_ms}ms")
        else:
            print(f"错误: {result.error_message}")
        print("=" * 60)
    
    # 批量测试
    else:
        # 加载配置
        if not os.path.exists(args.config):
            print(f"\n📝 配置文件不存在，创建示例配置: {args.config}")
            sample_config = {
                "cam_001": "rtsp://192.168.1.100:554/stream1",
                "cam_002": "rtsp://192.168.1.101:554/stream1",
                "cam_003": "rtsp://admin:123456@192.168.1.102:554/stream",
            }
            with open(args.config, "w") as f:
                json.dump(sample_config, f, indent=2, ensure_ascii=False)
            print("请修改配置文件中的RTSP地址后重新运行")
            sys.exit(0)
        
        with open(args.config, "r") as f:
            config = json.load(f)
        
        print(f"\n📋 加载了 {len(config)} 路摄像头配置")
        
        # 执行批量测试
        results = tester.test_batch(
            config,
            max_workers=args.workers,
            timeout=args.timeout,
            capture_frame=not args.no_capture
        )
        
        # 生成报告
        report_path = tester.generate_report(results)
        
        # 简要汇总
        success = sum(1 for r in results if r.success)
        total = len(results)
        print(f"\n📊 测试汇总:")
        print(f"   总数: {total}")
        print(f"   成功: {success}")
        print(f"   失败: {total - success}")
        print(f"   成功率: {success/total*100:.1f}%")