from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import base64
import re
import json
import math
from pathlib import Path
import os
from datetime import datetime

# 通过 pip install volcengine-python-sdk[ark] 安装方舟SDK
from volcenginesdkarkruntime._exceptions import ArkAPIError
from volcenginesdkarkruntime import Ark


def parse_action_output(output_text):
    # 初始化结果字典
    result = {
        "thought": "",
        "action": "",
        "key": None,
        "content": None,
        "start_box": None,
        "end_box": None,
        "direction": None
    }
    
    # 处理空输入
    if not output_text or not output_text.strip():
        return json.dumps(result, ensure_ascii=False)
    
    output_text = output_text.strip()
    
    # 提取Thought部分（如果存在）
    thought_match = re.search(r'Thought:(.*?)(?=\nAction:|$)', output_text, re.DOTALL)
    if thought_match:
        result["thought"] = thought_match.group(1).strip()
    
    # 提取Action部分 - 支持多种格式
    action_text = ""
    
    # 格式1: "Action: click(...)"
    action_match = re.search(r'Action:\s*(.*?)(?:\n|$)', output_text, re.DOTALL)
    if action_match:
        action_text = action_match.group(1).strip()
    else:
        # 格式2: 直接是操作格式 "click(...)"
        # 检查是否包含常见的action格式
        for action_type in ['click', 'type', 'scroll', 'drag', 'hotkey', 'wait', 'finished']:
            if action_type + '(' in output_text:
                # 找到完整的操作语句
                pattern = rf'{action_type}\([^)]*\)'
                match = re.search(pattern, output_text)
                if match:
                    action_text = match.group(0)
                    break
    
    # 如果仍然没有找到action_text，但输入看起来像操作格式，尝试整体解析
    if not action_text and ('(' in output_text and ')' in output_text):
        # 可能是不完整的操作格式，尝试直接使用
        action_text = output_text
    
    # 如果没有action_text，将整个输入作为thought（如果thought为空）
    if not action_text:
        if not result["thought"] and output_text.strip():
            result["thought"] = output_text.strip()
        return json.dumps(result, ensure_ascii=False)

    # 解析action类型和参数
    action_match = re.match(r'(\w+)\((.*)\)', action_text)
    if not action_match:
        # 如果无法匹配标准格式，尝试提取操作类型
        action_type_match = re.match(r'(\w+)', action_text)
        if action_type_match:
            result["action"] = action_type_match.group(1)
        return json.dumps(result, ensure_ascii=False)
    
    action_type = action_match.group(1)
    params_text = action_match.group(2)
    result["action"] = action_type

    # 解析参数
    if params_text.strip():
        # 处理键值对参数
        # 使用更智能的分割方式，避免在引号内和方括号内分割
        params = []
        current_param = ""
        in_quotes = False
        quote_char = None
        paren_count = 0
        bracket_count = 0  # 跟踪方括号嵌套层级
        
        for char in params_text:
            if char in ['"', "'"] and (not in_quotes or char == quote_char):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            elif char == '<':
                paren_count += 1
            elif char == '>':
                paren_count -= 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
            elif char == ',' and not in_quotes and paren_count == 0 and bracket_count == 0:
                params.append(current_param.strip())
                current_param = ""
                continue
            
            current_param += char
        
        if current_param.strip():
            params.append(current_param.strip())
        
        # 解析每个参数
        for param in params:
            param = param.strip()
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 处理bbox格式 - 支持多种格式
                if 'box' in key:
                    coords = None
                    
                    # 格式1: '<bbox>813 389 938 407</bbox>'
                    bbox_match = re.search(r'<bbox>([^<]+)</bbox>', value)
                    if bbox_match:
                        numbers = re.findall(r'\d+', bbox_match.group(1))
                        if numbers:
                            coords = [int(num) for num in numbers]
                    else:
                        # 格式2: '[813, 389, 938, 407]' 或 '813 389 938 407'
                        # 先尝试提取所有数字
                        numbers = re.findall(r'\d+', value)
                        if numbers:
                            coords = [int(num) for num in numbers]
                    
                    if coords and len(coords) >= 4:
                        coords = coords[:4]  # 只取前4个数字
                        if key == 'start_box':
                            result["start_box"] = coords
                        elif key == 'end_box':
                            result["end_box"] = coords
                
                elif key == 'key':
                    result["key"] = value.strip('"\'')
                elif key == 'content':
                    # 处理转义字符
                    content = value.strip('"\'')
                    content = content.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
                    result["content"] = content
                elif key == 'direction':
                    result["direction"] = value.strip('"\'')

    return json.dumps(result, ensure_ascii=False, indent=2)

