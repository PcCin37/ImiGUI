# UI-TARS with Memory System Integration

## 概述

本项目将 GUI Agent Memory 系统集成到 UI-TARS 自动化流程中，实现了从过往经验中学习和检索相关知识的能力。

## 功能特性

### 🧠 记忆系统功能
- **经验学习**: 自动从任务执行历史中学习操作经验
- **知识检索**: 在开始新任务时检索相关的历史经验和知识
- **步骤记录**: 详细记录每个操作步骤的成功/失败状态
- **智能提示**: 基于历史经验提供操作建议

### 📱 UI-TARS 集成
- **无缝集成**: 保持原有 UI-TARS 功能的同时添加记忆能力
- **向后兼容**: 即使记忆系统不可用也能正常运行
- **实时反馈**: 在执行过程中显示记忆系统状态

## 安装配置

### 1. 安装依赖

确保已安装 `gui-agent-memory` 包：

```bash
cd "c:\Users\Mr. Ye\Desktop\Agent\ImitateAgent copy"
pip install -e ../gui-agent-memory
pip install -r requirements.txt
```

### 2. 环境配置

复制并配置环境文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下参数：

```env
# Gitee AI Configuration (for embeddings)
GITEE_AI_API_KEY=your_gitee_ai_api_key
GITEE_AI_BASE_URL=https://ai.gitee.com/v1
GITEE_AI_EMBEDDING_MODEL=bge-large-zh-v1.5
GITEE_AI_RERANKER_MODEL=bge-reranker-v2-m3

# Experience LLM Configuration
EXPERIENCE_LLM_API_KEY=your_llm_api_key
EXPERIENCE_LLM_BASE_URL=https://api.openai.com/v1
EXPERIENCE_LLM_MODEL=gpt-4

# Memory Storage Configuration
MEMORY_STORAGE_PATH=./memory_data
EXPERIENCE_COLLECTION_NAME=gui_experiences
FACT_COLLECTION_NAME=gui_facts

# Logging Configuration
LOG_FILE_PATH=./logs/memory.log
```

## 使用方法

### 启动程序

```bash
cd "c:\Users\Mr. Ye\Desktop\Agent\ImitateAgent copy\0-ui-tars-flow"
python final_uitars.py
```

### 操作流程

1. **任务输入**: 输入全局任务描述（支持多行，以 `END` 结束）
2. **应用名称**: 输入目标应用名称（可选）
3. **经验检索**: 系统自动检索相关历史经验
4. **执行操作**: 按步骤执行UI自动化操作
5. **经验学习**: 任务结束时学习本次执行经验

### 交互命令

在执行过程中，可以使用以下命令：

- **Enter** 或 **y**: 继续下一步操作
- **n** 或 **q**: 退出程序并学习经验
- **e**: 立即评估任务并学习经验（可选择继续或退出）

## 记忆系统输出说明

### 启动时的经验检索

```
🧠 Found 2 relevant experiences:
   1. ✅ 在淘宝搜索商品并查看详情
      Keywords: 淘宝, 搜索, 商品
      Preconditions: 需要打开淘宝应用
   2. ❌ 登录淘宝账户
      Keywords: 登录, 账户, 密码

📚 Found 1 relevant facts:
   1. 淘宝搜索框通常位于页面顶部，可以通过点击进入搜索模式...
```

### 执行过程中的步骤记录

```
✅ Step 3: click on '搜索按钮'
   💭 Reasoning: 用户需要搜索商品，点击搜索按钮开始搜索
```

### 任务完成时的经验学习

```
🧠 Experience learned: exp_20241201_143022_001
📊 Task result: Success
📝 Steps executed: 5
```

## 文件结构

```
0-ui-tars-flow/
├── final_uitars.py              # 集成记忆系统的主程序
├── README_memory_integration.md # 本说明文档
├── uitars.py                   # UI-TARS 核心功能
├── comprehension.py            # 图像理解功能
├── compare.py                  # 任务评估功能
├── history.py                  # 历史记录功能
├── utils_history.py            # 历史工具函数
└── ...
```

## 故障排除

### 记忆系统不可用

如果看到以下警告：

```
Warning: Memory system not available: No module named 'gui_agent_memory'
Continuing without memory functionality...
```

**解决方案**:
1. 确保已正确安装 `gui-agent-memory` 包
2. 检查 Python 路径和虚拟环境
3. 验证依赖包是否完整安装

### 环境配置错误

如果记忆系统初始化失败：

```
❌ Failed to initialize memory system: Invalid API key
```

**解决方案**:
1. 检查 `.env` 文件是否存在且配置正确
2. 验证 API 密钥的有效性
3. 确认网络连接正常

### ChromaDB 相关错误

如果遇到 ChromaDB 相关错误：

**解决方案**:
1. 确保 `MEMORY_STORAGE_PATH` 目录有写入权限
2. 检查磁盘空间是否充足
3. 尝试删除现有的 ChromaDB 数据重新初始化

## 性能优化建议

1. **定期清理**: 定期清理过期的记忆数据以保持性能
2. **批量操作**: 对于重复性任务，可以批量学习经验
3. **网络优化**: 确保稳定的网络连接以获得最佳的 LLM 响应速度

## 更新日志

### v1.0.0 (2024-12-01)
- 初始版本
- 集成 GUI Agent Memory 系统
- 支持经验学习和知识检索
- 添加步骤记录和任务评估功能

## 技术支持

如有问题或建议，请参考：
- [GUI Agent Memory 文档](../gui-agent-memory/README.md)
- [UI-TARS 原始文档](./README_uitars.md)