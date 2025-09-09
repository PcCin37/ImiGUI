#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询记忆系统中存储的经验和操作记录
"""

import sys
import os

# 添加gui_agent_memory到路径
sys.path.append('gui-agent-memory')
sys.path.append('ImitateAgent copy/0-ui-tars-flow')

try:
    from gui_agent_memory import MemorySystem
    
    def query_memory_system():
        """查询记忆系统中的所有内容"""
        print("🔍 正在初始化记忆系统...")
        
        # 初始化记忆系统
        memory_system = MemorySystem()
        
        print("\n📊 记忆系统状态:")
        
        # 尝试检索所有经验
        print("\n🔍 检索所有经验记录...")
        try:
            # 使用通用查询来获取所有经验
            memories = memory_system.retrieve_memories("任务 操作 点击 输入", top_n=50)
            
            if memories.experiences:
                print(f"\n✅ 找到 {len(memories.experiences)} 条经验记录:")
                for i, exp in enumerate(memories.experiences, 1):
                    print(f"\n=== 经验 {i} ===")
                    print(f"📝 任务描述: {exp.task_description}")
                    print(f"🔑 关键词: {', '.join(exp.keywords)}")
                    print(f"📱 应用名称: {getattr(exp, 'app_name', '未知')}")
                    print(f"🆔 来源任务ID: {getattr(exp, 'source_task_id', '未知')}")
                    print(f"✅ 是否成功: {'是' if exp.is_successful else '否'}")
                    print(f"📊 使用次数: {exp.usage_count}")
                    print(f"🕒 最后使用: {exp.last_used_at}")
                    
                    if hasattr(exp, 'preconditions') and exp.preconditions:
                        print(f"⚙️ 前置条件: {exp.preconditions}")
                    
                    if hasattr(exp, 'postconditions') and exp.postconditions:
                        print(f"✅ 后置条件: {exp.postconditions}")
                    
                    if exp.action_flow:
                        print(f"🔘 操作步骤 ({len(exp.action_flow)}步):")
                        for j, step in enumerate(exp.action_flow, 1):
                            action_type = getattr(step, 'action_type', getattr(step, 'action', '未知'))
                            description = getattr(step, 'target_element_description', getattr(step, 'description', '未知'))
                            thought = getattr(step, 'thought', '无')
                            print(f"  {j}. 思考: {thought}")
                            print(f"     操作: {action_type}")
                            print(f"     目标: {description}")
                            if hasattr(step, 'coordinates') and step.coordinates:
                                print(f"     坐标: {step.coordinates}")
                            if hasattr(step, 'text') and step.text:
                                print(f"     文本: {step.text}")
            else:
                print("📑 未找到任何经验记录")
            
            if memories.facts:
                print(f"\n📎 找到 {len(memories.facts)} 个事实记录:")
                for i, fact in enumerate(memories.facts, 1):
                    print(f"\n=== 事实 {i} ===")
                    print(f"📄 内容: {fact.content}")
                    print(f"🔑 关键词: {', '.join(fact.keywords)}")
                    print(f"📍 来源: {getattr(fact, 'source', '未知')}")
                    print(f"🆔 事实ID: {getattr(fact, 'fact_id', '未知')}")
                    if hasattr(fact, 'confidence_score'):
                        print(f"📊 置信度: {fact.confidence_score}")
                    if hasattr(fact, 'created_at'):
                        print(f"📅 创建时间: {fact.created_at}")
            else:
                print("\n📎 未找到任何事实记录")
                
        except Exception as e:
            print(f"⚠️ 检索记忆时出错: {e}")
        
        # 尝试获取统计信息
        try:
            print("\n📈 尝试获取记忆系统统计信息...")
            # 这里可以添加更多统计查询
        except Exception as e:
            print(f"⚠️ 获取统计信息时出错: {e}")
    
    if __name__ == "__main__":
        query_memory_system()
        
except ImportError as e:
    print(f"❌ 无法导入记忆系统模块: {e}")
    print("请确保gui_agent_memory模块已正确安装")
except Exception as e:
    print(f"❌ 运行时错误: {e}")