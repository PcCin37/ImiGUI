#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询记忆系统中关于商城、最高价、最低价的经验记录
"""

import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

sys.path.append('C:/Users/Mr. Ye/Desktop/Agent/gui-agent-memory')

try:
    from gui_agent_memory.storage import MemoryStorage
    
    def query_mall_experiences():
        """查询商城相关的经验记录"""
        print("🔍 正在查询记忆系统中的商城相关经验...")
        
        storage = MemoryStorage()
        
        # 查询包含"商城"的经验
        print("\n📊 查询包含'商城'的经验:")
        result = storage.query_experiences(query_texts=['商城'], n_results=10)
        
        if result['ids'][0]:
            print(f"找到 {len(result['ids'][0])} 个相关经验:")
            for i, (id_, doc) in enumerate(zip(result['ids'][0], result['documents'][0])):
                print(f"\n=== 经验 {i+1} ===")
                print(f"ID: {id_}")
                print(f"文档: {doc}")
                
                # 获取元数据
                if i < len(result['metadatas'][0]):
                    metadata = result['metadatas'][0][i]
                    if 'keywords' in metadata:
                        print(f"关键词: {metadata['keywords']}")
                    if 'is_successful' in metadata:
                        print(f"成功状态: {metadata['is_successful']}")
                    if 'source_task_id' in metadata:
                        print(f"来源任务ID: {metadata['source_task_id']}")
                    if 'action_flow' in metadata:
                        print(f"操作步骤: {metadata['action_flow'][:200]}...")
        else:
            print("未找到包含'商城'的经验记录")
            
        # 查询包含"价格"或"最高价"或"最低价"的经验
        print("\n📊 查询包含价格相关的经验:")
        price_result = storage.query_experiences(query_texts=['价格', '最高价', '最低价', '筛选'], n_results=10)
        
        if price_result['ids'][0]:
            print(f"找到 {len(price_result['ids'][0])} 个价格相关经验:")
            for i, (id_, doc) in enumerate(zip(price_result['ids'][0], price_result['documents'][0])):
                print(f"\n=== 价格经验 {i+1} ===")
                print(f"ID: {id_}")
                print(f"文档: {doc}")
                
                # 获取元数据
                if i < len(price_result['metadatas'][0]):
                    metadata = price_result['metadatas'][0][i]
                    if 'keywords' in metadata:
                        print(f"关键词: {metadata['keywords']}")
                    if 'source_task_id' in metadata:
                        print(f"来源任务ID: {metadata['source_task_id']}")
        else:
            print("未找到价格相关的经验记录")
            
        # 获取集合统计信息
        stats = storage.get_collection_stats()
        print(f"\n📈 数据库统计:")
        print(f"   经验记录数: {stats['experiential_memories']}")
        print(f"   事实记录数: {stats['declarative_memories']}")
        print(f"   总记录数: {stats['total']}")
        
    if __name__ == "__main__":
        query_mall_experiences()
        
except ImportError as e:
    print(f"❌ 无法导入记忆系统模块: {e}")
    print("请确保gui_agent_memory模块已正确安装")
except Exception as e:
    print(f"❌ 运行时错误: {e}")