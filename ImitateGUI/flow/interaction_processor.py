# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import json
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from openai import OpenAI
from tqdm import tqdm
from find import search_icon_bbox

import re

client = OpenAI(
    api_key="sk-icEwgvQl5Jmb42Ec8aHVnmLNG7kEUyIa6TDToilFxXSOxkeW",  # 替换为你的 key
    base_url="https://poloai.top/v1"
)

interaction_knowledge = """
**单击**
单次点击一个，适用于广泛的组件、按钮交互。
interaction_type: tap。
interaction_parameter: [x, y]
参数中，x与y为点击位置在屏幕中的百分比坐标，如(0.03, 0.70)。
左滑操作：
在指定的区域内滑动，操作的结果通常是：页面左滑获取更多信息。
interaction_type: swipe_left。
interaction_parameter: [x1, y1, x2, y2]
右滑操作：
在指定的区域内滑动，操作的结果通常是：页面右滑获取更多信息。
interaction_type: swipe_right。
interaction_parameter: [x1, y1, x2, y2]
"""
additional_interaction_knowledge = """
应用内返回：
什么情况下使用：在任何页面没有表示返回的可交互信息（按钮、文本）时可以尝试使用，可以在视频边缘执行左右滑动以返回。
操作的结果通常是：退出当前详情页/评论页，返回上一个浏览的页面。
interaction_type: app_return。
系统级返回：
什么情况下使用：在任何页面没有表示返回的可交互信息（按钮、文本），以及应用级返回失效时，可以在屏幕边缘执行滑动以返回。
操作的结果通常是：在系统层面返回上一个层级。
interaction_type: system_return。
翻看上一个视频：
什么情况下使用：当想重新观看刚才看过的视频/信息，但没有直接交互组件时，可以上滑页面查看上一页。
操作的结果通常是：返回到上一页的视频内容。
interaction_type: swipe_last_video。
翻看下一个视频：
什么情况下使用：当想跳过当前视频/信息，观看下一个推荐视频/信息，但没有直接交互组件时，可以下滑页面查看下一页。
操作的结果通常是：切换到下一页内容。
interaction_type: swipe_next_video。
长按视频显示子菜单：
什么情况下使用：如果视频播放页面中显示的操作没有满足需求，需要更多选项时。
操作的结果通常是：调出面板提供如倍速设置、推荐、不感兴趣、举报、稍后播放等功能。
interaction_type: long_press_menu。
双击操作：
什么情况下使用：当需要快速执行点赞操作时，可以双击操作。
操作的结果通常是：对对应的直播和视频进行点赞。
interaction_type: double_tap。
输入操作：
什么情况下使用：当需要输入文字时，传入文字。
操作的结果通常是：在输入框中输入文字。
interaction_type: input_text。
浏览更多内容：
什么情况下使用：当需要浏览更多内容时，可以向上滑动页面，通常在购物，评论区等界面使用，来查看更多信息。
操作的结果通常是：页面向上滑动获取更多信息。
interaction_type: swipe_up。
"""
# planner_prompt = """
    
# 你是一个UI操作规划助手，请根据用户输入的UI界面图像和对应任务，判断需要执行的交互操作。
# 以下是当前的UI界面图像、UI元素的分析与定位结果、界面UI的理解结果。
# som分析图像结果将在稍后呈现:
#     图像中包含了已标注的UI元素，每个标注都有一个数字标签位于框的左上角。
# som分析UI元素结果：{som_tags}
#     标签信息格式说明：
#     - 类型(type)：表示UI元素的类型（如按钮、文本框等）
#     - 位置(bbox)：表示UI元素在界面中的坐标位置
#     - 内容(content)：表示UI元素包含的文本或信息
# 界面UI理解结果：{comprehension}
#     理解结果分析了每个UI元素的详细描述和功能

# 为保证输出一致性，你需要按照以下交互知识来确定interaction_object、interaction_type和interaction_parameter：
# 基本交互知识：
# {interaction_knowledge}
# 额外交互知识：
# {additional_interaction_knowledge}

# 当前任务为: {task}

# 接下来，请你根据以上信息,判断为了完成当前任务需要执行的交互操作。

# 请你完全遵循以下的输出指导：

# 1. 如果通过基础交互知识就可以完成的任务（即有对应直接交互组件）：
# 请你判断交互对象左上角的数字标签，并在som分析UI元素结果中查找有无接近数字标签（有时可能会有数字偏大或者偏下的偏差）、同时符合元素content的icon，如果有，请输出在som分析UI元素结果中准确的数字标签+content。
# 你的输出格式应该为：
# '''json格式'''
# {{
#     "interaction_object": "component_interaction",
#     "interaction_type": "<对应交互操作的type>",
#     "interaction_parameter": {{
#         "tag": "<对应数字标签>",
#         "content": "<对应content>"
#     }}
# }}

