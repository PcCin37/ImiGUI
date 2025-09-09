#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI-TARS多设备自动化流程启动器
Author: Pengchen Chen
Date: 2025-01-16
适用于所有平台 (Windows/macOS/Linux)
支持多设备并发测试
"""

import os
import sys
import subprocess
import importlib.util
import argparse
from pathlib import Path
import threading
import time
from datetime import datetime

def check_package(package_name, install_command=None):
    """检查Python包是否已安装"""
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        print(f"❌ 错误: 请安装 {package_name}")
        if install_command:
            print(f"安装命令: {install_command}")
        return False
    return True

def get_connected_devices():
    """获取所有已连接的ADB设备"""
    try:
        # 检查ADB命令是否存在
        subprocess.run(['adb', 'version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ 错误: 未找到ADB命令")
        return []
    
    try:
        # 获取设备列表
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=True)
        devices = []
        for line in result.stdout.strip().split('\n')[1:]:
            if line.strip() and '\t' in line:
                device_id, status = line.strip().split('\t')
                if status == 'device':
                    devices.append(device_id)
        
        return devices
        
    except subprocess.CalledProcessError:
        print("❌ 错误: ADB命令执行失败")
        return []

def validate_device(device_id):
    """验证指定设备是否连接且可用"""
    connected_devices = get_connected_devices()
    return device_id in connected_devices

def create_device_output_dir(base_output_dir, device_id):
    """为指定设备创建输出目录"""
    device_safe_id = device_id.replace(':', '_').replace('.', '_')
    device_output_dir = Path(base_output_dir) / f"device_{device_safe_id}"
    
    # 创建设备专用目录
    device_output_dir.mkdir(parents=True, exist_ok=True)
    (device_output_dir / "screenshots" / "img").mkdir(parents=True, exist_ok=True)
    (device_output_dir / "screenshots" / "outputs").mkdir(parents=True, exist_ok=True)
    (device_output_dir / "test_task").mkdir(parents=True, exist_ok=True)
    
    return str(device_output_dir)

def run_uitars_for_device(device_id, output_dir, task_description=None, csv_file=None):
    """为指定设备运行UI-TARS自动化流程"""
    print(f"🚀 [设备 {device_id}] 开始执行UI-TARS自动化流程...")
    
    try:
        # 设置环境变量
        env = os.environ.copy()
        env['UITARS_DEVICE_ID'] = device_id
        env['UITARS_OUTPUT_DIR'] = output_dir
        if task_description:
            env['UITARS_TASK_DESC'] = task_description
        if csv_file:
            env['UITARS_CSV_FILE'] = csv_file
        
        # 切换到输出目录
        original_cwd = os.getcwd()
        os.chdir(output_dir)
        
        # 导入并运行主程序
        import final_uitars
        
        # 调用main函数并传递设备ID参数
        final_uitars.main(device_id=device_id)
        
        print(f"✅ [设备 {device_id}] UI-TARS自动化流程执行完成！")
        
    except ImportError as e:
        print(f"❌ [设备 {device_id}] 错误: 无法导入final_uitars模块: {e}")
    except KeyboardInterrupt:
        print(f"\n⏹️ [设备 {device_id}] 用户中断程序执行")
    except Exception as e:
        print(f"❌ [设备 {device_id}] 程序执行出错: {e}")
    finally:
        # 恢复原始工作目录
        os.chdir(original_cwd)

def main():
    parser = argparse.ArgumentParser(
        description='UI-TARS多设备自动化流程启动器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 列出所有连接的设备
  python run_multi_device.py --list-devices
  
  # 为指定设备运行测试
  python run_multi_device.py --device emulator-5554 --output ./output
  
  # 为多个设备并发运行测试
  python run_multi_device.py --device emulator-5554 --device emulator-5556 --output ./output
  
  # 为所有连接的设备运行测试
  python run_multi_device.py --all-devices --output ./output
  
  # 使用CSV文件批量执行任务
  python run_multi_device.py --device emulator-5554 --csv tasks.csv --output ./output
  
  # 为多个设备并发执行CSV批量任务
  python run_multi_device.py --all-devices --csv tasks.csv --concurrent --output ./output
        """
    )
    
    parser.add_argument('--device', '-d', action='append', dest='devices',
                       help='指定设备ID（可多次使用以指定多个设备）')
    parser.add_argument('--all-devices', '-a', action='store_true',
                       help='为所有连接的设备运行测试')
    parser.add_argument('--output', '-o', default='./multi_device_output',
                       help='输出目录基路径（默认: ./multi_device_output）')
    parser.add_argument('--task', '-t',
                       help='任务描述（可选）')
    parser.add_argument('--csv', '-csv',
                       help='CSV任务文件路径（用于批量任务执行）')
    parser.add_argument('--list-devices', '-l', action='store_true',
                       help='列出所有连接的设备')
    parser.add_argument('--concurrent', '-c', action='store_true',
                       help='并发执行多设备测试（默认为顺序执行）')
    
    args = parser.parse_args()
    
    print("🚀 UI-TARS多设备GUI自动化流程启动器")
    print("====================================")
    
    # 检查ARK_API_KEY环境变量
    if not os.environ.get('ARK_API_KEY'):
        print("❌ 错误: 请先设置ARK_API_KEY环境变量")
        print("设置方法:")
        if os.name == 'nt':  # Windows
            print("  set ARK_API_KEY=your_api_key")
        else:  # Unix/Linux/macOS
            print("  export ARK_API_KEY=\"your_api_key\"")
        sys.exit(1)
    
    # 检查Python版本
    if sys.version_info < (3, 6):
        print("❌ 错误: 需要Python 3.6或更高版本")
        sys.exit(1)
    
    # 检查依赖包
    print("🔍 检查依赖包...")
    checks = [
        ("volcenginesdkarkruntime", "pip install volcengine-python-sdk[ark]"),
        ("PIL", "pip install Pillow"),
        ("json", None),  # 标准库
        ("datetime", None),  # 标准库
    ]
    
    all_good = True
    for package, install_cmd in checks:
        if not check_package(package, install_cmd):
            all_good = False
    
    if not all_good:
        print("❌ 请先安装缺失的依赖包")
        sys.exit(1)
    
    # 获取连接的设备
    print("📱 检查ADB设备连接...")
    connected_devices = get_connected_devices()
    
    if not connected_devices:
        print("❌ 错误: 未检测到已连接的Android设备")
        print("请确保:")
        print("  1. 设备已连接到电脑")
        print("  2. 已启用USB调试")
        print("  3. 已授权此电脑进行调试")
        sys.exit(1)
    
    print(f"✅ 检测到 {len(connected_devices)} 个已连接的设备:")
    for i, device in enumerate(connected_devices, 1):
        print(f"  {i}. {device}")
    
    # 处理列出设备的请求
    if args.list_devices:
        print("\n📋 已连接的设备列表:")
        for device in connected_devices:
            print(f"  - {device}")
        return
    
    # 确定要使用的设备
    target_devices = []
    
    if args.all_devices:
        target_devices = connected_devices
        print(f"\n🎯 将为所有 {len(target_devices)} 个设备运行测试")
    elif args.devices:
        # 验证指定的设备
        for device in args.devices:
            if device in connected_devices:
                target_devices.append(device)
            else:
                print(f"⚠️ 警告: 设备 {device} 未连接，跳过")
        
        if not target_devices:
            print("❌ 错误: 没有有效的设备可用")
            sys.exit(1)
        
        print(f"\n🎯 将为指定的 {len(target_devices)} 个设备运行测试:")
        for device in target_devices:
            print(f"  - {device}")
    else:
        print("❌ 错误: 请指定设备或使用 --all-devices 选项")
        print("使用 --help 查看帮助信息")
        sys.exit(1)
    
    # 创建输出目录
    base_output_dir = Path(args.output)
    base_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 输出目录: {base_output_dir.absolute()}")
    
    # 为每个设备创建专用输出目录
    device_dirs = {}
    for device in target_devices:
        device_output_dir = create_device_output_dir(base_output_dir, device)
        device_dirs[device] = device_output_dir
        print(f"  📂 设备 {device}: {device_output_dir}")
    
    print("\n✅ 环境检查完成，开始执行UI-TARS自动化流程...")
    print("="*50)
    
    start_time = datetime.now()
    
    try:
        if args.concurrent and len(target_devices) > 1:
            # 并发执行
            print(f"🔄 并发模式: 同时为 {len(target_devices)} 个设备执行测试")
            threads = []
            
            for device in target_devices:
                thread = threading.Thread(
                    target=run_uitars_for_device,
                    args=(device, device_dirs[device], args.task, args.csv),
                    name=f"UITars-{device}"
                )
                threads.append(thread)
                thread.start()
                time.sleep(1)  # 错开启动时间，避免资源冲突
            
            # 等待所有线程完成
            for thread in threads:
                thread.join()
        else:
            # 顺序执行
            print(f"📋 顺序模式: 依次为 {len(target_devices)} 个设备执行测试")
            for i, device in enumerate(target_devices, 1):
                print(f"\n[{i}/{len(target_devices)}] 处理设备: {device}")
                run_uitars_for_device(device, device_dirs[device], args.task, args.csv)
                if i < len(target_devices):
                    print(f"⏳ 等待 2 秒后处理下一个设备...")
                    time.sleep(2)
    
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断程序执行")
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*50)
    print(f"🎉 多设备UI-TARS自动化流程执行完成！")
    print(f"⏱️ 总耗时: {duration}")
    print(f"📊 处理设备数: {len(target_devices)}")
    print(f"📁 输出目录: {base_output_dir.absolute()}")

if __name__ == "__main__":
    main()