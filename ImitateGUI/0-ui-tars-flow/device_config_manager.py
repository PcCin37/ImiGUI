#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备配置管理器
用于加载和管理多设备配置文件
"""

import json
import os
import sys
from typing import Dict, List, Optional, Any

class DeviceConfigManager:
    """设备配置管理器"""
    
    def __init__(self, config_file: str = "device_config_template.json"):
        self.config_file = config_file
        self.config_data = None
        self.load_config()
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file):
                print(f"❌ 配置文件不存在: {self.config_file}")
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            print(f"✅ 成功加载配置文件: {self.config_file}")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ 配置文件JSON格式错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}")
            return False
    
    def get_enabled_devices(self) -> List[Dict[str, Any]]:
        """获取所有启用的设备配置"""
        if not self.config_data:
            return []
        
        enabled_devices = []
        for device in self.config_data.get('device_configs', []):
            if device.get('enabled', True):
                enabled_devices.append(device)
        
        # 按优先级排序
        enabled_devices.sort(key=lambda x: x.get('priority', 999))
        return enabled_devices
    
    def get_device_config(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取指定设备的配置"""
        if not self.config_data:
            return None
        
        for device in self.config_data.get('device_configs', []):
            if device.get('device_id') == device_id:
                return device
        
        return None
    
    def get_global_settings(self) -> Dict[str, Any]:
        """获取全局设置"""
        if not self.config_data:
            return {}
        
        return self.config_data.get('global_settings', {})
    
    def get_task_template(self, task_name: str) -> Optional[Dict[str, Any]]:
        """获取任务模板"""
        if not self.config_data:
            return None
        
        templates = self.config_data.get('task_templates', {})
        return templates.get(task_name)
    
    def list_devices(self) -> None:
        """列出所有设备配置"""
        devices = self.get_enabled_devices()
        
        if not devices:
            print("❌ 没有找到启用的设备配置")
            return
        
        print(f"📋 找到 {len(devices)} 个启用的设备配置:")
        for i, device in enumerate(devices, 1):
            status = "✅" if device.get('enabled', True) else "❌"
            print(f"  {i}. {status} {device.get('device_name', 'Unknown')} ({device.get('device_id', 'Unknown')})")
            print(f"     优先级: {device.get('priority', 'N/A')}")
            print(f"     输出目录: {device.get('output_dir', 'N/A')}")
            tasks = device.get('tasks', [])
            if tasks:
                print(f"     任务: {', '.join(tasks)}")
            print()
    
    def validate_device_ids(self, device_ids: List[str]) -> List[str]:
        """验证设备ID列表，返回有效的设备ID"""
        valid_devices = []
        configured_devices = {d.get('device_id') for d in self.get_enabled_devices()}
        
        for device_id in device_ids:
            if device_id in configured_devices:
                valid_devices.append(device_id)
            else:
                print(f"⚠️  设备 {device_id} 未在配置文件中找到或未启用")
        
        return valid_devices
    
    def create_output_directories(self, devices: List[str]) -> Dict[str, str]:
        """为指定设备创建输出目录"""
        output_dirs = {}
        
        for device_id in devices:
            device_config = self.get_device_config(device_id)
            if device_config:
                output_dir = device_config.get('output_dir', f'./outputs/{device_id}')
                # 确保目录存在
                os.makedirs(output_dir, exist_ok=True)
                os.makedirs(os.path.join(output_dir, 'screenshots'), exist_ok=True)
                os.makedirs(os.path.join(output_dir, 'logs'), exist_ok=True)
                output_dirs[device_id] = output_dir
                print(f"📁 已创建设备 {device_id} 的输出目录: {output_dir}")
        
        return output_dirs

def main():
    """主函数 - 用于测试配置管理器"""
    import argparse
    
    parser = argparse.ArgumentParser(description='设备配置管理器')
    parser.add_argument('--config', '-c', default='device_config_template.json', help='配置文件路径')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有设备配置')
    parser.add_argument('--validate', '-v', nargs='+', help='验证指定的设备ID')
    parser.add_argument('--create-dirs', '-d', nargs='+', help='为指定设备创建输出目录')
    
    args = parser.parse_args()
    
    # 创建配置管理器
    config_manager = DeviceConfigManager(args.config)
    
    if args.list:
        config_manager.list_devices()
    
    if args.validate:
        valid_devices = config_manager.validate_device_ids(args.validate)
        print(f"✅ 有效设备: {valid_devices}")
    
    if args.create_dirs:
        config_manager.create_output_directories(args.create_dirs)

if __name__ == "__main__":
    main()