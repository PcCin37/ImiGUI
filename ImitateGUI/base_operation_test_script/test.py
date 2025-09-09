import os
import torch
from PIL import Image
import base64
import io
from datetime import datetime

from util.utils import check_ocr_box, get_yolo_model, get_caption_model_processor, get_som_labeled_img

# 初始化模型，yolo模型and caption模型
yolo_model = get_yolo_model(model_path='weights/icon_detect/model.pt')
caption_model_processor = get_caption_model_processor(model_name="florence2", model_name_or_path="weights/icon_caption_florence")

DEVICE = torch.device('cpu')

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

    # 获取当前时间，用于文件命名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 创建输出文件夹
    output_folder = "testcase/outputs/3"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 保存处理后的图像
    output_image_path = os.path.join(output_folder, f"processed_image_{current_time}.png")
    image.save(output_image_path)

    # 将解析的内容保存为文本文件
    output_text_path = os.path.join(output_folder, f"parsed_content_{current_time}.txt")
    parsed_content_list = '\n'.join([f'icon {i}: ' + str(v) for i, v in enumerate(parsed_content_list)])

    with open(output_text_path, 'w') as f:
        f.write(parsed_content_list)

    print(f"Processing complete. Image saved at {output_image_path}")
    print(f"Parsed content saved at {output_text_path}")

    return output_image_path, output_text_path

image_path = "testcase/img/3.jpg"
box_threshold = 0.05
iou_threshold = 0.1
use_paddleocr = True
imgsz = 640

process_image(image_path, box_threshold, iou_threshold, use_paddleocr, imgsz)