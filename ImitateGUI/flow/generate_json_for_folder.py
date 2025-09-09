# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import json

def generate_json_for_folder(folder_path):
    folder_name = os.path.basename(os.path.normpath(folder_path))
    files = os.listdir(folder_path)
    # 构建文件名映射
    def find_file(suffix):
        for f in files:
            if f.endswith(suffix):
                return f
        return None
    original_img = find_file('original_img.jpg')
    som_img = find_file('som_img.jpg')
    tags_order = find_file('tags_order.txt')
    tags_order_content = find_file('tags_order_content.txt')
    comprehension = find_file('comprehension.txt')
    # 构建image字段
    image = {
        "original_iamge": os.path.join(folder_path, original_img) if original_img else None,
        "som_image": os.path.join(folder_path, som_img) if som_img else None,
        "som_text": os.path.join(folder_path, tags_order) if tags_order else None,
        "som_tags": os.path.join(folder_path, tags_order_content) if tags_order_content else None,
        "comprehension": os.path.join(folder_path, comprehension) if comprehension else None
    }
    # 路径转为相对路径
    for k, v in image.items():
        if v:
            image[k] = os.path.relpath(v)
    # 构建最终结构
    result = [{
        "id": folder_name,
        "image": image,
        "task": ""
    }]
    output_json_path = os.path.join(folder_path, f"{folder_name}_output.json")
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"已生成: {output_json_path}") 