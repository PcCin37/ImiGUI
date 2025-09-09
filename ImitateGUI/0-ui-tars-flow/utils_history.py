import os
import json
from typing import List
import glob

HISTORY_JSONL_PATH = "screenshots/outputs/history.jsonl"

def append_entry_to_jsonl(file_path: str, entry: dict):
    with open(file_path, "a", encoding="utf-8") as f:
        json.dump({"history_entry": entry}, f, ensure_ascii=False)
        f.write("\n")

def find_history_files() -> List[str]:
    """查找所有可能的历史记录文件路径"""
    possible_paths = [
        HISTORY_JSONL_PATH,  # 原始路径
        "test_task/*/outputs/history.jsonl",  # test_task目录结构
        "screenshots/outputs/history.jsonl"  # 备用路径
    ]
    
    history_files = []
    for pattern in possible_paths:
        if "*" in pattern:
            # 使用glob匹配通配符路径
            matches = glob.glob(pattern)
            history_files.extend(matches)
        else:
            # 直接检查文件是否存在
            if os.path.exists(pattern):
                history_files.append(pattern)
    
    return history_files

def load_all_entries(specific_task_dir: str = None) -> List[dict]:
    """
    加载历史记录条目
    
    Args:
        specific_task_dir: 指定任务目录，如果提供则只读取该目录下的历史记录
                          格式如: "test_task/task_20250813_125120"
    
    Returns:
        List[dict]: 历史记录条目列表
    """
    entries = []
    
    if specific_task_dir:
        # 如果指定了特定任务目录，只读取该目录下的历史记录
        specific_history_file = os.path.join(specific_task_dir, "outputs", "history.jsonl")
        if os.path.exists(specific_history_file):
            try:
                with open(specific_history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            obj = json.loads(line)
                            entry = obj.get("history_entry", {})
                            if entry:  # 只添加非空条目
                                entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"读取历史文件 {specific_history_file} 时出错: {e}")
        else:
            print(f"指定的历史文件不存在: {specific_history_file}")
    else:
        # 如果没有指定目录，使用原来的逻辑查找所有历史文件
        history_files = find_history_files()
        
        for history_file in history_files:
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                obj = json.loads(line)
                                entry = obj.get("history_entry", {})
                                if entry:  # 只添加非空条目
                                    entries.append(entry)
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    print(f"读取历史文件 {history_file} 时出错: {e}")
                    continue
    
    return entries
