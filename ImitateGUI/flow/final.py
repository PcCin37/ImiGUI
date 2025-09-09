# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import subprocess
from datetime import datetime
from PIL import Image
import shutil
import sys
import json
import time

# 导入 som.py 中的相关方法
from som import process_image, sort_tags, mark_on_image  # 确保 som.py 在同一目录或者设置了正确的路径

# 导入后续交互处理模块
from comprehension import analyze_ui_folder, generate_subtask_for_page
from delete import extract_icon_content
from generate_json_for_folder import generate_json_for_folder
from history import get_history_knowledge, save_history_entry, get_comprehension
from interaction_processor import run_interaction_processing
from output import run_adb_command_generator
from compare import evaluate_task_success, append_entry_to_jsonl

# 导入check_unloaded_content的函数
from check_unloaded_content import check_and_handle_unloaded_content


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
        # time.sleep(20)  # 增加延时，确保截图文件写入完成
        subprocess.run(
            ['adb', '-s', adb_device_id, 'pull', '/sdcard/screenshot.png', save_path],
            check=True
        )
        print(f"截图已保存至: {save_path}")
        return save_path
    except subprocess.CalledProcessError as e:
        print(f"ADB 截图失败: {e}")
        return None


def process_folder(folder_path: str, whole_task: str, width: int, height: int, original_screenshot_path: str):
    """
    对给定 UI 分析文件夹进行后续交互流程：
    1. 分析 UI
    2. 提取 icon 内容
    3. 生成 JSON
    4. 生成子 task
    5. 获取历史摘要并推理
    6. 生成 ADB 执行命令（包含自动分辨率）
    """
    print(f"全局任务: {whole_task}")
    print(f"开始处理 UI 分析文件夹: {folder_path}") 

    analyze_ui_folder(folder_path)
    print("UI 分析完成，开始提取 icon 内容...")
    extract_icon_content(folder_path)
    print("icon 内容提取完成，开始生成 JSON...")
    generate_json_for_folder(folder_path)

    folder_name = os.path.basename(os.path.normpath(folder_path))
    input_json = os.path.join(folder_path, f"{folder_name}_output.json")
    response_json = os.path.join(folder_path, f"{folder_name}_response.json")

    print("获取历史摘要和建议信息...")
    history_knowledge = get_history_knowledge(input_json)

    print("根据全局任务生成当前页面子 task...")
    generate_subtask_for_page(folder_path, whole_task, history_knowledge)

    print("开始批量交互推理...")
    run_interaction_processing(input_json, response_json, history_knowledge)

    print("保存本轮操作历史...")

    adb_output_json = os.path.join(folder_path, f"{folder_name}_adb_commands.json")
    print(f"生成 ADB 执行命令 (分辨率 {width}x{height})...")
    run_adb_command_generator(
        # width=width,
        # height=height,
        input_file=response_json,
        output_file=adb_output_json
    )

    print("处理完成。")


def append_step_log(step_log_path, step_id, before_img, after_img, reason):
    """
    追加写入每步的图像路径和操作描述到 step_log.jsonl
    """
    log_entry = {
        "step_id": step_id,
        "before_img": before_img,
        "after_img": after_img,
        "reason": reason
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

        # 创建分析输出文件夹
        image_name = os.path.splitext(os.path.basename(screenshot_path))[0]
        image_folder = os.path.join(outputs_folder, image_name)
        os.makedirs(image_folder, exist_ok=True)

        # 执行 SOM 预处理
        processed_image_path, processed_text_path = process_image(
            screenshot_path,
            box_threshold=0.05,
            iou_threshold=0.1,
            use_paddleocr=True,
            imgsz=640
        )

        # 移动结果到输出目录
        target_img = os.path.join(image_folder, f"{image_name}_original_img.jpg")
        target_txt = os.path.join(image_folder, f"{image_name}_parsed.txt")
        shutil.move(processed_image_path, target_img)
        shutil.move(processed_text_path, target_txt)

        print(f"处理后的图像: {target_img}")
        print(f"解析内容: {target_txt}")

        # 排序标签并保存
        sorted_lines, sorted_tags = sort_tags(target_txt)
        tags_file = os.path.join(image_folder, f"{image_name}_tags_order.txt")
        with open(tags_file, 'w', encoding='utf-8') as f:
            for line in sorted_lines:
                f.write(line + '\n')
        print(f"排序后的标签: {tags_file}")

        # 在原图上标注并保存
        mark_on_image(screenshot_path, target_img, sorted_tags)
        revised_image = os.path.join(image_folder, f"{image_name}_som_img.jpg")
        print(f"标注后的图像: {revised_image}")

        # 调用后续交互流程，传入自动获取的分辨率和原始截图路径
        process_folder(image_folder, whole_task=whole_task, width=width, height=height, original_screenshot_path=screenshot_path)
        
        print(f"\n第 {step_count} 步操作处理完成")
        print("ADB命令已生成并将自动执行，等待界面切换...")
        
        # 等待ADB命令自动执行和界面切换
        import time
        
        # 立即截图捕获新界面
        print("正在截图捕获新界面...")
        time.sleep(1)  # 稍等1秒确保界面稳定
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        next_screenshot_path = os.path.join(img_folder, f"screenshot_step{step_count + 1}_{timestamp}.png")
        next_screenshot = capture_screenshot(adb_device_id, next_screenshot_path)
        
        if not next_screenshot:
            print("新界面截图失败")
            current_screenshot = None
        else:
            print(f"新界面截图已保存: {next_screenshot}")
            # === 新增：自动评估本轮子任务是否执行成功 ===
            # response_json 路径
            folder_name = os.path.basename(os.path.normpath(image_folder))
            response_json = os.path.join(image_folder, f"{folder_name}_response.json")
            # 调用评估函数
            result = evaluate_task_success(screenshot_path, next_screenshot, response_json)
            print("本轮子任务执行判定：", result)
            # 读取 response_json，提取操作参数
            with open(response_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                task_id = item.get("id")
                subtask_id = item.get("task")
                response = item.get("response", {})
                if isinstance(response, dict):
                    interaction_parameter = response.get("interaction_parameter", {})
                    tag = interaction_parameter.get("tag")
                    interaction_object = response.get("interaction_object")
                    interaction_type = response.get("interaction_type")
                else:
                    tag = None
                    interaction_object = None
                    interaction_type = None
                ui_context = {
                    "subtask": tag,
                    "comprehension": get_comprehension(screenshot_path)
                }
                action = {
                    "interaction_object": interaction_object,
                    "type": interaction_type
                }
            else:
                task_id = subtask_id = ui_context = action = None
            entry = {
                "task_id": task_id,
                "subtask_id": subtask_id,
                "step_id": step_count,
                "ui_context": ui_context,
                "action": action,
                "before_img": screenshot_path,
                "after_img": next_screenshot,
                "response_json": response_json,
                "success": result.get("success"),
                "reason": result.get("reason")
            }
            append_entry_to_jsonl("history.jsonl", entry)
            # 新增：写入step_log.jsonl
            append_step_log("step_log.jsonl", step_count, screenshot_path, next_screenshot, result.get("reason"))
            # === 新增：判断未加载内容并处理 ===
            # next_screenshot 可能会被替换为重新截图
            next_screenshot = check_and_handle_unloaded_content(
                current_img_path=screenshot_path,
                after_img_path=next_screenshot,
                response_json_path=response_json,
                adb_device_id=adb_device_id,
                img_folder=img_folder,
                step_count=step_count
            )
            current_screenshot = next_screenshot

        
        
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
