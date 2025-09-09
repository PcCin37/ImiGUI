# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import re

def normalize(s):
    return ''.join(s.split())

def search_icon_bbox(icon_id_input, user_input, content_file, order_file):
    # 1. 只查找icon编号是否存在于content_file
    found = False
    with open(content_file, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r"icon (\d+):", line)
            if match:
                idx = match.group(1)
                if idx == icon_id_input:
                    found = True
                    break
    if not found:
        return None
    # 2. 只查找icon编号并返回bbox
    with open(order_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith(f'icon {icon_id_input}:'):
                bbox_match = re.search(r"'bbox':\s*(\[[^\]]+\])", line)
                if bbox_match:
                    bbox_str = bbox_match.group(1)
                    bbox_vals = eval(bbox_str)
                    x1, y1, x2, y2 = bbox_vals
                    xc = (x1 + x2) / 2
                    yc = (y1 + y2) / 2
                    return (xc, yc)
                else:
                    return None
    return None

# 示例用法
if __name__ == '__main__':
    content_file = 'level1/1_tags_order_content.txt'
    order_file = 'level1/1_tags_order.txt'
    icon_id_input = input("请输入icon编号：").strip()
    user_input = input("请输入要查找的内容：")
    result = search_icon_bbox(icon_id_input, user_input, content_file, order_file)
    if result is None:
        print("没查找到")
    else:
        print(f"icon {icon_id_input} 的中心点坐标为: (xc={result[0]}, yc={result[1]})")