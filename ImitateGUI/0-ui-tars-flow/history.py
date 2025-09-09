# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import base64
import json
from typing import List, Optional

from utils_history import load_all_entries, append_entry_to_jsonl
import comprehension

from openai import OpenAI

client = OpenAI(
    api_key="sk-b2np5XZBDSzyoYHm7RUSt6bB4bxbUTR13LGRyFbQVilHXeGu",  # 替换为你的 key
    base_url="https://poloai.top/v1"
)

HISTORY_JSONL_PATH = "screenshots/outputs/history.jsonl"

# ========== 工具函数 ==========

def build_action_summaries(entries: List[dict]) -> str:
    """
    构建包含 UI 信息和执行操作总结的完整历史提示内容
    """
    if not entries:
        return "暂无历史操作记录。"

    summaries = []
    for e in entries:
        step = e.get("step_id", "?")
        subtask = e.get("subtask_id", "?")
        ui = e.get("ui_context") or {}
        action = e.get("action") or {}
        # 新增：读取执行结果
        success = e.get("success", None)
        reason = e.get("reason", None)
        # 界面信息
        comprehension = ui.get("comprehension", "页面理解缺失")

        # 操作信息
        target_desc = action.get("interaction_object", "未知目标")
        cmd = action.get("type", "未知命令")

        summary = (
            f"步骤{step}：\n"
            f"子任务：{subtask}\n"
            f"- 页面理解：{comprehension}\n"
            f"- 执行操作：{target_desc}（命令：{cmd}）"
        )
        if success is not None:
            summary += f"\n- 执行结果：{'成功' if success else '失败'}"
        if reason:
            summary += f"\n- 判定说明：{reason}"
        summaries.append(summary)

    return "\n\n".join(summaries)

def generate_guidance_prompt(subtask: str, history_summary: str) -> str:
    """调用 OpenAI API 生成执行器提示词"""
    prompt_text = f"""
你是一个智能执行策略生成器。

当前需要完成的子任务是："{subtask}"。

以下是该任务相关的全部历史记录（包括页面信息和操作记录）：
{history_summary}

请根据这些信息，总结一条具有指导性的建议，用于帮助执行器模型生成最优操作指令。
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一个可靠的任务助手，请根据页面与操作历史生成执行建议。"},
                {"role": "user", "content": prompt_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 请求失败：", e)
        return "生成提示失败，请检查 API 配置。"

def generate_summary(history_summary: str) -> str:
    """生成历史操作记录的总结"""
    summary_prompt = f"""
你是一个历史记录总结生成器。

以下是全部历史操作记录：
{history_summary}

请根据这些信息，总结一条简洁的历史记录总结。要求聚焦于执行的操作。
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一个可靠的历史记录助手，请根据操作历史生成总结。"},
                {"role": "user", "content": summary_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 请求失败：", e)
        return "生成总结失败，请检查 API 配置。"

def get_comprehension(img_path: str):
    """
    根据img_path获取页面理解
    """
    prompt = """以下是用户给出的界面，你需要对界面进行分析，并用精炼的语言描述页面的主要内容和可交互组件。\n"""
    # 读取图片并转换为 Base64 编码
    try:
        with open(img_path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
    except FileNotFoundError:
        print(f"❌ 图片文件未找到：{img_path}")
        return "页面理解失败：图片文件未找到"
    except Exception as e:
        print(f"❌ 图片读取失败：{e}")
        return "页面理解失败：图片读取失败"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "你是页面识别助手，擅长理解页面整体的内容，并给出页面理解"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"API调用出错: {str(e)}"

def get_entry_fields(output_json_path, img_path) -> dict:

    with open(output_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                # 访问列表中的第一个字典元素
                task_id = data[0].get("id",None)
                subtask_id = data[0].get("task", None)
                ui_subtask = data[0].get("response", {}).get("interaction_parameter", {}).get("tag", None)
                comprehension = data[0].get("comprehension", None)
                # cmd = 没有对应的内容
                # target_desc =
                comprehension = get_comprehension(img_path)
                interaction_type = data[0].get("response",{}).get("interaction_type", None)
                interaction_object = data[0].get("response",{}).get("interaction_object", None)
            else:
                print("JSON 文件格式不正确或为空。")
                subtask_id = None
    return {
        "task_id": task_id,
        "subtask_id": subtask_id,
        "ui_context": {"subtask": ui_subtask, "comprehension": comprehension},
        "action": {
            #"cmd": cmd,
            "interaction_object": interaction_object,
            "type": interaction_type,
            #"target_desc": target_desc,
        }
    }

def get_history_knowledge(output_json_path: str):
    """
    只负责加载历史记录、构建历史摘要、生成执行器提示词，返回知识内容。
    """
    # subtask_id = input("请输入当前子任务：").strip()
    try:
        with open(output_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                # 访问列表中的第一个字典元素
                subtask_id = data[0].get("task", None)
                if subtask_id is None:
                    print("task 不存在于 JSON 文件中。")
            else:
                print("JSON 文件格式不正确或为空。")
                subtask_id = None
    except FileNotFoundError:
        print(f"文件 {output_json_path} 未找到。")
        subtask_id = None
    except json.JSONDecodeError:
        print(f"文件 {output_json_path} 不是有效的 JSON 格式。")
        subtask_id = None

    entries = load_all_entries()
    summary = build_action_summaries(entries)
    print("\n✅ 历史操作记录（全部）如下：\n")
    print(summary)
    guidance = generate_guidance_prompt(subtask_id, summary)
    print("\n✅ 给执行器生成的提示词如下：\n")
    print(guidance)
    return {
        "subtask_id": subtask_id,
        "history_summary": summary,
        "guidance": guidance
    }

def save_history_entry(output_json_path: str, img_path):
    """
    从json中获取本轮操作信息
    """
    data = get_entry_fields(output_json_path, img_path)
    entries = load_all_entries()
    summary = build_action_summaries(entries)
    history_summary = generate_summary(summary)
    new_step_id = len(entries) + 1
    new_entry = {
        "task_id": data["task_id"],
        "subtask_id": data["subtask_id"],
        "step_id": new_step_id,
        "history_summary": history_summary,  # 可根据需要补充
        "ui_context": data["ui_context"],
        "action": data["action"]
    }
    append_entry_to_jsonl(HISTORY_JSONL_PATH, new_entry)
    print("\n✅ 已保存当前 entry：")
    print(json.dumps(new_entry, indent=2, ensure_ascii=False))

