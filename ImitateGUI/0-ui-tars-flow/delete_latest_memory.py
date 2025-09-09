#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除记忆系统中最新的一条记录
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
    
    def delete_latest_experience():
        """删除记忆系统中最新的一条经验记录"""
        print("🗑️ 正在查找并删除记忆系统中最新的记录...")
        
        storage = MemoryStorage()
        
        # 获取所有经验记录，按时间排序
        print("\n🔍 查找最新记录:")
        
        # 查询所有记录
        collection = storage.experiential_collection
        all_records = collection.get()
        
        if not all_records['ids']:
            print("❌ 记忆系统中没有找到任何记录")
            return
            
        print(f"📊 总共找到 {len(all_records['ids'])} 条记录")
        
        # 找到最新的记录（通过元数据中的时间戳或ID排序）
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
            print("⚠️ 未找到时间戳信息，使用最后一个记录作为最新记录")
        
        # 显示最新记录信息
        latest_id = all_records['ids'][latest_record_idx]
        latest_doc = all_records['documents'][latest_record_idx] if all_records['documents'] else "无文档内容"
        latest_metadata = all_records['metadatas'][latest_record_idx] if all_records['metadatas'] else {}
        
        print(f"\n=== 最新记录信息 ===")
        print(f"ID: {latest_id}")
        print(f"文档内容: {latest_doc[:200]}..." if len(latest_doc) > 200 else f"文档内容: {latest_doc}")
        
        if latest_metadata:
            print(f"元数据:")
            for key, value in latest_metadata.items():
                print(f"  {key}: {value}")
        
        # 询问用户确认
        print("\n⚠️ 确认删除操作:")
        confirm = input("是否确认删除以上最新记录？(输入 'yes' 确认): ")
        
        if confirm.lower() == 'yes':
            try:
                # 删除记录
                collection.delete(ids=[latest_id])
                print(f"\n✅ 成功删除最新记录: {latest_id}")
                
                # 验证删除结果
                verify_result = collection.get(ids=[latest_id])
                if not verify_result['ids']:
                    print("✅ 验证成功：记录已完全删除")
                else:
                    print(f"⚠️ 警告：记录可能未完全删除")
                    
            except Exception as e:
                print(f"❌ 删除失败: {e}")
        else:
            print("❌ 删除操作已取消")
            
        # 显示删除后的统计信息
        try:
            stats = storage.get_collection_stats()
            print(f"\n📈 删除后的数据库统计:")
            print(f"   经验记录数: {stats['experiential_memories']}")
            print(f"   事实记录数: {stats['declarative_memories']}")
            print(f"   总记录数: {stats['total']}")
        except Exception as e:
            print(f"⚠️ 无法获取统计信息: {e}")
        
    if __name__ == "__main__":
        delete_latest_experience()
        
except ImportError as e:
    print(f"❌ 无法导入记忆系统模块: {e}")
    print("请确保gui_agent_memory模块已正确安装")
except Exception as e:
    print(f"❌ 运行时错误: {e}")