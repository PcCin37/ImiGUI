# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import re
import os

def extract_icon_content(folder_path):
    """
    处理指定文件夹下所有包含'tags_order'且以.txt结尾但不以_content.txt结尾的文件，
    提取icon行的content内容，输出到同名_content.txt文件。
    """
    if not os.path.isdir(folder_path):
        print(f"路径不存在或不是文件夹: {folder_path}")
        return
    for file in os.listdir(folder_path):
        if 'tags_order' in file and file.endswith('.txt') and not file.endswith('_content.txt'):
            input_file = os.path.join(folder_path, file)
            output_file = os.path.join(folder_path, file.replace('.txt', '_content.txt'))
            with open(input_file, 'r', encoding='utf-8') as fin, open(output_file, 'w', encoding='utf-8') as fout:
                for line in fin:
                    prefix_match = re.match(r"^(icon \d+:)", line)
                    content_match = re.search(r"'content':\s*'([^']*)'", line)
                    if prefix_match and content_match:
                        prefix = prefix_match.group(1)
                        content = content_match.group(1)
                        fout.write(f"{prefix} {{'content': '{content}'}}\n")