def coordinates_convert(relative_bbox, img_size):
    """
       将相对坐标[0,1000]转换为图片上的绝对像素坐标

       参数:
           relative_bbox: 相对坐标列表/元组 [x1, y1, x2, y2] (范围0-1000)
           img_size: 图片尺寸元组 (width, height)

       返回:
           绝对坐标列表 [x1, y1, x2, y2] (单位:像素)

       示例:
           >>> coordinates_convert([500, 500, 600, 600], (1000, 2000))
           [500, 1000, 600, 1200]  # 对于2000高度的图片，y坐标×2
       """
    # 参数校验
    if len(relative_bbox) != 4 or len(img_size) != 2:
        raise ValueError("输入参数格式应为: relative_bbox=[x1,y1,x2,y2], img_size=(width,height)")

    # 解包图片尺寸
    img_width, img_height = img_size

    # 计算绝对坐标
    abs_x1 = int(relative_bbox[0] * img_width / 1000)
    abs_y1 = int(relative_bbox[1] * img_height / 1000)
    abs_x2 = int(relative_bbox[2] * img_width / 1000)
    abs_y2 = int(relative_bbox[3] * img_height / 1000)

    return [abs_x1, abs_y1, abs_x2, abs_y2]

def draw_box_and_show(image, start_box=None, end_box=None, direction=None, save_path=None, show_image=True):
    """
    在图片上绘制两个边界框和指向箭头

    参数:
        image: PIL.Image对象或图片路径
        start_box: 起始框坐标 [x1,y1,x2,y2] (绝对坐标)
        end_box: 结束框坐标 [x1,y1,x2,y2] (绝对坐标)
        direction: 操作方向 ('up', 'down', 'left', 'right' 或 None)
        save_path: 保存路径，如果为None则不保存
        show_image: 是否显示图片，默认为True
    
    返回:
        绘制后的PIL.Image对象
    """
    box_color = "red"
    arrow_color = "blue"
    box_width = 10
    drag_arrow_length = 150  # drag操作箭头长度

    # 创建图片副本以避免修改原图
    image_copy = image.copy()
    draw = ImageDraw.Draw(image_copy)

    # 绘制起始框
    if start_box is not None:
        draw.rectangle(start_box, outline=box_color, width=box_width)

    # 绘制结束框
    if end_box is not None:
        draw.rectangle(end_box, outline=box_color, width=box_width)

    # 处理不同类型的操作
    if start_box is not None:
        start_center = ((start_box[0] + start_box[2]) / 2, (start_box[1] + start_box[3]) / 2)

        if end_box is not None:
            # 绘制两个框之间的连接线和箭头
            end_center = ((end_box[0] + end_box[2]) / 2, (end_box[1] + end_box[3]) / 2)
            draw.line([start_center, end_center], fill=arrow_color, width=box_width)
            draw_arrow_head(draw, start_center, end_center, arrow_color, box_width * 3)
        elif direction is not None:
            # 处理drag操作（只有start_box和direction）
            end_point = calculate_drag_endpoint(start_center, direction, drag_arrow_length)
            draw.line([start_center, end_point], fill=arrow_color, width=box_width)
            draw_arrow_head(draw, start_center, end_point, arrow_color, box_width * 3)

    # 保存图片
    if save_path:
        image_copy.save(save_path)
        print(f"图片已保存到: {save_path}")

    # 显示结果图片
    if show_image:
        plt.imshow(image_copy)
        plt.axis('on')  # 不显示坐标轴
        plt.show()
    
    return image_copy

def draw_arrow_head(draw, start, end, color, size):
    """
    绘制箭头头部
    """
    # 计算角度
    angle = math.atan2(end[1] - start[1], end[0] - start[0])

    # 计算箭头三个点的位置
    p1 = end
    p2 = (
        end[0] - size * math.cos(angle + math.pi / 6),
        end[1] - size * math.sin(angle + math.pi / 6)
    )
    p3 = (
        end[0] - size * math.cos(angle - math.pi / 6),
        end[1] - size * math.sin(angle - math.pi / 6)
    )

    # 绘制箭头
    draw.polygon([p1, p2, p3], fill=color)

def calculate_drag_endpoint(start_point, direction, length):
    """
    计算drag操作的箭头终点

    参数:
        start_point: 起点坐标 (x, y)
        direction: 方向 ('up', 'down', 'left', 'right')
        length: 箭头长度

    返回:
        终点坐标 (x, y)
    """
    x, y = start_point
    if direction == 'up':
        return (x, y - length)
    elif direction == 'down':
        return (x, y + length)
    elif direction == 'left':
        return (x - length, y)
    elif direction == 'right':
        return (x + length, y)
    else:
        return (x, y)  # 默认不移动

def image_to_base64(image_path):
    ext = Path(image_path).suffix.lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.svg': 'image/svg+xml',
    }
    with open(image_path, "rb") as image_file:
        binary_data = image_file.read()
        base64_data = base64.b64encode(binary_data).decode("utf-8")
    return f"data:{mime_types.get(ext, 'image/png')};base64,{base64_data}"