# 2. 如果需要通过额外交互完成的任务（即页面中没有直接交互组件）：
# 请你判断需要执行的操作，并返回对应的interaction_type。
# 你的输出格式应该为：
# '''json格式'''
# {{
#     "interaction_object": "area_interaction",
#     "interaction_type": "<对应交互操作的type>"
# }}
# """
planner_prompt = """

你是一个UI操作规划助手，请根据用户输入的UI界面图像和对应任务，判断需要执行的交互操作。
以下是当前的UI界面图像、UI元素的分析与定位结果、界面UI的理解结果。
som分析图像结果将在稍后呈现:
    图像中包含了已标注的UI元素，每个标注都有一个数字标签位于框的左上角。
som分析UI元素结果：{som_tags}
    标签信息格式说明：
    - 类型(type)：表示UI元素的类型（如按钮、文本框等）
    - 位置(bbox)：表示UI元素在界面中的坐标位置
    - 内容(content)：表示UI元素包含的文本或信息
界面UI理解结果：{comprehension}
    理解结果分析了每个UI元素的详细描述和功能

为保证输出一致性，你需要按照以下交互知识来确定interaction_object、interaction_type和interaction_parameter：
基本交互知识：
{interaction_knowledge}
额外交互知识：
{additional_interaction_knowledge}

当前任务为: {task}
以下是历史交互记录：{history_knowledge}

接下来，请你根据以上信息,判断为了完成当前任务需要执行的交互操作。

请你完全遵循以下的输出指导：

1. 如果通过基础交互知识就可以完成的任务（即有对应直接交互组件）：
1.1. 请你判断交互对象左上角的数字标签，并在som分析UI元素结果中查找有无接近数字标签（有时可能会有数字偏大或者偏下的偏差）、同时符合元素content的icon，如果有，请输出在som分析UI元素结果中准确的数字标签+content。需要注意的是，你返回的content需要与{som_tags}中的content一致，不要进行任何修改。
【注意】如果交互类型为 double_tap（双击），请直接输出 area_interaction，不要输出 tag 或 content。
你的输出格式应该为：
'''json格式'''
{{
    "interaction_object": "component_interaction",
    "interaction_type": "<对应交互操作的type>",
    "interaction_parameter": {{
        "tag": "<对应数字标签>",
        "content": "<对应content>"
    }}
}}
1.2. 如果没有，则可能是识别时错误遗漏了当前交互对象坐标，请你以屏幕左上角为(0,0)，右下角为(1,1)，预测当前交互对象交互坐标。
【注意】如果交互类型为 double_tap（双击），请直接输出 area_interaction，不要输出 tag 或 content。
你的输出格式应该为：
'''json格式'''
{{
    "interaction_object": "component_interaction",
    "interaction_type": "<对应交互操作的type>",
    "interaction_parameter": {{
        "grounding": [x, y]
    }}
}}

1.2.1. 【左滑（swipe_left）与右滑（swipe_right）操作的特殊指导】
- 如果任务需要执行左滑（swipe_left）或右滑（swipe_right）操作，且只能在指定区域内完成，请你务必返回该区域的grounding边界（即滑动起止点的百分比坐标），而不是全屏范围。
- 你需要根据som分析UI元素结果，判断允许滑动的区域，并输出该区域的左上角和右下角的百分比坐标，作为滑动的起止点。x1,y1为左上角，x2,y2为右下角。请尽可能的减小限制区域的范围，以避免在边界上滑动导致误操作。
- 【重要】grounding的值必须严格从tags_order文件中获取，不允许自己预测。tags_order文件即为SOM分析后生成的UI元素顺序和坐标文件，路径为data["image"]["som_text"]。
- 输出格式如下：

'''json格式'''
{{
    "interaction_object": "area_interaction",
    "interaction_type": "swipe_left",  // 或 "swipe_right"
    "interaction_parameter": {{
        "grounding": [x1, y1, x2, y2]  // 分别为滑动起点和终点的百分比坐标，且必须在指定区域内
    }}
}}
【左右滑动操作选择说明】
如果任务涉及滑动操作（swipe_left或swipe_right），请根据当前UI内容、元素分布和任务目标，判断本轮操作应优先执行左滑还是右滑。
如果两者都可行，请优先推荐更符合用户意图的方向。

1.3. 如果需要输入文字（interaction_type为input_text），请直接输出如下格式：
'''json格式'''
{{
    "interaction_object": "area_interaction",
    "interaction_type": "input_text",
    "interaction_parameter": {{
        "text": "<要输入的内容>"
    }}
}}
- 【重要】因为不同操作设备的跳转逻辑不同，在输入文字之前必须先点击对应的文本输入框，点击后才能输入文字。
2. 如果需要通过额外交互完成的任务（即页面中没有直接交互组件），或交互类型为 double_tap（双击）：
请你判断需要执行的操作，并返回对应的interaction_type。
你的输出格式应该为：
'''json格式'''
{{
    "interaction_object": "area_interaction",
    "interaction_type": "<对应交互操作的type>"
}}
"""


