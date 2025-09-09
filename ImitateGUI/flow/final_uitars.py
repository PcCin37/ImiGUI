# 版权所有 (C) 2025 bytedance technical flow 模块 - UI-TARS版本
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# 使用UI-TARS模型替换原有的界面理解流程
# --------------------------------------

import os
import subprocess
from datetime import datetime
from PIL import Image
import json
import time
import shutil
from pathlib import Path

# 导入ui-tars模型相关功能
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'ui-tars'))
from project.ImitateAgent.flow.uitars import run as uitars_run, parse_action_output, coordinates_convert, draw_box_and_show, generate_save_path

# 导入评估和历史记录功能
from compare import evaluate_task_success, append_entry_to_jsonl
from check_unloaded_content import check_and_handle_unloaded_content

# 导入历史知识和子任务生成功能
from history import load_all_entries, build_action_summaries, generate_guidance_prompt
from comprehension import encode_image


def get_connected_device() -> str:
    """自动获取第一个已连接且状态为 'device' 的 ADB 设备 ID"""
    try:
        output = subprocess.check_output(['adb', 'devices'], stderr=subprocess.DEVNULL)
        lines = output.decode().strip().splitlines()[1:]
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'device':
                return parts[0]
    except subprocess.CalledProcessError:
        pass
    return None


