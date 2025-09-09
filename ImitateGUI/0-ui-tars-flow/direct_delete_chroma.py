#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接操作ChromaDB删除特定记录
"""

import chromadb
import os
from pathlib import Path

def delete_chroma_records():
    """直接删除ChromaDB中的记录"""
    print("🗑️ 直接操作ChromaDB删除记录...")
    
    # ChromaDB数据路径
    chroma_path = Path("c:/Users/Mr. Ye/Desktop/Agent/ImitateAgent copy/0-ui-tars-flow/memory_system/data/chroma")
    
    if not chroma_path.exists():
        print(f"❌ ChromaDB路径不存在: {chroma_path}")
        return
    
    try:
        # 连接到ChromaDB
        client = chromadb.PersistentClient(path=str(chroma_path))
        
        # 列出所有集合
        collections = client.list_collections()
        print(f"\n📊 找到 {len(collections)} 个集合:")
        
        for collection in collections:
            print(f"   - {collection.name} (ID: {collection.id})")
            
            # 获取集合中的所有记录
            try:
                results = collection.get()
                print(f"     记录数: {len(results['ids'])}")
                
                # 查找包含task_20250816_130742的记录
                records_to_delete = []
                for i, (id_, metadata) in enumerate(zip(results['ids'], results['metadatas'])):
                    if metadata and 'source_task_id' in metadata:
                        if metadata['source_task_id'] == 'task_20250816_130742':
                            records_to_delete.append(id_)
                            print(f"     找到要删除的记录: {id_} (任务ID: {metadata['source_task_id']})")
                
                # 删除找到的记录
                if records_to_delete:
                    print(f"\n⚠️ 准备删除 {len(records_to_delete)} 条记录")
                    confirm = input("确认删除？(输入 'yes' 确认): ")
                    
                    if confirm.lower() == 'yes':
                        collection.delete(ids=records_to_delete)
                        print(f"✅ 成功删除 {len(records_to_delete)} 条记录")
                        
                        # 验证删除
                        remaining = collection.get()
                        print(f"✅ 集合 {collection.name} 剩余记录数: {len(remaining['ids'])}")
                    else:
                        print("❌ 删除操作已取消")
                else:
                    print(f"     未找到task_20250816_130742相关记录")
                    
            except Exception as e:
                print(f"     ❌ 处理集合 {collection.name} 时出错: {e}")
                
    except Exception as e:
        print(f"❌ 连接ChromaDB失败: {e}")
        
        # 尝试重置ChromaDB
        print("\n🔄 尝试重置ChromaDB数据库...")
        reset_confirm = input("是否要删除整个ChromaDB数据库并重新初始化？(输入 'reset' 确认): ")
        
        if reset_confirm.lower() == 'reset':
            try:
                import shutil
                if chroma_path.exists():
                    shutil.rmtree(chroma_path)
                    print("✅ ChromaDB数据库已删除")
                    print("💡 请重新运行记忆系统初始化脚本")
            except Exception as reset_error:
                print(f"❌ 重置失败: {reset_error}")

if __name__ == "__main__":
    delete_chroma_records()