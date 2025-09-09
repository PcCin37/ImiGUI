# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import requests
import json
import os
import base64
from PIL import Image
import io
import argparse
from history import load_all_entries
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def read_tags_order_sorted(file_path):
    """读取SOM处理后的tags_order_sorted.txt文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.read().strip().split('\n')
    
    tags = {}
    for line in lines:
        if not line.strip():
            continue
        
        parts = line.split(': ', 1)
        if len(parts) != 2:
            continue
            
        tag_id = parts[0].split(' ')[1]
        tag_data = eval(parts[1])  # 解析字典字符串
        tags[tag_id] = tag_data
    
    return tags

def encode_image(image_path):
    """将图像编码为base64格式"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def call_llm_api(image_base64, tags_data):
    """
    调用大型语言模型API分析UI图像和标签，统一为openai.OpenAI库的调用方式
    """
    api_key = os.getenv('ARK_API_KEY')
    if not api_key:
        raise ValueError("ARK_API_KEY环境变量未设置")
    base_url = "https://poloai.top/v1"
    client = OpenAI(api_key=api_key, base_url=base_url)

    # 构建提示词
    prompt = """

你是一个UI分析助手，请对上传的UI界面图像进行详细分析。图像中包含了已标注的UI元素，每个标注都有一个数字标签位于框的左上角。

【严格要求】
1. 你必须严格按照图片中已标注的所有序号（标签）进行分析，输出的分析内容中的序号、解释和图片中的序号、对象一一对应。
2. 不允许自行增加、合并、跳过或重新编号任何标签。无论标签内容是否有意义，都必须对每一个上传的标签编号进行分析和输出。
3. 所有补充内容（即图片中未标注但你认为重要的UI元素）必须全部放在最后的"未标注UI元素补充"部分，不得插入到已标注标签分析中间。
4. 输出顺序必须与图片中的标签顺序一致。

分析要求：
- 详细解释每个已标注区域的UI元素，包括元素的外形、位置、大小、颜色、文字内容等。
- 说明每个UI元素的功能和用途，判断UI元素是否可交互。
- 分析UI元素之间的关系和布局逻辑。
- 识别未标注的重要UI元素（仅在最后补充部分列出）。

    标签信息格式说明：
    - 类型(type)：表示UI元素的类型（如按钮、文本框等）
    - 位置(bbox)：表示UI元素在界面中的坐标位置
    - 内容(content)：表示UI元素包含的文本或信息

    已识别的标签内容如下：
    """
    # 添加标签信息
    for tag_id, tag_info in tags_data.items():
        prompt += f"标签 {tag_id}: 类型={tag_info['type']}, 位置={tag_info['bbox']}, 内容='{tag_info['content']}'\n"
    prompt += """
    你需要结合标签信息和图像识别结果，判断标签信息中的识别是否准确，如果存在错误，请进行修正。
    此外，你需要判断图像中是否存在未标注及标注错误的UI元素，如果有，请进行补充说明。

    你需要确保对所有的标签都有详细的分析和描述，UI元素功能的分析结果需要尽可能详细，如果可能，说明UI元素的交互方式和当前状态。
    
    对于不能完全确定功能的UI元素，请说明所有可能的功能。
    请不要遗漏任何UI元素，不要遗漏任何可能的功能。
    
    请按以下格式输出分析结果：
    

    1. 已标注UI元素分析：
       标签 [编号]: [元素类型] [详细说明该UI元素的描述]
         功能：[详细说明该UI元素的功能与可能的功能]
    
    例如：
    标签 1: 按钮 这是一个按钮，位于界面左上角，按钮上显示"返回"字样。
    功能：点击按钮可以返回上一级界面。
    
    注意：编号不能被组合，请不要出现类似"1-2"的编号。

    2. 未标注UI元素补充：
       补充元素1：[位置描述]
         类型：[推测的元素类型]
         功能：[推测的功能]
         参考位置：[相对于最近标签的位置]
   
    除了按格式输出的分析结果不要输出其他内容。
    请确保分析准确、专业且易于理解。
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的UI分析助手，擅长理解和解释UI界面的各个元素。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ],
            max_tokens=10000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"API调用出错: {str(e)}"

def analyze_ui_folder(folder_path):
    if not folder_path:
        print("请指定文件夹路径")
        return None
    files = os.listdir(folder_path)
    tags_files = [f for f in files if f.endswith('_tags_order.txt')]
    img_files = [f for f in files if f.endswith('_som_img.jpg')]
    if not tags_files:
        print("错误：未找到以_tags_order结尾的标签文件")
        return None
    if not img_files:
        print("错误：未找到以_som_img结尾的图片文件")
        return None
    tags_file = os.path.join(folder_path, tags_files[0])
    image_file = os.path.join(folder_path, img_files[0])
    folder_name = os.path.basename(os.path.normpath(folder_path))
    output_filename = f"{folder_name}_comprehension.txt"
    output_path = os.path.join(folder_path, output_filename)
    tags_data = read_tags_order_sorted(tags_file)
    image_base64 = encode_image(image_file)
    result = call_llm_api(image_base64, tags_data)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"结果已保存至: {output_path}")
    return result

def generate_subtask_for_page(folder_path, whole_task, history_knowledge=None):
    """
    根据whole_task和页面内容，生成当前页面的子task，并写入_output.json的task字段
    """
    # 读取历史记录，过滤已成功的子任务
    history_entries = load_all_entries()
    finished_subtasks = set()
    for entry in history_entries:
        if entry.get("subtask_id") and entry.get("success") is True:
            finished_subtasks.add(entry["subtask_id"])

    files = os.listdir(folder_path)
    img_files = [f for f in files if f.endswith('_som_img.jpg')]
    tags_files = [f for f in files if f.endswith('_tags_order.txt')]
    comprehension_files = [f for f in files if f.endswith('_comprehension.txt')]
    output_json_files = [f for f in files if f.endswith('_output.json')]

    if not (img_files and tags_files and comprehension_files and output_json_files):
        print("缺少必要文件")
        return

    image_file = os.path.join(folder_path, img_files[0])
    tags_file = os.path.join(folder_path, tags_files[0])
    comprehension_file = os.path.join(folder_path, comprehension_files[0])
    output_json_file = os.path.join(folder_path, output_json_files[0])

    # 读取文本内容
    with open(tags_file, 'r', encoding='utf-8') as f:
        tags_content = f.read()
    with open(comprehension_file, 'r', encoding='utf-8') as f:
        comprehension_content = f.read()
    image_base64 = encode_image(image_file)

    # 新增：历史摘要内容
    history_summary = ""
    if history_knowledge and isinstance(history_knowledge, dict):
        history_summary = history_knowledge.get("history_summary", "")

    # 构造prompt
    prompt = f"""
