#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI-TARS自动化流程启动器 (Python版本)
Author: Pengchen Chen
Date: 2025-07-26
适用于所有平台 (Windows/macOS/Linux)
"""

import os
import sys
import subprocess
import importlib.util

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

def check_adb():
    """检查ADB连接"""
    devices = get_connected_devices()
    
    if not devices:
        print("❌ 错误: 未检测到已连接的Android设备")
        print("请确保:")
        print("  1. 设备已连接到电脑")
        print("  2. 已启用USB调试")
        print("  3. 已授权此电脑进行调试")
        return False
    
    print(f"✅ 检测到 {len(devices)} 个已连接的设备:")
    for i, device in enumerate(devices, 1):
        print(f"  {i}. {device}")
    
    # 如果有多个设备，提示用户可以使用多设备脚本
    if len(devices) > 1:
        print("\n💡 提示: 检测到多个设备，您可以:")
        print("  - 继续使用当前脚本（将提供设备选择）")
        print("  - 使用 run_multi_device.py 进行多设备并发测试")
    
    return True

def main():
    print("🚀 UI-TARS GUI自动化流程启动器")
    print("================================")
    
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
    
    # 检查ADB连接
    print("📱 检查ADB设备连接...")
    if not check_adb():
        sys.exit(1)
    
    # 创建必要的目录
    print("📁 创建输出目录...")
    os.makedirs("screenshots/img", exist_ok=True)
    os.makedirs("screenshots/outputs", exist_ok=True)
    
    # 设备选择
    devices = get_connected_devices()
    selected_device = None
    
    if len(devices) == 1:
        selected_device = devices[0]
        print(f"🎯 自动选择唯一设备: {selected_device}")
    elif len(devices) > 1:
        print("\n📱 请选择要使用的设备:")
        for i, device in enumerate(devices, 1):
            print(f"  {i}. {device}")
        
        while True:
            try:
                choice = input("\n请输入设备序号 (1-{}) 或完整设备ID: ".format(len(devices))).strip()
                
                # 尝试作为序号解析
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(devices):
                        selected_device = devices[idx]
                        break
                    else:
                        print(f"❌ 无效序号，请输入 1-{len(devices)} 之间的数字")
                # 尝试作为完整设备ID解析
                elif choice in devices:
                    selected_device = choice
                    break
                else:
                    print("❌ 无效输入，请输入有效的序号或设备ID")
            except (ValueError, KeyboardInterrupt):
                print("\n⏹️ 用户取消选择")
                sys.exit(0)
        
        print(f"✅ 已选择设备: {selected_device}")
    
    # 启动主程序
    print("\n✅ 环境检查完成，启动UI-TARS自动化流程...")
    print("")
    
    try:
        # 导入并运行主程序
        import final_uitars
        final_uitars.main(device_id=selected_device)
    except ImportError as e:
        print(f"❌ 错误: 无法导入final_uitars模块: {e}")
        print("请确保在正确的目录中运行此脚本")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断程序执行")
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        sys.exit(1)
    
    print("")
    print("🎉 UI-TARS自动化流程执行完成！")

if __name__ == "__main__":
    main()