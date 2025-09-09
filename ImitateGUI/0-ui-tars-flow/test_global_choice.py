#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试全局选择功能的简单脚本
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 模拟记忆系统
class MockMemorySystem:
    def __init__(self):
        self.available = True

def test_global_choice_logic():
    """
    测试全局选择逻辑
    """
    print("🧪 测试全局选择功能逻辑")
    print("=" * 40)
    
    # 模拟记忆系统可用的情况
    memory_system = MockMemorySystem()
    
    print("\n📋 测试场景 1: 记忆系统可用，用户选择启用经验优化")
    use_experience_optimization = True
    if memory_system and memory_system.available:
        if use_experience_optimization:
            print("✅ 经验优化已启用 - 将检索经验并优化子任务")
        else:
            print("🚫 经验优化已禁用 - 直接使用初步子任务规划")
    else:
        print("⚠️ 记忆系统不可用 - 自动禁用经验优化")
    
    print("\n📋 测试场景 2: 记忆系统可用，用户选择禁用经验优化")
    use_experience_optimization = False
    if memory_system and memory_system.available:
        if use_experience_optimization:
            print("✅ 经验优化已启用 - 将检索经验并优化子任务")
        else:
            print("🚫 经验优化已禁用 - 直接使用初步子任务规划")
    else:
        print("⚠️ 记忆系统不可用 - 自动禁用经验优化")
    
    print("\n📋 测试场景 3: 记忆系统不可用")
    memory_system = None
    use_experience_optimization = True  # 用户选择启用，但系统不可用
    if memory_system and hasattr(memory_system, 'available') and memory_system.available:
        if use_experience_optimization:
            print("✅ 经验优化已启用 - 将检索经验并优化子任务")
        else:
            print("🚫 经验优化已禁用 - 直接使用初步子任务规划")
    else:
        print("⚠️ 记忆系统不可用 - 自动禁用经验优化")
        use_experience_optimization = False
    
    print(f"\n🎯 最终设置: use_experience_optimization = {use_experience_optimization}")
    
    print("\n✅ 全局选择功能逻辑测试完成！")

if __name__ == "__main__":
    test_global_choice_logic()