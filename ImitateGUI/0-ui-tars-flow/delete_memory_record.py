#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除记忆系统中的特定经验记录
"""

import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

sys.path.append('C:/Users/Mr. Ye/Desktop/Agent/gui-agent-memory')

try:
    from gui_agent_memory.storage import MemoryStorage
    
    def delete_mall_experience():
        """删除商城相关的失败经验记录"""
        print("🗑️ 正在删除记忆系统中的商城失败经验记录...")
        
        storage = MemoryStorage()
        
        # 首先查询要删除的记录
        print("\n🔍 查找要删除的记录:")
        result = storage.query_experiences(query_texts=['商城', 'task_20250816_130742'], n_results=10)
        
        if result['ids'][0]:
            print(f"找到 {len(result['ids'][0])} 个相关记录:")
            
            # 显示找到的记录
            for i, (id_, doc) in enumerate(zip(result['ids'][0], result['documents'][0])):
                print(f"\n=== 记录 {i+1} ===")
                print(f"ID: {id_}")
                print(f"文档: {doc[:100]}...")
                
                # 检查元数据
                if i < len(result['metadatas'][0]):
                    metadata = result['metadatas'][0][i]
                    if 'source_task_id' in metadata:
                        print(f"来源任务ID: {metadata['source_task_id']}")
                    if 'is_successful' in metadata:
                        print(f"成功状态: {metadata['is_successful']}")
            
            # 询问用户确认
            print("\n⚠️ 确认删除操作:")
            confirm = input("是否确认删除以上记录？(输入 'yes' 确认): ")
            
            if confirm.lower() == 'yes':
                try:
                    # 删除记录
                    collection = storage.experiential_collection
                    ids_to_delete = result['ids'][0]
                    
                    collection.delete(ids=ids_to_delete)
                    print(f"\n✅ 成功删除 {len(ids_to_delete)} 条记录")
                    
                    # 验证删除结果
                    verify_result = storage.query_experiences(query_texts=['task_20250816_130742'], n_results=5)
                    if not verify_result['ids'][0]:
                        print("✅ 验证成功：记录已完全删除")
                    else:
                        print(f"⚠️ 警告：仍有 {len(verify_result['ids'][0])} 条相关记录存在")
                        
                except Exception as e:
                    print(f"❌ 删除失败: {e}")
            else:
                print("❌ 删除操作已取消")
        else:
            print("未找到要删除的记录")
            
        # 显示删除后的统计信息
        stats = storage.get_collection_stats()
        print(f"\n📈 删除后的数据库统计:")
        print(f"   经验记录数: {stats['experiential_memories']}")
        print(f"   事实记录数: {stats['declarative_memories']}")
        print(f"   总记录数: {stats['total']}")
        
    if __name__ == "__main__":
        delete_mall_experience()
        
except ImportError as e:
    print(f"❌ 无法导入记忆系统模块: {e}")
    print("请确保gui_agent_memory模块已正确安装")
except Exception as e:
    print(f"❌ 运行时错误: {e}")