def get_device_resolution(adb_device_id: str) -> tuple:
    """通过 adb 获取设备分辨率"""
    try:
        output = subprocess.check_output(
            ['adb', '-s', adb_device_id, 'shell', 'wm', 'size'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        # 输出示例: 'Physical size: 1080x1920'
        if ':' in output:
            size = output.split(':', 1)[1].strip()
        else:
            size = output
        width, height = size.split('x')
        return int(width), int(height)
    except Exception:
        # 默认分辨率
        return 1080, 1920


def capture_screenshot(adb_device_id: str, save_path: str) -> str:
    """通过 ADB 截取设备屏幕截图并保存"""
    try:
        subprocess.run(
            ['adb', '-s', adb_device_id, 'shell', 'screencap', '-p', '/sdcard/screenshot.png'],
            check=True
        )
        subprocess.run(
            ['adb', '-s', adb_device_id, 'pull', '/sdcard/screenshot.png', save_path],
            check=True
        )
        print(f"截图已保存至: {save_path}")
        return save_path
    except subprocess.CalledProcessError as e:
        print(f"ADB 截图失败: {e}")
        return None


def get_history_knowledge_simple():
    """
    简化版的历史知识获取，不依赖output.json文件
    """
    try:
        entries = load_all_entries()
        summary = build_action_summaries(entries)
        print("\n✅ 历史操作记录（全部）如下：\n")
        print(summary)
        guidance = generate_guidance_prompt(None, summary)
        print("\n✅ 给执行器生成的提示词如下：\n")
        print(guidance)
        return {
            "subtask_id": None,
            "history_summary": summary,
            "guidance": guidance
        }
    except Exception as e:
        print(f"获取历史知识失败: {e}")
        return {
            "subtask_id": None,
            "history_summary": "暂无历史记录",
            "guidance": "这是第一次操作，请根据任务描述执行相应操作。"
        }


def generate_subtask_simple(screenshot_path: str, whole_task: str, history_knowledge: dict):
    """
    简化版的子任务生成，基于截图和全局任务
    """
    try:
        # 读取历史记录，过滤已成功的子任务
        history_entries = load_all_entries()
        finished_subtasks = set()
        for entry in history_entries:
            if entry.get("subtask_id") and entry.get("success") is True:
                finished_subtasks.add(entry["subtask_id"])

        # 编码图片
        image_base64 = encode_image(screenshot_path)
        
        # 新增：历史摘要内容
        history_summary = history_knowledge.get("history_summary", "暂无历史记录")

        # 构造prompt
        prompt = f"""
你是一个UI任务分解专家。全局任务是：{whole_task}

请根据以下内容，推理并生成本页面的【单步交互操作】（task）：
1. 当前界面截图（已上传）
2. 历史操作记录摘要：
{history_summary}

【要求】：
- task应该是这个页面需要执行的操作，具体如何操作如"点击xx按钮"会在后续步骤中输出，无需在当前task生成中输出。
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

        # 这里可以调用大模型API来生成子任务
        # 为了简化，我们返回一个基于全局任务的默认子任务
        # 在实际部署时，您可以添加大模型API调用
        
        # 简化版：基于全局任务和历史记录生成子任务
        if not finished_subtasks:
            subtask = f"开始执行任务：{whole_task}"
        else:
            subtask = f"继续执行任务：{whole_task}"
        
        print(f"生成的子任务: {subtask}")
        return subtask
        
    except Exception as e:
        print(f"生成子任务失败: {e}")
        return f"执行任务：{whole_task}"


def process_screenshot_with_uitars(screenshot_path: str, task_description: str, step_count: int, width: int, height: int):
    """
    使用UI-TARS模型处理截图并生成操作
    
    Args:
        screenshot_path: 截图路径
        task_description: 任务描述
        step_count: 当前步骤数
        width: 设备宽度
        height: 设备高度
    
    Returns:
        dict: 包含模型输出和处理结果的字典
    """
    print(f"使用UI-TARS模型分析截图: {screenshot_path}")
    print(f"全局任务描述: {task_description}")
    
    # 第一步：获取历史知识
    print("获取历史摘要和建议信息...")
    history_knowledge = get_history_knowledge_simple()
    
    # 第二步：生成当前页面的子任务
    print("根据全局任务生成当前页面子任务...")
    current_subtask = generate_subtask_simple(screenshot_path, task_description, history_knowledge)
    
    # 第三步：构造增强的任务描述，包含历史知识和子任务
    enhanced_task_description = f"""
全局任务：{task_description}
当前子任务：{current_subtask}

历史操作指导：
{history_knowledge.get('guidance', '这是第一次操作，请根据任务描述执行相应操作。')}

请根据当前界面和上述上下文信息，执行最合适的操作。
"""
    
    print(f"增强后的任务描述:")
    print(enhanced_task_description)
    
    # 调用UI-TARS模型
    try:
        model_response = uitars_run(screenshot_path, enhanced_task_description)
        print("模型原始响应:")
        print(model_response)
        
        # 解析模型输出
        parsed_output = json.loads(parse_action_output(model_response))
        print("解析后的输出:")
        print(json.dumps(parsed_output, ensure_ascii=False, indent=2))
        
        # 加载图片获取尺寸
        image = Image.open(screenshot_path)
        img_width, img_height = image.size
        
        # 转换坐标（如果存在）
        start_abs = None
        end_abs = None
        if parsed_output.get("start_box"):
            start_abs = coordinates_convert(parsed_output["start_box"], image.size)
            print(f"起始框绝对坐标: {start_abs}")
        
        if parsed_output.get("end_box"):
            end_abs = coordinates_convert(parsed_output["end_box"], image.size)
            print(f"结束框绝对坐标: {end_abs}")
        
        # 创建输出文件夹
        image_name = os.path.splitext(os.path.basename(screenshot_path))[0]
        outputs_folder = "screenshots/outputs"
        image_folder = os.path.join(outputs_folder, image_name)
        os.makedirs(image_folder, exist_ok=True)
        
        # 保存可视化结果
        annotated_save_path = os.path.join(image_folder, f"{image_name}_annotated.png")
        draw_box_and_show(
            image, 
            start_abs, 
            end_abs, 
            parsed_output.get("direction"),
            save_path=annotated_save_path,
            show_image=False
        )
        
        # 保存分析结果JSON
        analysis_result = {
            "step_id": step_count,
            "global_task": task_description,
            "current_subtask": current_subtask,
            "enhanced_task_description": enhanced_task_description,
            "history_knowledge": history_knowledge,
            "screenshot_path": screenshot_path,
            "model_response": model_response,
            "parsed_action": parsed_output,
            "absolute_coordinates": {
                "start_box": start_abs,
                "end_box": end_abs,
                "direction": parsed_output.get("direction")
            },
            "device_resolution": {"width": width, "height": height},
            "image_size": {"width": img_width, "height": img_height},
            "annotated_image": annotated_save_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        analysis_json_path = os.path.join(image_folder, f"{image_name}_analysis.json")
        with open(analysis_json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        print(f"分析结果已保存到: {analysis_json_path}")
        print(f"可视化图片已保存到: {annotated_save_path}")
        
        # 生成ADB命令
        adb_commands = generate_adb_commands_from_action(parsed_output, start_abs, end_abs, adb_device_id=None)
        
        # 保存ADB命令
        adb_commands_path = os.path.join(image_folder, f"{image_name}_adb_commands.json")
        with open(adb_commands_path, 'w', encoding='utf-8') as f:
            json.dump(adb_commands, f, ensure_ascii=False, indent=2)
        
        print(f"ADB命令已保存到: {adb_commands_path}")
        
        return {
            "analysis_result": analysis_result,
            "analysis_json_path": analysis_json_path,
            "adb_commands": adb_commands,
            "adb_commands_path": adb_commands_path,
            "image_folder": image_folder
        }
        
    except Exception as e:
        print(f"UI-TARS模型处理失败: {e}")
        return None


def generate_adb_commands_from_action(parsed_action: dict, start_abs: list, end_abs: list, adb_device_id: str) -> dict:
    """
    根据UI-TARS模型的输出生成ADB命令
    
    Args:
        parsed_action: 解析后的动作
        start_abs: 起始坐标（绝对坐标）
        end_abs: 结束坐标（绝对坐标）
        adb_device_id: ADB设备ID
    
    Returns:
        dict: ADB命令字典
    """
    action_type = parsed_action.get("action", "")
    commands = []
    
    if action_type == "click":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            commands.append(f"adb shell input tap {center_x} {center_y}")
    
    elif action_type == "left_double":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            commands.append(f"adb shell input tap {center_x} {center_y}")
            commands.append("sleep 0.1")
            commands.append(f"adb shell input tap {center_x} {center_y}")
    
    elif action_type == "right_single":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            # 长按实现右键（Android中通常用长按）
            commands.append(f"adb shell input swipe {center_x} {center_y} {center_x} {center_y} 1000")
    
    elif action_type == "drag":
        if start_abs and end_abs:
            start_x = (start_abs[0] + start_abs[2]) // 2
            start_y = (start_abs[1] + start_abs[3]) // 2
            end_x = (end_abs[0] + end_abs[2]) // 2
            end_y = (end_abs[1] + end_abs[3]) // 2
            commands.append(f"adb shell input swipe {start_x} {start_y} {end_x} {end_y} 500")
    
    elif action_type == "scroll":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            direction = parsed_action.get("direction", "down")
            
            if direction == "down":
                commands.append(f"adb shell input swipe {center_x} {center_y} {center_x} {center_y - 500} 300")
            elif direction == "up":
                commands.append(f"adb shell input swipe {center_x} {center_y} {center_x} {center_y + 500} 300")
            elif direction == "left":
                commands.append(f"adb shell input swipe {center_x} {center_y} {center_x + 500} {center_y} 300")
            elif direction == "right":
                commands.append(f"adb shell input swipe {center_x} {center_y} {center_x - 500} {center_y} 300")
    
    elif action_type == "type":
        content = parsed_action.get("content", "")
        if content:
            # 转义特殊字符
            content = content.replace(" ", "%s").replace("&", "\\&")
            commands.append(f"adb shell input text '{content}'")
    
    elif action_type == "hotkey":
        key = parsed_action.get("key", "")
        key_mapping = {
            "enter": "KEYCODE_ENTER",
            "back": "KEYCODE_BACK",
            "home": "KEYCODE_HOME",
            "menu": "KEYCODE_MENU",
            "escape": "KEYCODE_ESCAPE",
            "delete": "KEYCODE_DEL",
            "backspace": "KEYCODE_DEL"
        }
        if key.lower() in key_mapping:
            commands.append(f"adb shell input keyevent {key_mapping[key.lower()]}")
    
    elif action_type == "wait":
        commands.append("sleep 5")
    
    elif action_type == "finished":
        commands.append("echo 'Task completed'")
    
    return {
        "action_type": action_type,
        "parsed_action": parsed_action,
        "coordinates": {
            "start_abs": start_abs,
            "end_abs": end_abs
        },
        "commands": commands,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def execute_adb_commands(adb_commands: dict, adb_device_id: str) -> bool:
    """
    执行ADB命令
    
    Args:
        adb_commands: ADB命令字典
        adb_device_id: ADB设备ID
    
    Returns:
        bool: 执行是否成功
    """
    commands = adb_commands.get("commands", [])
    if not commands:
        print("没有需要执行的ADB命令")
        return True
    
    print("开始执行ADB命令:")
    for i, cmd in enumerate(commands):
        print(f"  {i+1}. {cmd}")
        
        if cmd.startswith("sleep"):
            # 处理sleep命令
            sleep_time = float(cmd.split()[1])
            time.sleep(sleep_time)
        elif cmd.startswith("echo"):
            # 处理echo命令
            print(cmd)
        else:
            # 处理adb命令
            if not cmd.startswith("adb"):
                cmd = f"adb -s {adb_device_id} {cmd}"
            else:
                # 在adb后添加设备ID
                cmd = cmd.replace("adb ", f"adb -s {adb_device_id} ")
            
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"命令执行失败: {cmd}")
                    print(f"错误信息: {result.stderr}")
                    return False
                else:
                    print(f"命令执行成功: {cmd}")
            except Exception as e:
                print(f"执行命令时出错: {e}")
                return False
    
    print("所有ADB命令执行完成")
    return True


def append_step_log(step_log_path, step_id, before_img, after_img, reason, action_info):
    """
    追加写入每步的图像路径和操作描述到 step_log.jsonl
    """
    log_entry = {
        "step_id": step_id,
        "before_img": before_img,
        "after_img": after_img,
        "reason": reason,
        "action_info": action_info,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(step_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def main():
    # 首先获取全局任务描述（支持多行输入，输入 END 结束）
    print("请输入全局任务描述（支持多行，输入单独一行 END 结束）：")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    whole_task = "\n".join(lines)
    
    # 自动检测设备ID
    adb_device_id = get_connected_device()
    if not adb_device_id:
        print("未检测到已连接的 ADB 设备，请检查连接后重试。")
        return
    print(f"检测到设备ID: {adb_device_id}")

    # 自动获取分辨率
    width, height = get_device_resolution(adb_device_id)
    print(f"设备分辨率: {width}x{height}")

    # 文件夹设置
    img_folder = "screenshots/img"
    outputs_folder = "screenshots/outputs"
    os.makedirs(img_folder, exist_ok=True)
    os.makedirs(outputs_folder, exist_ok=True)

    step_count = 1
    current_screenshot = None  # 用于存储当前需要处理的截图
    
    # 开始循环执行
    while True:
        print(f"\n=== 第 {step_count} 步操作 ===")
        print(f"全局任务: {whole_task}")
        
        # 如果没有当前截图，则进行初始截图
        if current_screenshot is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(img_folder, f"screenshot_step{step_count}_{timestamp}.png")
            current_screenshot = capture_screenshot(adb_device_id, screenshot_path)
            if not current_screenshot:
                print("截图失败，停止执行")
                break
        else:
            # 使用上一步处理完ADB操作后的截图
            screenshot_path = current_screenshot

        # 使用UI-TARS模型处理截图
        process_result = process_screenshot_with_uitars(
            screenshot_path, 
            whole_task, 
            step_count, 
            width, 
            height
        )
        
        if not process_result:
            print("UI-TARS模型处理失败，跳过当前步骤")
            break
        
        # 执行ADB命令
        print("开始执行生成的ADB命令...")
        success = execute_adb_commands(process_result["adb_commands"], adb_device_id)
        
        if not success:
            print("ADB命令执行失败")
            # 询问是否继续
            user_input = input("ADB命令执行失败，是否继续下一步？(y/n): ").strip().lower()
            if user_input not in ['y', 'yes', '']:
                break
        
        print(f"\n第 {step_count} 步操作处理完成")
        print("等待界面切换...")
        
        # 等待界面切换
        time.sleep(2)  # 等待2秒确保界面稳定
        
        # 截图捕获新界面
        print("正在截图捕获新界面...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        next_screenshot_path = os.path.join(img_folder, f"screenshot_step{step_count + 1}_{timestamp}.png")
        next_screenshot = capture_screenshot(adb_device_id, next_screenshot_path)
        
        if not next_screenshot:
            print("新界面截图失败")
            current_screenshot = None
        else:
            print(f"新界面截图已保存: {next_screenshot}")
            
            # 评估本轮任务是否执行成功
            result = evaluate_task_success(screenshot_path, next_screenshot, process_result["analysis_json_path"])
            print("本轮子任务执行判定：", result)
            
            # 记录历史
            analysis_result = process_result["analysis_result"]
            parsed_action = analysis_result["parsed_action"]
            
            entry = {
                "task_id": whole_task,
                "subtask_id": analysis_result.get("current_subtask", ""),
                "step_id": step_count,
                "ui_context": {
                    "subtask": analysis_result.get("current_subtask", ""),
                    "comprehension": parsed_action.get("thought", ""),
                    "global_task": whole_task
                },
                "action": {
                    "interaction_object": parsed_action.get("action", ""),
                    "type": parsed_action.get("action", ""),
                    "coordinates": analysis_result["absolute_coordinates"]
                },
                "before_img": screenshot_path,
                "after_img": next_screenshot,
                "response_json": process_result["analysis_json_path"],
                "success": result.get("success"),
                "reason": result.get("reason")
            }
            append_entry_to_jsonl("history.jsonl", entry)
            
            # 写入step_log.jsonl
            append_step_log(
                "step_log.jsonl", 
                step_count, 
                screenshot_path, 
                next_screenshot, 
                result.get("reason"),
                {
                    "action_type": parsed_action.get("action"),
                    "thought": parsed_action.get("thought"),
                    "coordinates": analysis_result["absolute_coordinates"]
                }
            )
            
            # 判断未加载内容并处理
            next_screenshot = check_and_handle_unloaded_content(
                current_img_path=screenshot_path,
                after_img_path=next_screenshot,
                response_json_path=process_result["analysis_json_path"],
                adb_device_id=adb_device_id,
                img_folder=img_folder,
                step_count=step_count
            )
            
            current_screenshot = next_screenshot
            
            # 检查是否已完成任务
            if parsed_action.get("action") == "finished":
                print("任务已完成！")
                break
        
        # 询问是否继续下一步
        user_input = input("\n是否继续下一步操作？(y/n，或输入'q'退出): ").strip().lower()
        
        if user_input in ['n', 'no', 'q', 'quit', 'exit']:
            print("用户选择退出，程序结束")
            break
        elif user_input in ['y', 'yes', '']:
            step_count += 1
            print("准备处理新界面...")
            continue
        else:
            print("输入无效，默认继续下一步")
            step_count += 1
            continue


if __name__ == "__main__":
    main() 