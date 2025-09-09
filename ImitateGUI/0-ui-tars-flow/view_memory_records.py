#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看记忆系统中的所有记录
"""

import sys
import os
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

sys.path.append('C:/Users/Mr. Ye/Desktop/Agent/gui-agent-memory')

try:
    from gui_agent_memory.storage import MemoryStorage
    
    def view_all_memory_records():
        """查看记忆系统中的所有记录"""
        print("📋 正在查看记忆系统中的所有记录...")
        
        storage = MemoryStorage()
        
        # 获取所有经验记录
        print("\n🔍 获取所有经验记录:")
        
        collection = storage.experiential_collection
        all_records = collection.get()
        
        if not all_records['ids']:
            print("❌ 记忆系统中没有找到任何记录")
            return
            
        print(f"📊 总共找到 {len(all_records['ids'])} 条经验记录")
        print("=" * 80)
        
        # 显示所有记录
        for i, record_id in enumerate(all_records['ids']):
            print(f"\n=== 记录 {i+1} ===")
            print(f"ID: {record_id}")
            
            # 显示文档内容
            if all_records['documents'] and i < len(all_records['documents']):
                doc = all_records['documents'][i]
                if len(doc) > 300:
                    print(f"文档内容: {doc[:300]}...")
                else:
                    print(f"文档内容: {doc}")
            else:
                print("文档内容: 无")
            
            # 显示元数据
            if all_records['metadatas'] and i < len(all_records['metadatas']):
                metadata = all_records['metadatas'][i]
                if metadata:
                    print("元数据:")
                    for key, value in metadata.items():
                        print(f"  {key}: {value}")
                else:
                    print("元数据: 无")
            else:
                print("元数据: 无")
            
            print("-" * 60)
        
        # 显示统计信息
        try:
            stats = storage.get_collection_stats()
            print(f"\n📈 数据库统计信息:")
            print(f"   经验记录数: {stats['experiential_memories']}")
            print(f"   事实记录数: {stats['declarative_memories']}")
            print(f"   总记录数: {stats['total']}")
        except Exception as e:
            print(f"⚠️ 无法获取统计信息: {e}")
            
        # 显示最新记录信息
        if all_records['metadatas']:
            latest_record_idx = -1
            latest_timestamp = None
            
            # 尝试通过元数据找到最新记录
            for i, metadata in enumerate(all_records['metadatas']):
                if metadata and 'created_at' in metadata:
                    created_at = metadata['created_at']
                    if latest_timestamp is None or created_at > latest_timestamp:
                        latest_timestamp = created_at
                        latest_record_idx = i
            
            # 如果没有时间戳，使用最后一个记录
            if latest_record_idx == -1:
                latest_record_idx = len(all_records['ids']) - 1
            
            print(f"\n🕒 最新记录: 记录 {latest_record_idx + 1} (ID: {all_records['ids'][latest_record_idx]})")
            if latest_timestamp:
                print(f"   创建时间: {latest_timestamp}")
        
    if __name__ == "__main__":
        view_all_memory_records()
        
except ImportError as e:
    print(f"❌ 无法导入记忆系统模块: {e}")
    print("请确保gui_agent_memory模块已正确安装")
except Exception as e:
    print(f"❌ 运行时错误: {e}")