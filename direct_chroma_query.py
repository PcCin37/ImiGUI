#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接查询ChromaDB数据库内容
"""

import chromadb
from pathlib import Path
import json

def query_chroma_directly():
    """直接查询ChromaDB数据库"""
    print("🔍 直接查询ChromaDB数据库...")
    
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
        print(f"\n📊 找到 {len(collections)} 个集合:")
        
        for collection in collections:
            print(f"\n=== 集合: {collection.name} ===")
            print(f"📝 描述: {collection.metadata}")
            
            # 获取集合统计
            count = collection.count()
            print(f"📊 记录数: {count}")
            
            if count > 0:
                # 获取所有记录（最多50条）
                try:
                    results = collection.get(limit=min(count, 50))
                    
                    print(f"\n📋 记录详情 (显示前{min(count, 50)}条):")
                    
                    if results['ids']:
                        for i, (id_, doc, metadata) in enumerate(zip(
                            results['ids'], 
                            results['documents'] or [], 
                            results['metadatas'] or []
                        )):
                            print(f"\n--- 记录 {i+1} ---")
                            print(f"🆔 ID: {id_}")
                            if doc:
                                print(f"📄 文档: {doc[:200]}{'...' if len(doc) > 200 else ''}")
                            if metadata:
                                print(f"📋 元数据: {json.dumps(metadata, ensure_ascii=False, indent=2)}")
                    else:
                        print("   (无记录内容)")
                        
                except Exception as e:
                    print(f"   ❌ 获取记录失败: {e}")
            else:
                print("   (集合为空)")
                
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    query_chroma_directly()