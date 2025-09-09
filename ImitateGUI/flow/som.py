# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import os
import sys
import torch
from PIL import Image
import base64
import io
from datetime import datetime
import re
import cv2
import random

# 把当前脚本目录的上一级目录加入搜索路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
sys.path.insert(0, PARENT_DIR)

from util.utils import check_ocr_box, get_yolo_model, get_caption_model_processor, get_som_labeled_img

# 初始化模型，yolo模型and caption模型
yolo_model = get_yolo_model(model_path='../weights/icon_detect/model.pt')
caption_model_processor = get_caption_model_processor(model_name="florence2", model_name_or_path="../weights/icon_caption_florence")

DEVICE = torch.device('cuda')

# 处理图像主函数
def process_image(image_path, box_threshold, iou_threshold, use_paddleocr, imgsz):
    image_input = Image.open(image_path)

    box_overlay_ratio = image_input.size[0] / 3200
    draw_bbox_config = {
        'text_scale': 0.8 * box_overlay_ratio,
        'text_thickness': max(int(2 * box_overlay_ratio), 1),
        'text_padding': max(int(3 * box_overlay_ratio), 1),
        'thickness': max(int(3 * box_overlay_ratio), 1),
    }

    # 获取OCR框的结果
    ocr_bbox_rslt, is_goal_filtered = check_ocr_box(image_input, display_img=False, output_bb_format='xyxy', goal_filtering=None, easyocr_args={'paragraph': False, 'text_threshold': 0.9}, use_paddleocr=use_paddleocr)
    text, ocr_bbox = ocr_bbox_rslt

    # 获取带标签的图像以及解析的内容
    dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
        image_input, yolo_model, BOX_TRESHOLD=box_threshold, output_coord_in_ratio=True, ocr_bbox=ocr_bbox, 
        draw_bbox_config=draw_bbox_config, caption_model_processor=caption_model_processor, 
        ocr_text=text, iou_threshold=iou_threshold, imgsz=imgsz
    )

    # 将图像保存为本地文件
    image = Image.open(io.BytesIO(base64.b64decode(dino_labled_img)))

    # 获取原始图像的文件名
    original_image_name = os.path.splitext(os.path.basename(image_path))[0]

    # 创建输出文件夹
    output_folder = "temp"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 保存处理后的图像（使用原始文件名 + "_processed"）
    output_image_path = os.path.join(output_folder, f"{original_image_name}_original_img.jpg")
    image.save(output_image_path)

    # 将解析的内容保存为文本文件（使用原始文件名 + "_parsed_content"）
    output_text_path = os.path.join(output_folder, f"{original_image_name}_parsed.txt")
    parsed_content_list = '\n'.join([f'icon {i}: ' + str(v) for i, v in enumerate(parsed_content_list)])

    with open(output_text_path, 'w') as f:
        f.write(parsed_content_list)

    return output_image_path, output_text_path


