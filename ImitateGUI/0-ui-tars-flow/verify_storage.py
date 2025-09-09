import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

sys.path.append('C:/Users/Mr. Ye/Desktop/Agent/gui-agent-memory')

from gui_agent_memory.storage import MemoryStorage

def verify_stored_data():
    """验证存储的数据"""
    storage = MemoryStorage()
    
    # 查询包含"商城"的经验
    result = storage.query_experiences(query_texts=['商城'], n_results=5)
    
    print(f"找到 {len(result['ids'][0])} 个相关经验:")
    
    for i, (id_, doc) in enumerate(zip(result['ids'][0], result['documents'][0])):
        print(f"  {i+1}. ID: {id_}")
        print(f"     文档: {doc}")
        
        # 获取元数据
        if i < len(result['metadatas'][0]):
            metadata = result['metadatas'][0][i]
            if 'keywords' in metadata:
                print(f"     关键词: {metadata['keywords']}")
            if 'is_successful' in metadata:
                print(f"     成功状态: {metadata['is_successful']}")
            if 'action_flow' in metadata:
                import json
                try:
                    action_flow = json.loads(metadata['action_flow'])
                    print(f"     操作步骤数: {len(action_flow)}")
                except:
                    print(f"     操作步骤: {metadata['action_flow'][:100]}...")
        print()
    
    # 获取集合统计信息
    stats = storage.get_collection_stats()
    print(f"\n📊 数据库统计:")
    print(f"   经验记录数: {stats['experiential_memories']}")
    print(f"   事实记录数: {stats['declarative_memories']}")
    print(f"   总记录数: {stats['total']}")

if __name__ == "__main__":
    verify_stored_data()