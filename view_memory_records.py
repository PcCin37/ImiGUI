#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看记忆系统中的所有记录
"""

import chromadb
from pathlib import Path
import json

def view_all_memory_records():
    """查看记忆系统中的所有记录"""
    print("🔍 查看记忆系统中的所有记录...")
    
    # ChromaDB数据库路径
    chroma_path = "c:/Users/Mr. Ye/Desktop/Agent/ImitateAgent copy/0-ui-tars-flow/memory_system/data/chroma"
    
    try:
        # 检查数据库路径是否存在
        if not Path(chroma_path).exists():
            print(f"❌ ChromaDB路径不存在: {chroma_path}")
            return
        
        # 初始化ChromaDB客户端
        client = chromadb.PersistentClient(path=chroma_path)
        
        # 获取所有集合
        collections = client.list_collections()
        print(f"\n📊 找到 {len(collections)} 个集合")
        
        for collection in collections:
            print(f"\n{'='*60}")
            print(f"📁 集合名称: {collection.name}")
            print(f"📝 描述: {collection.metadata}")
            
            # 获取集合统计
            count = collection.count()
            print(f"📊 记录总数: {count}")
            
            if count > 0:
                # 获取所有记录
                try:
                    results = collection.get()
                    
                    if results['ids']:
                        for i, (id_, doc, metadata) in enumerate(zip(
                            results['ids'], 
                            results['documents'] or [], 
                            results['metadatas'] or []
                        )):
                            print(f"\n--- 记录 {i+1} ---")
                            print(f"🆔 ID: {id_}")
                            print(f"📄 任务描述: {doc[:100]}..." if len(doc) > 100 else f"📄 任务描述: {doc}")
                            
                            if metadata:
                                print(f"🏷️  关键词: {metadata.get('keywords', 'N/A')}")
                                print(f"✅ 成功状态: {metadata.get('is_successful', 'N/A')}")
                                print(f"🔗 来源任务: {metadata.get('source_task_id', 'N/A')}")
                                print(f"📅 最后使用: {metadata.get('last_used_at', 'N/A')}")
                                
                                # 显示操作步骤（简化）
                                if 'action_flow' in metadata:
                                    try:
                                        action_flow = json.loads(metadata['action_flow'])
                                        print(f"🔧 操作步骤数: {len(action_flow)}")
                                        print(f"🎯 主要操作: ", end="")
                                        actions = [step.get('action', 'unknown') for step in action_flow[:3]]
                                        print(" → ".join(actions))
                                        if len(action_flow) > 3:
                                            print(f"     ... 还有 {len(action_flow) - 3} 个步骤")
                                    except:
                                        print(f"🔧 操作步骤: {metadata['action_flow'][:100]}...")
                                
                                # 显示前置条件（简化）
                                if 'preconditions' in metadata:
                                    precond = metadata['preconditions']
                                    if len(precond) > 100:
                                        precond = precond[:100] + "..."
                                    print(f"📋 前置条件: {precond}")
                            
                            print("-" * 40)
                    else:
                        print("   (集合为空)")
                        
                except Exception as e:
                    print(f"❌ 获取记录时出错: {e}")
            else:
                print("   (集合为空)")
        
        print(f"\n{'='*60}")
        print("✅ 记录查看完成")
        
    except Exception as e:
        print(f"❌ 查询ChromaDB时出错: {e}")

if __name__ == "__main__":
    view_all_memory_records()