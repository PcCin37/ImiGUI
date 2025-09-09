#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证记录删除结果
"""

import chromadb
from pathlib import Path

def verify_deletion():
    """验证删除结果"""
    print("🔍 验证记录删除结果...")
    
    # ChromaDB数据路径
    chroma_path = Path("c:/Users/Mr. Ye/Desktop/Agent/ImitateAgent copy/0-ui-tars-flow/memory_system/data/chroma")
    
    try:
        # 连接到ChromaDB
        client = chromadb.PersistentClient(path=str(chroma_path))
        
        # 获取经验记忆集合
        collection = client.get_collection("experiential_memories")
        
        # 获取所有记录
        results = collection.get()
        print(f"\n📊 当前经验记忆集合中有 {len(results['ids'])} 条记录:")
        
        # 显示剩余记录的详细信息
        for i, (id_, metadata) in enumerate(zip(results['ids'], results['metadatas'])):
            print(f"\n=== 记录 {i+1} ===")
            print(f"ID: {id_}")
            if metadata:
                if 'source_task_id' in metadata:
                    print(f"来源任务ID: {metadata['source_task_id']}")
                if 'is_successful' in metadata:
                    print(f"成功状态: {metadata['is_successful']}")
                if 'keywords' in metadata:
                    print(f"关键词: {metadata['keywords']}")
                if 'created_at' in metadata:
                    print(f"创建时间: {metadata['created_at']}")
        
        # 特别检查是否还有task_20250816_130742相关记录
        task_found = False
        for metadata in results['metadatas']:
            if metadata and 'source_task_id' in metadata:
                if metadata['source_task_id'] == 'task_20250816_130742':
                    task_found = True
                    break
        
        if task_found:
            print("\n⚠️ 警告：仍然找到task_20250816_130742相关记录")
        else:
            print("\n✅ 确认：task_20250816_130742相关记录已完全删除")
            
        # 检查是否有其他商城相关记录
        mall_records = []
        for i, (id_, doc, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
            if '商城' in doc or (metadata and 'keywords' in metadata and '商城' in metadata['keywords']):
                mall_records.append((id_, doc, metadata))
        
        if mall_records:
            print(f"\n📋 剩余的商城相关记录 ({len(mall_records)} 条):")
            for i, (id_, doc, metadata) in enumerate(mall_records):
                print(f"\n--- 商城记录 {i+1} ---")
                print(f"ID: {id_}")
                print(f"文档: {doc[:100]}...")
                if metadata and 'source_task_id' in metadata:
                    print(f"来源任务ID: {metadata['source_task_id']}")
                if metadata and 'is_successful' in metadata:
                    print(f"成功状态: {metadata['is_successful']}")
        else:
            print("\n📋 未找到其他商城相关记录")
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")

if __name__ == "__main__":
    verify_deletion()