# 标签排序函数
def sort_tags(file_path):
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    tags = []
    # 解析每一行文本
    for line in lines:
        # 提取icon编号
        icon_num_match = re.search(r'icon (\d+):', line)
        if not icon_num_match:
            continue  # 跳过没有 icon 的行
        icon_num = int(icon_num_match.group(1))

        # 提取bbox信息
        bbox_match = re.search(r"'bbox': \[(.*?)\]", line)
        if not bbox_match:
            continue  # 跳过没有 bbox 的行
        bbox_str = bbox_match.group(1)
        bbox = [float(x) for x in bbox_str.split(', ')]

        # 提取其他信息
        content = None
        if "'content': '" in line:
            content = line.split("'content': '")[1].split("', 'source")[0]

        source = None
        if "'source': '" in line:
            source = line.split("'source': '")[1].split("'")[0]

        tag_type = None
        if "'type': '" in line:
            tag_type = line.split("'type': '")[1].split("', 'bbox")[0]

        interactivity_match = re.search(r"'interactivity': (.*?),", line)
        interactivity = False
        if interactivity_match:
            interactivity = bool(interactivity_match.group(1))

        # 计算中心点坐标
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2

        tags.append({
            'icon_num': icon_num,
            'bbox': bbox,
            'content': content if content else "N/A",  # 默认值为 N/A
            'source': source if source else "N/A",    # 默认值为 N/A
            'type': tag_type if tag_type else "N/A",  # 默认值为 N/A
            'interactivity': interactivity,
            'center_x': center_x,
            'center_y': center_y
        })

    # 先按y轴排序，y轴差异在0.01以内的元素被认为是同一y层级
    tags.sort(key=lambda x: x['center_y'])
    y_levels = []
    current_level = []
    for i, tag in enumerate(tags):
        if i == 0 or abs(tag['center_y'] - tags[i - 1]['center_y']) < 0.01:
            current_level.append(tag)
        else:
            y_levels.append(current_level)
            current_level = [tag]
    y_levels.append(current_level)

    # 对每个y层级按x轴排序
    sorted_tags = []
    for level in y_levels:
        level.sort(key=lambda x: x['center_x'])
        sorted_tags.extend(level)

    # 根据排序重新命名icon
    sorted_lines = []
    for i, tag in enumerate(sorted_tags):
        line = f"icon {i}: {{'type': '{tag['type']}', 'bbox': {tag['bbox']}, 'interactivity': {tag['interactivity']}, 'content': '{tag['content']}', 'source': '{tag['source']}'}}"
        sorted_lines.append(line)

    return sorted_lines, sorted_tags


# 根据生成的标签和原始图像进行标注
def mark_on_image(original_image_path, saved_path, sorted_tags):
    # 读取原始图像
    image = cv2.imread(original_image_path)
    if image is not None:
        height, width = image.shape[:2]

        # 在原图上绘制框和标签
        for i, tag in enumerate(sorted_tags):
            bbox = tag['bbox']
            # 将百分比坐标转换为像素坐标
            x1 = int(bbox[0] * width)
            y1 = int(bbox[1] * height)
            x2 = int(bbox[2] * width)
            y2 = int(bbox[3] * height)
            fontScale = 1.0
            # 生成随机颜色
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            # 绘制 1px 线框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)
            cv2.putText(image, str(i), (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, fontScale, (0, 0, 255), 2)

        # 保存标注后的图像
        output_image_path = saved_path.replace('_original_img.jpg', '_som_img.jpg')
        cv2.imwrite(output_image_path, image)
        print(f"标注后的图片已保存到 {output_image_path}")
    else:
        print(f"无法读取图片文件: {original_image_path}")


# # 调用函数并保存结果
# def main():
#     # 获取当前脚本所在目录
#     script_dir = os.path.dirname(os.path.abspath(__file__))

#     # 构建文件的绝对路径
#     image_path = os.path.join(script_dir, 'test\\1749635703778.jpg')  # 原始图像路径
#     saved_path = os.path.join(script_dir, 'test\\1749635703778_processed.jpg')

#     # 执行图像处理并生成解析内容文件
#     processed_image_path, processed_text_path = process_image(image_path, box_threshold=0.05, iou_threshold=0.1, use_paddleocr=True, imgsz=640)

#     # 对生成的文本进行标签排序
#     sorted_lines, sorted_tags = sort_tags(processed_text_path)

#     # 将排序后的结果写入新文件
#     output_file_path = os.path.join(script_dir, 'test\\1749635703778', 'tags_order_sorted.txt')
#     os.makedirs(os.path.dirname(output_file_path), exist_ok=True)  # 确保目录存在
#     with open(output_file_path, 'w', encoding='utf-8') as file:
#         for line in sorted_lines:
#             file.write(line + '\n')

#     print(f"排序后的结果已保存到 {output_file_path}")

#     # 对原始图像进行标注
#     mark_on_image(image_path, saved_path, sorted_tags)

# if __name__ == "__main__":
#     main()
    