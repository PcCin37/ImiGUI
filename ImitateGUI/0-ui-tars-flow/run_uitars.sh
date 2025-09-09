#!/bin/bash

# UI-TARS自动化流程启动脚本
# Author: Pengchen Chen
# Date: 2025-01-07

echo "🚀 UI-TARS GUI自动化流程启动器"
echo "================================"

# 检查ARK_API_KEY环境变量
if [ -z "$ARK_API_KEY" ]; then
    echo "❌ 错误: 请先设置ARK_API_KEY环境变量"
    echo "设置方法: export ARK_API_KEY=\"your_api_key\""
    exit 1
fi

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "❌ 错误: 未找到Python"
    exit 1
fi

# 检查依赖包
echo "🔍 检查依赖包..."
python -c "import volcenginesdkarkruntime" 2>/dev/null || {
    echo "❌ 错误: 请安装volcengine-python-sdk[ark]"
    echo "安装命令: pip install volcengine-python-sdk[ark]"
    exit 1
}

python -c "import PIL" 2>/dev/null || {
    echo "❌ 错误: 请安装Pillow"
    echo "安装命令: pip install Pillow"
    exit 1
}

# 检查ADB连接
echo "📱 检查ADB设备连接..."
if ! command -v adb &> /dev/null; then
    echo "❌ 错误: 未找到ADB命令"
    exit 1
fi

devices=$(adb devices | grep -c "device$")
if [ "$devices" -eq 0 ]; then
    echo "❌ 错误: 未检测到已连接的Android设备"
    echo "请确保:"
    echo "  1. 设备已连接到电脑"
    echo "  2. 已启用USB调试"
    echo "  3. 已授权此电脑进行调试"
    exit 1
fi

# 创建必要的目录
echo "📁 创建输出目录..."
mkdir -p screenshots/img
mkdir -p screenshots/outputs

# 启动主程序
echo "✅ 环境检查完成，启动UI-TARS自动化流程..."
echo ""
python final_uitars.py

echo ""
echo "�� UI-TARS自动化流程执行完成！" 