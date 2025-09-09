# UI-TARS自动化流程文件夹

## 📁 文件夹说明

这个文件夹包含了基于UI-TARS模型的新版GUI自动化执行流程的所有相关文件。相比原有的复杂流程，新流程更加简洁高效，同时保留了重要的历史知识和任务分解功能。

## 📋 文件清单

### 🎯 核心文件
- **`final_uitars.py`** - 主要执行脚本，新版自动化流程的核心
- **`uitars.py`** - UI-TARS模型调用模块，负责界面理解和操作生成
- **`README_uitars.md`** - 详细的使用说明文档

### 🔧 功能模块
- **`history.py`** - 历史记录管理模块，提供历史知识获取和操作记录功能
- **`comprehension.py`** - 界面理解模块，提供图片编码等基础功能
- **`compare.py`** - 操作结果评估模块，使用AI智能判断操作成功/失败
- **`check_unloaded_content.py`** - 未加载内容检测模块，确保界面完全加载

## 🚀 快速开始

### 方法1: 使用启动脚本 (推荐)

**Linux/macOS用户**:
```bash
export ARK_API_KEY="your_ark_api_key"
./run_uitars.sh
```

**Windows/跨平台用户**:
```bash
set ARK_API_KEY=your_api_key    # Windows
python run_uitars.py
```

### 方法2: 直接运行

1. **设置环境变量**:
   ```bash
   export ARK_API_KEY="your_ark_api_key"
   ```

2. **运行主脚本**:
   ```bash
   python final_uitars.py
   ```

3. **查看详细说明**:
   ```bash
   cat README_uitars.md
   ```

## 🔄 新流程概述

```
截图 → 历史知识获取 → 子任务生成 → UI-TARS模型分析 → 坐标转换 → ADB命令生成 → 执行评估
```

## 📊 主要优势

- ✅ **更强的界面理解**: 使用UI-TARS模型替代复杂的omniparser+som+comprehension流程
- ✅ **智能上下文感知**: 集成历史知识和子任务生成，为模型提供丰富的操作背景
- ✅ **简化的处理流程**: 从8个主要步骤优化为6个步骤
- ✅ **统一的输出格式**: 所有结果保存为标准化的JSON格式
- ✅ **内置可视化**: 自动生成操作可视化图片
- ✅ **智能评估**: 使用AI自动判断操作成功/失败

## 📁 输出文件结构

每次执行后会在 `screenshots/` 目录下生成：

```
screenshots/
├── img/                          # 原始截图
│   └── screenshot_stepX_YYYYMMDD_HHMMSS.png
└── outputs/                      # 分析结果
    └── screenshot_stepX_YYYYMMDD_HHMMSS/
        ├── screenshot_stepX_YYYYMMDD_HHMMSS_analysis.json      # 完整分析结果
        ├── screenshot_stepX_YYYYMMDD_HHMMSS_annotated.png      # 可视化图片
        └── screenshot_stepX_YYYYMMDD_HHMMSS_adb_commands.json  # ADB命令
```

## 📚 历史记录

- `history.jsonl` - 详细的操作历史记录
- `step_log.jsonl` - 简要的步骤日志

## 🔗 依赖关系

- 需要连接Android设备并启用USB调试
- 需要安装 `volcengine-python-sdk[ark]`
- 需要有效的ARK API密钥

## 📝 版本信息

- **版本**: UI-TARS Enhanced Flow v1.0
- **创建日期**: 2025-07-26
- **作者**: Pengchen
- **用途**: 个人研究，禁止商业用途 