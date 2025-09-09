# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import json
import os
import subprocess
import urllib.parse
from typing import Dict, List, Any

class ADBCommandGenerator:
    def __init__(self):
        self.adb_commands = []
        self.screen_width = 1080  # 默认屏幕宽度
        self.screen_height = 1920  # 默认屏幕高度

    def get_device_resolution(self):
        """通过 ADB 命令获取设备的屏幕分辨率"""
        try:
            result = subprocess.run(['adb', 'shell', 'wm', 'size'], capture_output=True, text=True, check=True)
            resolution = result.stdout.strip().split(':')[1].strip()
            width, height = resolution.split('x')
            self.screen_width = int(width)
            self.screen_height = int(height)
            print(f"设备分辨率: {self.screen_width}x{self.screen_height}")
        except subprocess.CalledProcessError as e:
            print(f"获取设备分辨率失败: {e}")
            # 如果获取失败，使用默认分辨率
            self.screen_width = 1080
            self.screen_height = 1920

    def set_screen_resolution(self, width: int, height: int):
        """手动设置屏幕分辨率"""
        self.screen_width = width
        self.screen_height = height

    def convert_coordinates(self, grounding: List[float]) -> tuple:
        """
        将相对坐标转换为绝对像素坐标
        grounding: [x_ratio, y_ratio] (0-1之间的比例)
        返回: (x_pixel, y_pixel)
        """
        x_pixel = int(grounding[0] * self.screen_width)
        y_pixel = int(grounding[1] * self.screen_height)
        return x_pixel, y_pixel

    def generate_tap_command(self, grounding: List[float]) -> str:
        """生成点击命令"""
        x, y = self.convert_coordinates(grounding)
        return f"adb shell input tap {x} {y}"

    def generate_swipe_left_command(self, grounding: List[float] = None) -> str:
        """生成左滑命令"""
        if grounding and len(grounding) == 4:
            x1 = int(grounding[0] * self.screen_width) + 100
            x2 = int(grounding[2] * self.screen_width) - 200
            y1 = grounding[1]
            y2 = grounding[3]
            y_center = int(((y1 + y2) / 2) * self.screen_height)
            # 左滑：从右往左
            return f"adb shell input swipe {x2} {y_center} {x1} {y_center} 300"
        return ""

    def generate_swipe_right_command(self, grounding: List[float] = None) -> str:
        """生成右滑命令"""
        if grounding and len(grounding) == 4:
            x1 = int(grounding[0] * self.screen_width) + 200
            x2 = int(grounding[2] * self.screen_width) - 100
            y1 = grounding[1]
            y2 = grounding[3]
            y_center = int(((y1 + y2) / 2) * self.screen_height)
            # 右滑：从左往右
            return f"adb shell input swipe {x1} {y_center} {x2} {y_center} 300"
        return ""

    def generate_swipe_command(self, interaction_type: str, grounding: List[float] = None) -> str:
        """生成滑动命令，支持swipe_left、swipe_right等自定义区域滑动"""
        if interaction_type == "swipe_next_video":
            # 从屏幕下方向上滑动（模拟查看下一个视频）
            start_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.8)
            end_x = self.screen_width // 2
            end_y = int(self.screen_height * 0.2)
            return f"adb shell input swipe {start_x} {start_y} {end_x} {end_y} 300"
        elif interaction_type == "swipe_up":
            # 向下滑动（页面向上滚动，查看更多内容）
            start_x = self.screen_width // 2
            start_y = int(self.screen_height * 0.9)
            end_x = self.screen_width // 2
            end_y = int(self.screen_height * 0.5)
            return f"adb shell input swipe {start_x} {start_y} {end_x} {end_y} 300"
        return ""

    def generate_long_press_command(self, grounding: List[float] = None) -> str:
        """生成长按命令"""
        if grounding:
            x, y = self.convert_coordinates(grounding)
        else:
            # 如果没有具体坐标，使用屏幕中心
            x = self.screen_width // 2
            y = self.screen_height // 2

        # 长按命令（按住1000毫秒）
        return f"adb shell input touchscreen swipe {x} {y} {x} {y} 1000"

    def generate_double_tap_command(self, interaction_type: str) -> str:
        """生成双击命令"""
        if interaction_type == "double_tap":
            x = self.screen_width // 2
            y = self.screen_height // 2
            # 两次tap命令，间隔100毫秒
            return f"adb shell input tap {x} {y} && adb shell input tap {x} {y}"
        else:
            return ""

    def generate_input_text_command(self, text: str) -> str:
        """通过ADB Keyboard输入中文和特殊字符"""
        return f'adb shell am broadcast -a ADB_INPUT_TEXT --es msg "{text}"'

    def process_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个response数据"""
        interaction_type = response_data.get("interaction_type", "")
        interaction_param = response_data.get("interaction_parameter", {})

        adb_command = ""
        command_description = ""

        if interaction_type == "tap":
            grounding = interaction_param.get("grounding") or response_data.get("grounding")
            if grounding:
                adb_command = self.generate_tap_command(grounding)
                x, y = self.convert_coordinates(grounding)
                command_description = f"点击坐标 ({x}, {y})"

                # 如果有tag和content信息，添加到描述中
                tag = interaction_param.get("tag", "")
                content = interaction_param.get("content", "")
                if content:
                    command_description += f" - 点击元素: {content}"
                if tag:
                    command_description += f" (标签: {tag})"

        elif interaction_type == "swipe_next_video":
            adb_command = self.generate_swipe_command(interaction_type)
            command_description = "向上滑动查看下一个视频"

        elif interaction_type == "swipe_up":
            adb_command = self.generate_swipe_command(interaction_type)
            command_description = "滑动查看更多内容"

        elif interaction_type == "swipe_left":
            grounding = interaction_param.get("grounding") or response_data.get("grounding")
            if grounding and len(grounding) == 4:
                adb_command = self.generate_swipe_left_command(grounding)
                x1 = int(grounding[0] * self.screen_width) + 100
                x2 = int(grounding[2] * self.screen_width) - 200
                y1 = grounding[1]
                y2 = grounding[3]
                y_center = int(((y1 + y2) / 2) * self.screen_height)
                command_description = f"左滑 区域: 起点({x2},{y_center}) 终点({x1},{y_center})"
            else:
                command_description = "左滑，但未提供有效grounding参数"

        elif interaction_type == "swipe_right":
            grounding = interaction_param.get("grounding") or response_data.get("grounding")
            if grounding and len(grounding) == 4:
                adb_command = self.generate_swipe_right_command(grounding)
                x1 = int(grounding[0] * self.screen_width) + 200
                x2 = int(grounding[2] * self.screen_width) - 100
                y1 = grounding[1]
                y2 = grounding[3]
                y_center = int(((y1 + y2) / 2) * self.screen_height)
                command_description = f"右滑 区域: 起点({x1},{y_center}) 终点({x2},{y_center})"
            else:
                command_description = "右滑，但未提供有效grounding参数"

        elif interaction_type == "long_press_menu":
            grounding = interaction_param.get("grounding") or response_data.get("grounding")
            adb_command = self.generate_long_press_command(grounding)
            if grounding:
                x, y = self.convert_coordinates(grounding)
                command_description = f"长按坐标 ({x}, {y}) 打开菜单"
            else:
                command_description = "长按屏幕中心打开菜单"

        elif interaction_type == "double_tap":
            adb_command = self.generate_double_tap_command(interaction_type)
            command_description = f"双击屏幕中心"

        elif interaction_type == "input_text":
            text = interaction_param.get("text") or response_data.get("text")
            if text:
                adb_command = self.generate_input_text_command(text)
                command_description = f"输入文字: {text}"

        return {
            "interaction_type": interaction_type,
            "interaction_parameter": interaction_param,
            "adb_command": adb_command,
            "command_description": command_description
        }

    def process_json_file(self, input_file: str, output_file: str):
        """处理输入的JSON文件并直接执行ADB命令"""
        try:
            # 获取设备分辨率
            self.get_device_resolution()

            # 读取输入文件
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 处理每个任务
            for item in data:
                task_id = item.get("id", "")
                task = item.get("task", "")
                response = item.get("response", {})

                # 处理response数据
                processed_response = self.process_response(response)

                # 执行ADB命令
                adb_command = processed_response["adb_command"]
                if adb_command:
                    self.execute_adb_command(adb_command)

                # 添加 ADB 执行命令记录
                item['adb_command_executed'] = adb_command

            # 保存处理结果到新文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"处理完成，新的文件已保存到: {output_file}")

        except FileNotFoundError:
            print(f" 错误: 找不到输入文件 {input_file}")
        except json.JSONDecodeError:
            print(f" 错误: {input_file} 不是有效的JSON文件")
        except Exception as e:
            print(f" 处理文件时发生错误: {str(e)}")

    def execute_adb_command(self, command: str):
        """直接在终端执行ADB命令"""
        try:
            print(f"执行命令: {command}")
            subprocess.run(command, shell=True, check=True)
            print(f"命令执行成功: {command}")
        except subprocess.CalledProcessError as e:
            print(f"命令执行失败: {e}")

def run_adb_command_generator(input_file="interaction_output_response_simple.json", output_file="processed_interactions.json"):
    """封装后的主函数，可直接调用"""
    # 创建生成器实例
    generator = ADBCommandGenerator()
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"输入文件不存在: {input_file}")
    # 处理文件并执行命令，并保存到新的文件
    generator.process_json_file(input_file, output_file)