def generate_save_path(original_path, suffix="_annotated", output_dir=None, add_timestamp=False):
    """
    生成保存路径
    
    参数:
        original_path: 原始图片路径
        suffix: 文件名后缀，默认为"_annotated"
        output_dir: 输出目录，如果为None则在原图目录的同级创建annotated文件夹
        add_timestamp: 是否添加时间戳
    
    返回:
        生成的保存路径
    """
    original_path = Path(original_path)
    
    # 确定输出目录
    if output_dir is None:
        # 如果原图在子目录中（如img/），则在父目录下创建annotated文件夹
        if original_path.parent.name != ".":
            save_dir = original_path.parent.parent / "annotated"
        else:
            # 如果原图在根目录，则直接创建annotated文件夹
            save_dir = Path("annotated")
    else:
        save_dir = Path(output_dir)
    
    # 创建目录
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    filename = original_path.stem
    if add_timestamp:
        timestamp = datetime.now().strftime("_%Y%m%d_%H%M%S")
        filename = f"{filename}{suffix}{timestamp}"
    else:
        filename = f"{filename}{suffix}"
    
    save_filename = f"{filename}{original_path.suffix}"
    save_path = save_dir / save_filename
    
    return str(save_path)

def run(img_path, user_prompt, custom_prompt=""):
    ark_api_key = os.environ.get("ARK_API_KEY")
    
    # 基础系统提示词
    base_sp = "You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.\n## Output Format\n```\nThought: ...\nAction: ...\n```\n## Action Space\nclick(start_box='[x1, y1, x2, y2]')\nleft_double(start_box='[x1, y1, x2, y2]')\nright_single(start_box='[x1, y1, x2, y2]')\ndrag(start_box='[x1, y1, x2, y2]', end_box='[x3, y3, x4, y4]')\nhotkey(key='')\ntype(content='') #If you want to submit your input, use \"\\n\" at the end of `content`.\nscroll(start_box='[x1, y1, x2, y2]', direction='down or up or right or left')\nwait() #Sleep for 5s and take a screenshot to check for any changes.\nfinished(content='xxx') # Use escape characters \\\\', \\\\\", and \\\\n in content part to ensure we can parse the content in normal python string format.\n## Important Rules\n- For text input operations (like entering search keywords, usernames, passwords, etc.), you can directly use the type() action without clicking the input field first.\n- Only click input fields if they are not already focused or if the interface specifically requires activation.\n- This helps avoid unnecessary two-step operations (click + type) and improves efficiency.\n## Note\n- Use Chinese in `Thought` part.\n- Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.\n## User Instruction"
    
    # 组合自定义提示词和基础提示词
    if custom_prompt:
        sp = f"{base_sp}\n\n## Additional Instructions\n{custom_prompt}"
    else:
        sp = base_sp

    client = Ark(api_key=ark_api_key, base_url="https://ark.cn-beijing.volces.com/api/v3/")
    try:
        response = client.chat.completions.create(
            model="doubao-1-5-ui-tars-250428",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": sp
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_to_base64(img_path)
                            }
                        }
                    ]
                }

            ],
        )
        print("【结果】\n", response.choices[0].message.content)
        return response.choices[0].message.content
    except ArkAPIError as e:
        print(e)

if __name__ == "__main__":
    image_path = "img/screenshot_step11.png"
    user_prompt = "购买商品"
    model_response = run(image_path, user_prompt)
    parsed_output = json.loads(parse_action_output(model_response))
    print(parsed_output)

    image = Image.open(image_path)

    # 转换坐标
    start_abs = coordinates_convert(parsed_output["start_box"], image.size) if parsed_output["start_box"] else None
    end_abs = coordinates_convert(parsed_output["end_box"], image.size) if parsed_output["end_box"] else None
    direction = parsed_output["direction"] if parsed_output["direction"] else None

    # 生成保存路径
    save_path = generate_save_path(image_path, suffix="_annotated", add_timestamp=False)
    
    # 生成txt文件保存路径
    txt_save_path = generate_save_path(image_path, suffix="_log", add_timestamp=False)
    txt_save_path = txt_save_path.replace('.png', '.txt').replace('.jpg', '.txt').replace('.jpeg', '.txt')
    
    # 保存终端内容到txt文件
    with open(txt_save_path, 'w', encoding='utf-8') as f:
        f.write("=== GUI智能体处理日志 ===\n\n")
        f.write(f"图片路径: {image_path}\n")
        f.write(f"用户指令: {user_prompt}\n\n")
        f.write("=== 模型原始响应 ===\n")
        f.write(model_response)
        f.write("\n\n=== 解析后的结果 ===\n")
        f.write(json.dumps(parsed_output, ensure_ascii=False, indent=2))
        f.write(f"\n\n=== 坐标转换结果 ===\n")
        f.write(f"图片尺寸: {image.size}\n")
        f.write(f"起始框绝对坐标: {start_abs}\n")
        f.write(f"结束框绝对坐标: {end_abs}\n")
        f.write(f"操作方向: {direction}\n")
        f.write(f"\n处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 绘制并保存图片
    annotated_image = draw_box_and_show(image, start_abs, end_abs, direction, 
                                       save_path=save_path, show_image=True)
    
    print(f"处理完成！")
    print(f"注释后的图片已保存到: {save_path}")
    print(f"处理日志已保存到: {txt_save_path}")