def send_request(data: Dict, prompt: str, history_knowledge: str) -> Dict:
    """向 OpenAI API 发送请求并将结果添加到数据中"""
    try:
        id_value = data["id"]
        image = data["image"]["som_image"]
        # 读取 som_tags 文件内容
        with open(data["image"]["som_tags"], "r", encoding="utf-8") as som_tags_file:
            som_tags = som_tags_file.read()
        # 读取 comprehension 文件内容
        with open(data["image"]["comprehension"], "r", encoding="utf-8") as comprehension_file:
            comprehension = comprehension_file.read()
        # 读取 tags_order 文件内容
        with open(data["image"]["som_text"], "r", encoding="utf-8") as tags_order_file:
            tags_order_content = tags_order_file.read()
        task = data["task"]
        # 使用 format 方法替换占位符
        full_prompt = prompt.format(
            som_tags=som_tags,
            comprehension=comprehension,
            interaction_knowledge=interaction_knowledge,
            additional_interaction_knowledge=additional_interaction_knowledge,
            task=task,
            history_knowledge=history_knowledge
        )
        # print(full_prompt)
        # 读取图片文件并转换为 base64 编码
        with open(image, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "text", "text": "以下是tags_order文件内容（SOM分析UI元素顺序和坐标）：\n" + tags_order_content},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
        )
        new_data = data.copy()  # 复制原始数据
        # 解析 response.choices[0].message.content 中的 JSON 字符串
        content = response.choices[0].message.content
        content = content.strip()

        # 1. 优先提取 markdown 代码块（支持 ```json ... ```、``` ... ```、'''json格式''' ...）
        json_block = None
        # 支持三种常见代码块格式
        patterns = [
            r"```json\s*([\s\S]*?)```",
            r"'''\s*json格式\s*'''([\s\S]*?)($|```|''')",
            r"```([\s\S]*?)```"
        ]
        for pat in patterns:
            match = re.search(pat, content)
            if match:
                json_block = match.group(1).strip()
                break

        # 2. 如果没找到，尝试找第一个 {...}
        if not json_block:
            match = re.search(r'(\{[\s\S]*\})', content)
            if match:
                json_block = match.group(1).strip()

        # 3. 如果还没找到，保留原内容
        if not json_block:
            json_block = content

        # 4. 检查是否为合法 JSON
        if not (json_block.startswith('{') and json_block.endswith('}')):
            print(f"[Warning] 提取到的内容不是完整 JSON: {json_block}")

        print(f"API response content for {data['id']}: {json_block}")
        try:
            parsed_response = json.loads(json_block)
            new_data["response"] = parsed_response

            # 新增部分：调用 search_icon_bbox 函数
            if "interaction_parameter" in parsed_response and "tag" in parsed_response["interaction_parameter"] and "content" in parsed_response["interaction_parameter"]:
                icon_id = parsed_response["interaction_parameter"]["tag"]
                # 此处 coentent 拼写错误，应为 content
                # coentent = parsed_response["interaction_parameter"]["content"]
                content = parsed_response["interaction_parameter"]["content"]
                content_file = data["image"]["som_tags"]
                order_file = data["image"]["som_text"]
                result = search_icon_bbox(icon_id, content, content_file, order_file)
                if result is not None:
                    xc, yc = result
                    new_data["response"]["grounding"] = [xc, yc]
                
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for {data['id']}: {e}")
            new_data["response"] = json_block
        return new_data
    except Exception as e:
        print(f"Error processing {data['id']}: {e}")
        return None

def process_data(input_file_path: str, output_file_path: str, history_knowledge: str, prompt: str):
    """处理数据并将结果写入输出文件"""

    # 修改此处，显式指定编码为 utf-8
    with open(input_file_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)
    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_data = {executor.submit(send_request, data, prompt, history_knowledge): data for data in input_data}
        for future in tqdm(as_completed(future_to_data), total=len(input_data), desc="Processing"):
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                data = future_to_data[future]
                print(f"Error processing {data['id']}: {e}")

    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"Total saved data size: {len(results)}")

def run_interaction_processing(input_file_path, output_file_path, history_knowledge, prompt=planner_prompt):
    process_data(input_file_path, output_file_path, history_knowledge, prompt)