你是一个UI任务分解专家。全局任务是：{whole_task}

请根据以下内容，推理并生成本页面的【单步交互操作】（task）：
1. som图片（已上传）
2. tags_order.txt内容：
{tags_content}
3. comprehension.txt内容：
{comprehension_content}
4. 历史操作记录摘要：
{history_summary}

【要求】：
- {tags_content}与{comprehension_content}只供更好的理解界面，在输出task时，不要输出具体的点击几号icon的具体交互操作，而是根据全局任务分析出当前需要执行的任务，如根据全局任务"购买一件裤子"和当前界面内容，分析出task"选择第几个商品把它添加到购物车"。
- task应该是这个页面需要执行的操作，具体如何操作如"点击几号icon"或"点击xx按钮"会在其他操作步骤中输出，无需在当前task生成中输出。
- 不要输出"查看价格""确认信息""评估商品质量"等非交互行为。
- 每个 task 只描述一步当前需要进行的操作，不要合并多步操作，不要输出复合操作。
- 如果有多个可交互操作，请只输出其中最关键的一步。
- 只输出 task 内容，不要输出多余内容。
- 【重要】以下子任务已被成功执行过：{list(finished_subtasks)}。
- 【提示】如果上一步操作失败（如误操作进入了错误页面），你可以考虑返回上一界面，但也可以根据实际情况判断是否需要继续当前任务。
- 【提示】在执行输入文本的交互操作之前，必须先点击对应的文本输入框，点击后才能输入文字。
- 【提示】在执行搜索操作之前，必须先检查搜索框内容是否符合要求，如果符合要求，则直接执行搜索操作，如果不符合要求，则先输入正确的搜索内容，再执行搜索操作。
请直接输出最终的 task。
"""

    # 调用大模型API
    api_key = os.getenv('ARK_API_KEY')
    if not api_key:
        raise ValueError("ARK_API_KEY环境变量未设置")
    base_url = "https://poloai.top/v1"
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的UI任务分解专家。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ],
            max_tokens=2048
        )
        subtask = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"API调用出错: {str(e)}")
        subtask = ""

    # 写入_output.json
    with open(output_json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list) and len(data) > 0:
        data[0]['task'] = subtask
    with open(output_json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"子任务已写入: {output_json_file}")

def main():
    parser = argparse.ArgumentParser(description='解释UI标签')
    parser.add_argument('--folder', type=str, help='输入文件夹路径，包含UI分析所需的文件')
    args = parser.parse_args()
    analyze_ui_folder(args.folder)

if __name__ == "__main__":
    main()