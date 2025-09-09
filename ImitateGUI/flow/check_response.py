# 版权所有 (C) 2025 bytedance technical flow 模块
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# --------------------------------------

import json


# 定义 tap 类型的检查函数。看交互坐标是否在两点定位区域内
def check_tap(response_param, answer_param):
    # 从 response_param 对应的 response 字典里获取 grounding
    grounding = response_param.get('grounding')
    grounding_range = answer_param.get('grounding_range') or answer_param.get('grounding_range_percent')

    print(f"[DEBUG] 当前检查记录的 response_param: {response_param}")
    print(f"[DEBUG] 当前检查记录的 answer_param: {answer_param}")

    if grounding and grounding_range:
        x, y = grounding
        x1, y1 = grounding_range[0], grounding_range[1]
        x2, y2 = grounding_range[2], grounding_range[3]
        print(f"正在检查 tap 类型，响应坐标: ({x}, {y})，答案坐标范围: ({x1}, {y1}) - ({x2}, {y2})")
        return x1 <= x <= x2 and y1 <= y <= y2
    else:
        print("[DEBUG] grounding 或 grounding_range 不存在，无法进行 tap 类型检查")
    return False


def check_response(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data_list = json.load(file)
    errors = []
    total_count = len(data_list)
    for data in data_list:
        record_id = data['id']
        answer = data['answer']
        response = data['response']
        print(f"正在检查记录 ID: {record_id}")
        # 检查 interaction_object
        object_valid = any(response['interaction_object'] == ans['interaction_object'] for ans in answer.values())
        print("正在检查 interaction_object...")
        if object_valid:
            print("interaction_object 检查通过")
        else:
            errors.append(f"interaction_object 错误：{record_id}")
            print(f"interaction_object 检查失败，记录 ID: {record_id}")
            continue
        # 检查 interaction_type
        type_valid = any(response['interaction_type'] == ans['interaction_type'] for ans in answer.values())
        print("正在检查 interaction_type...")
        if type_valid:
            print("interaction_type 检查通过")
        else:
            errors.append(f"interaction_type 错误：{record_id}")
            print(f"interaction_type 检查失败，记录 ID: {record_id}")
            continue
        # 检查 interaction_parameter
        print("正在检查 interaction_parameter...")
        param_valid = False
        if response['interaction_type'] == 'tap' and response['interaction_object'] == 'component_interaction':
            response_param = {
                'grounding': response.get('grounding'),
                **response['interaction_parameter']
            }
            print(f"[DEBUG] 提取到的 grounding: {response_param.get('grounding')}")
            print("检测到交互类型为 tap，开始检查坐标范围...")
            for ans in answer.values():
                if ans['interaction_type'] == 'tap':
                    if check_tap(response_param, ans['interaction_parameter']):
                        param_valid = True
                        break
        else:
            # 其他交互类型暂时默认通过，可根据需求扩展
            param_valid = True

        if not param_valid:
            if response['interaction_type'] == 'tap':
                errors.append(f"grounding 错误：{record_id}")
                print(f"grounding 检查失败，记录 ID: {record_id}")

    # 输出结果
    for error in errors:
        print(error)

    error_count = len(errors)
    accuracy = (total_count - error_count) / total_count if total_count > 0 else 0

    print(f"错误数量: {error_count}")
    print(f"准确率: {accuracy * 100:.2f}%")