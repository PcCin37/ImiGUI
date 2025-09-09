# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import sys
import os
from comprehension import analyze_ui_folder,generate_subtask_for_page
from delete import extract_icon_content
from generate_json_for_folder import generate_json_for_folder
from history import get_history_knowledge, save_history_entry
from interaction_processor import run_interaction_processing
from check_response import check_response

def process_folder(folder_path, whole_task):
    """
    先调用comprehension.py生成分析文件，再调用delete.py处理同一文件夹下的文件，生成json，获取历史摘要和建议，批量推理交互，最后保存操作信息。
    """
    print(f"全局任务: {whole_task}")
    print(f"开始分析文件夹: {folder_path}")
    analyze_ui_folder(folder_path)
    print(f"分析完成，开始提取icon内容...")
    extract_icon_content(folder_path)
    print(f"icon内容提取完成，开始生成json...")
    generate_json_for_folder(folder_path)

    # 新增：生成子task
    print(f"根据全局任务生成当前页面子task...")
    generate_subtask_for_page(folder_path, whole_task)
    
    # 自动推断输入输出json路径
    folder_name = os.path.basename(os.path.normpath(folder_path))
    input_json = os.path.join(folder_path, f"{folder_name}_output.json")
    output_json = os.path.join(folder_path, f"{folder_name}_response.json")

    # 获取历史摘要和建议
    print(f"json生成完成，获取历史摘要和建议...")
    history_knowledge = get_history_knowledge(input_json)
    # 你可以在此处将history_knowledge用于后续大模型推理

    '''缺少根据whole任务生成当前task的代码'''


    print(f"历史记录交互完成，开始批量交互推理...")
    run_interaction_processing(input_json, output_json, history_knowledge)

    #print(f"json生成完成，开始检查响应...")
    #check_response(output_json)
    
    #获取img路径
    img_path = os.path.join(folder_path, f"{folder_name}_som_img.jpg")
    
    print(f"批量交互推理完成，保存本轮操作信息...")
    save_history_entry(output_json, img_path)
    #自动读取而不是手动输入

    


    print(f"全部处理完成。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python integrated_process.py <目标文件夹路径>")
        sys.exit(1)
    folder = sys.argv[1]
    whole_task = input("请输入全局任务描述：")
    process_folder(folder, whole_task)