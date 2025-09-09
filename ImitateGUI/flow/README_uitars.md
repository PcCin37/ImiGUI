# UI-TARS GUI自动化脚本使用说明

## 概述

`final_uitars.py` 是使用UI-TARS模型替换原有复杂界面理解流程的新版本自动化脚本。相比原来的 `final.py`，新脚本具有更简洁的流程和更好的界面理解能力。

## 主要改进

### 1. 优化的处理流程
- **原流程**: 截图 → SOM处理 → UI分析 → icon提取 → JSON生成 → 子任务生成 → 历史知识获取 → 交互处理 → ADB命令生成
- **新流程**: 截图 → 历史知识获取 → 子任务生成 → UI-TARS模型分析 → 坐标转换 → ADB命令生成

### 2. 更好的模型能力和上下文感知
- 使用UI-TARS模型，具有更强的界面理解能力
- 保留历史知识获取功能，为模型提供操作历史和执行指导
- 集成子任务生成功能，基于全局任务和历史记录智能分解当前操作
- 直接输出结构化的操作指令
- 支持多种操作类型：click、drag、scroll、type、hotkey等

### 3. 统一的输出格式
每个步骤会生成以下文件：
- `*_analysis.json`: 完整的分析结果，包含模型响应、解析后的动作、坐标等
- `*_annotated.png`: 可视化图片，显示检测到的UI元素和操作箭头
- `*_adb_commands.json`: 生成的ADB命令列表

## 环境要求

1. **Python依赖**:
   ```bash
   pip install volcengine-python-sdk[ark]
   pip install pillow matplotlib
   ```

2. **环境变量**:
   ```bash
   export ARK_API_KEY="your_ark_api_key"
   ```

3. **ADB设备连接**:
   确保Android设备已连接并启用USB调试

## 使用方法

1. **启动脚本**:
   ```bash
   cd project/ImitateAgent/flow
   python final_uitars.py
   ```

2. **输入任务描述**:
   ```
   请输入全局任务描述（支持多行，输入单独一行 END 结束）：
   购买一件商品并添加到购物车
   END
   ```

3. **自动执行流程**:
   - 脚本会自动检测ADB设备和分辨率
   - 循环执行：截图 → 分析 → 生成操作 → 执行ADB命令 → 评估结果
   - 每步完成后询问是否继续

## 输出文件说明

### 分析结果文件 (`*_analysis.json`)
```json
{
  "step_id": 1,
  "global_task": "购买一件商品并添加到购物车",
  "current_subtask": "开始执行任务：购买一件商品并添加到购物车",
  "enhanced_task_description": "全局任务：购买一件商品并添加到购物车\n当前子任务：开始执行任务：购买一件商品并添加到购物车\n\n历史操作指导：\n这是第一次操作，请根据任务描述执行相应操作。\n\n请根据当前界面和上述上下文信息，执行最合适的操作。",
  "history_knowledge": {
    "subtask_id": null,
    "history_summary": "暂无历史记录",
    "guidance": "这是第一次操作，请根据任务描述执行相应操作。"
  },
  "screenshot_path": "screenshots/img/screenshot_step1_20250107_123456.png",
  "model_response": "Thought: 我需要点击商品图片...\nAction: click(start_box='[100, 200, 300, 400]')",
  "parsed_action": {
    "thought": "我需要点击商品图片",
    "action": "click",
    "start_box": [100, 200, 300, 400]
  },
  "absolute_coordinates": {
    "start_box": [108, 384, 324, 768],
    "direction": null
  },
  "device_resolution": {"width": 1080, "height": 1920},
  "annotated_image": "screenshots/outputs/screenshot_step1_20250107_123456/screenshot_step1_20250107_123456_annotated.png"
}
```

### ADB命令文件 (`*_adb_commands.json`)
```json
{
  "action_type": "click",
  "parsed_action": {
    "thought": "我需要点击商品图片",
    "action": "click",
    "start_box": [100, 200, 300, 400]
  },
  "coordinates": {
    "start_abs": [108, 384, 324, 768]
  },
  "commands": [
    "adb shell input tap 216 576"
  ]
}
```

## 支持的操作类型

1. **click**: 点击操作
   - 输出: `adb shell input tap x y`

2. **left_double**: 双击操作
   - 输出: 两次快速的 `adb shell input tap x y`

3. **right_single**: 右键/长按操作
   - 输出: `adb shell input swipe x y x y 1000`

4. **drag**: 拖拽操作
   - 输出: `adb shell input swipe x1 y1 x2 y2 500`

5. **scroll**: 滚动操作
   - 支持方向: up, down, left, right
   - 输出: `adb shell input swipe` (根据方向计算终点)

6. **type**: 文本输入
   - 输出: `adb shell input text 'content'`

7. **hotkey**: 按键操作
   - 支持: enter, back, home, menu, escape, delete等
   - 输出: `adb shell input keyevent KEYCODE_*`

8. **wait**: 等待操作
   - 输出: `sleep 5`

9. **finished**: 任务完成
   - 输出: `echo 'Task completed'`

## 历史知识和智能任务分解

### 历史知识获取
脚本在每步执行前会自动：
- 加载所有历史操作记录
- 构建操作摘要，包含成功/失败的操作
- 生成执行指导，避免重复失败的操作
- 过滤已成功完成的子任务，避免重复执行

### 智能子任务生成
基于全局任务和当前界面：
- 分析当前界面内容和历史操作记录
- 智能分解出当前页面需要执行的单步操作
- 考虑已完成的子任务，避免重复操作
- 为UI-TARS模型提供更精确的操作指导

### 增强的上下文传递
传递给UI-TARS模型的信息包含：
- 全局任务描述
- 当前子任务
- 历史操作指导
- 已完成的子任务列表

## 历史记录和评估

脚本会自动记录每步操作的结果：
- `history.jsonl`: 详细的操作历史记录
- `step_log.jsonl`: 每步的简要日志
- 自动评估每步操作的成功性
- 支持未加载内容的检测和处理

## 故障排除

1. **模型调用失败**: 检查ARK_API_KEY是否正确设置
2. **ADB连接失败**: 确保设备已连接且启用USB调试
3. **坐标转换错误**: 检查设备分辨率是否正确获取
4. **命令执行失败**: 检查ADB权限和设备状态

## 与原版本的对比

| 特性 | 原版本 (final.py) | 新版本 (final_uitars.py) |
|------|------------------|-------------------------|
| 界面理解 | omniparser + som + comprehension | UI-TARS模型 |
| 处理步骤 | 8个主要步骤 | 6个主要步骤 |
| 历史知识 | 复杂的JSON依赖 | 简化的历史知识获取 |
| 子任务生成 | 依赖多个文件 | 基于截图的智能生成 |
| 上下文感知 | 分离的处理流程 | 集成的上下文传递 |
| 输出文件 | 多个分散的文件 | 统一的JSON格式 |
| 可视化 | 需要额外处理 | 内置可视化功能 |
| 操作类型 | 有限的操作支持 | 丰富的操作类型 |
| 执行效率 | 较慢 | 更快 | 