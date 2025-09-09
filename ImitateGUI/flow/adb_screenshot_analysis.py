# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import subprocess
from datetime import datetime
from PIL import Image
import shutil
import time

# 导入 som.py 中的相关方法
from som import process_image, sort_tags, mark_on_image  # 确保 som.py 在同一目录或者设置了正确的路径

# ADB 截图函数
def capture_screenshot(adb_device_id, save_path):
    """通过 ADB 截取设备屏幕截图并保存"""
    try:
        # 使用 adb shell 命令在设备上执行截图并保存到 /sdcard/
        screenshot_cmd = f"adb -s {adb_device_id} shell screencap -p /sdcard/screenshot.png"
        subprocess.run(screenshot_cmd, shell=True, check=True)
        # time.sleep(20)  # 增加延时，确保截图文件写入完成
        # 将截图文件从设备拉取到本地保存路径
        pull_cmd = f"adb -s {adb_device_id} pull /sdcard/screenshot.png {save_path}"
        subprocess.run(pull_cmd, shell=True, check=True)

        print(f"截图已保存至: {save_path}")
    except subprocess.CalledProcessError as e:
        print(f"ADB 截图失败: {e}")
        return None
    return save_path

# 主函数
def main():
    # 设置设备 ID（可以通过 adb devices 获取设备 ID）
    adb_device_id = "e8aefcdf"  # 替换为你的设备 ID

    # 输出文件夹路径
    img_folder = "screenshots/img"
    outputs_folder = "screenshots/outputs"
    
    if not os.path.exists(img_folder):
        os.makedirs(img_folder)

    if not os.path.exists(outputs_folder):
        os.makedirs(outputs_folder)

    # 使用当前时间戳来命名文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(img_folder, f"screenshot_{timestamp}.png")

    # 1. 获取设备屏幕截图
    screenshot_path = capture_screenshot(adb_device_id, screenshot_path)
    if screenshot_path is None:
        return

    # 2. 获取文件夹路径（与图片名称相同的文件夹）
    image_name = os.path.splitext(os.path.basename(screenshot_path))[0]
    image_folder = os.path.join(outputs_folder, image_name)
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    # 3. 调用 som.py 中的 process_image 方法进行图像处理
    box_threshold = 0.05
    iou_threshold = 0.1
    use_paddleocr = True
    imgsz = 640

    # 调用 process_image 进行图像处理
    processed_image_path, processed_text_path = process_image(
        screenshot_path, 
        box_threshold=box_threshold, 
        iou_threshold=iou_threshold, 
        use_paddleocr=use_paddleocr, 
        imgsz=imgsz
    )

    # 将处理后的图像和解析文本移动到新建的文件夹中
    shutil.move(processed_image_path, os.path.join(image_folder, f"{image_name}_original_img.jpg"))
    shutil.move(processed_text_path, os.path.join(image_folder, f"{image_name}_parsed.txt"))

    print(f"处理后的图像已保存至: {os.path.join(image_folder, f'{image_name}_original_img.jpg')}")
    print(f"解析内容已保存至: {os.path.join(image_folder, f'{image_name}_parsed.txt')}")

    # 4. 执行 sort_tags 和 mark_on_image
    # 对生成的解析文件进行标签排序
    sorted_lines, sorted_tags = sort_tags(os.path.join(image_folder, f"{image_name}_parsed.txt"))

    # 保存排序后的标签
    with open(os.path.join(image_folder, f"{image_name}_tags_order.txt"), 'w', encoding='utf-8') as file:
        for line in sorted_lines:
            file.write(line + '\n')

    print(f"排序后的标签已保存至: {os.path.join(image_folder, f'{image_name}_tags_order.txt')}")

    # 对原始图像进行标注
    mark_on_image(screenshot_path, os.path.join(image_folder, f"{image_name}_original_img.jpg"), sorted_tags)

    print(f"标注后的图像已保存至: {os.path.join(image_folder, f'{image_name}_som_img.jpg')}")

if __name__ == "__main__":
    main()
