# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import json
import base64
from openai import OpenAI
from utils_history import append_entry_to_jsonl

client = OpenAI(
    api_key="sk-b2np5XZBDSzyoYHm7RUSt6bB4bxbUTR13LGRyFbQVilHXeGu",  # 替换为你的 key
    base_url="https://poloai.top/v1"
)

HISTORY_JSONL_PATH = "screenshots/outputs/history.jsonl"

def encode_image_to_base64(img_path):
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def append_entry_to_jsonl(file_path, entry: dict):
    with open(file_path, "a", encoding="utf-8") as f:
        json.dump({"history_entry": entry}, f, ensure_ascii=False)
        f.write("\n")

def evaluate_task_success(before_img, after_img, response_json):
    # 读取response_json
    with open(response_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 获取子任务信息 - 修改为适配新的数据结构
    if isinstance(data, dict):
        # 如果是字典格式，直接使用
        task_info = data
    elif isinstance(data, list) and len(data) > 0:
        # 如果是列表格式，取第一个
        task_info = data[0]
    else:
        # 默认空字典
        task_info = {}
    
    # 提取子任务描述
    current_subtask = task_info.get("current_subtask", "未知子任务")
    global_task = task_info.get("global_task", "未知全局任务")
    parsed_action = task_info.get("parsed_action", {})
    action_type = parsed_action.get("action", "未知操作")
    thought = parsed_action.get("thought", "")

    # 编码图片
    before_b64 = encode_image_to_base64(before_img)
    after_b64 = encode_image_to_base64(after_img)

    # 构造更详细的prompt，包含子任务信息
    prompt = f"""
你是一个UI自动化执行结果判定助手。

【全局任务】：{global_task}
【当前子任务】：{current_subtask}
【执行的操作】：{action_type}
【操作思路】：{thought}

下面是本次操作的详细信息：
{json.dumps(task_info, ensure_ascii=False, indent=2)}

【重要说明 - 操作前截图标注含义】：
操作前截图中的红色方框标注表示AI模型识别出的可交互UI元素，这些标注有以下含义：
- 红色方框：标识出当前界面中已经执行交互操作的UI组件
- 蓝色线段与箭头：已经执行的活动操作，箭头代表滑动方向，线段代表滑动的起点终点与滑动距离
- 标注目的：帮助你理解AI模型"看到"了哪些交互元素，以及已经操作的目标区域
- 判断依据：你可以根据标注区域来判断操作是否准确命中了预期的UI元素

请对比"操作前截图"和"操作后截图"，判断本次子任务是否执行成功，并简要说明理由。

【核心判断原则】：
- 对于输入文本类操作，唯一成功的标准是：输入框中出现了对应的文本内容
- 其他任何界面变化（如颜色变化、按钮状态变化、光标闪烁等）都不能作为成功的判断依据

【判断标准】：
1. 如果操作后界面发生了符合子任务描述的预期变化，则判定为成功
2. 如果操作后界面没有变化或变化不符合预期，则判定为失败
3. 如果操作后进入了错误页面或出现了错误提示，则判定为失败
4. 结合操作前截图的标注，判断是否正确操作了预期的UI元素

【特殊判断规则】：
- 对于"点击输入框"类操作：只有当输入框明显获得焦点（如出现光标、边框高亮、键盘弹出等）时才判定为成功
- 对于"输入文本"类操作：【重要】判断标准是输入框中是否出现了对应的文本内容，而不是其他任何变化。只有看到文本内容确实出现在输入框中才判定为成功，其他任何变化（如界面颜色变化、按钮状态变化等）都不能作为成功的判断依据
- 对于"搜索"类操作：只有当搜索框被点击并获得焦点时才判定为成功，输入搜索内容后需要看到搜索按钮可点击或搜索结果出现才判定为成功
- 对于"type"类操作：【重要】判断标准是输入框中是否出现了对应的文本内容，必须看到实际输入的文本才判定为成功
- 如果只是界面轻微变化（如按钮颜色变化、光标闪烁等）但不符合子任务预期，应判定为失败
- 参考操作前截图的红色标注区域，判断操作是否准确命中了预期的交互元素

请严格按照如下JSON格式输出：
{{
  "success": true/false,
  "reason": "简要说明成功或失败的原因，可结合标注区域分析操作准确性"
}}
"""

    # 发送到大模型
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{before_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{after_b64}"}}
            ]}
        ]
    )
    content = response.choices[0].message.content.strip()
    
    # 尝试提取JSON
    import re
    match = re.search(r'(\{[\s\S]*\})', content)
    if match:
        try:
            result = json.loads(match.group(1))
        except json.JSONDecodeError:
            result = {"success": None, "reason": f"JSON解析失败: {content}"}
    else:
        result = {"success": None, "reason": f"未找到JSON格式结果: {content}"}

    # 添加调试信息
    print(f"【任务判断调试信息】")
    print(f"子任务: {current_subtask}")
    print(f"操作类型: {action_type}")
    print(f"判断结果: {result}")
    
    return result

def main():
    before_img = input("请输入操作前截图路径: ").strip()
    after_img = input("请输入操作后截图路径: ").strip()
    response_json = input("请输入本轮response_json路径: ").strip()

    result = evaluate_task_success(before_img, after_img, response_json)
    print("判定结果：", result)

    # 写入history
    entry = {
        "before_img": before_img,
        "after_img": after_img,
        "response_json": response_json,
        "success": result.get("success"),
        "reason": result.get("reason")
    }
    append_entry_to_jsonl(HISTORY_JSONL_PATH, entry)
    print("已写入history.jsonl")

if __name__ == "__main__":
    main()