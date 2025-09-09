#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安装记忆系统依赖
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def install_gui_agent_memory():
    """安装 gui-agent-memory 包"""
    print("🔧 Installing gui-agent-memory package...")
    
    # 检查 gui-agent-memory 目录是否存在
    memory_path = Path("../gui-agent-memory")
    if not memory_path.exists():
        print(f"❌ gui-agent-memory directory not found at {memory_path.absolute()}")
        return False
    
    # 安装 gui-agent-memory
    cmd = f'{sys.executable} -m pip install -e "{memory_path.absolute()}"'
    success, stdout, stderr = run_command(cmd)
    
    if success:
        print("✅ gui-agent-memory installed successfully")
        print(stdout)
        return True
    else:
        print(f"❌ Failed to install gui-agent-memory: {stderr}")
        return False

def install_dependencies():
    """安装其他依赖"""
    print("\n🔧 Installing additional dependencies...")
    
    dependencies = [
        "pydantic",
        "chromadb", 
        "jieba",
        "openai",
        "python-dotenv",
        "requests"
    ]
    
    for dep in dependencies:
        print(f"Installing {dep}...")
        cmd = f'{sys.executable} -m pip install {dep}'
        success, stdout, stderr = run_command(cmd)
        
        if success:
            print(f"✅ {dep} installed")
        else:
            print(f"❌ Failed to install {dep}: {stderr}")
            return False
    
    return True

def test_import():
    """测试导入"""
    print("\n🔍 Testing imports...")
    
    try:
        from gui_agent_memory import MemorySystem, ExperienceRecord, FactRecord, ActionStep
        print("✅ gui_agent_memory imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def main():
    print("🚀 Starting memory system installation...\n")
    
    # 安装 gui-agent-memory
    if not install_gui_agent_memory():
        print("\n❌ Installation failed at gui-agent-memory step")
        return False
    
    # 安装其他依赖
    if not install_dependencies():
        print("\n❌ Installation failed at dependencies step")
        return False
    
    # 测试导入
    if not test_import():
        print("\n❌ Installation completed but import test failed")
        return False
    
    print("\n🎉 Memory system installation completed successfully!")
    print("\n💡 Next steps:")
    print("   1. Copy .env.example to .env and configure API keys")
    print("   2. Run: python final_uitars.py")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n💡 If installation fails, try:")
        print("   1. Check Python environment and pip")
        print("   2. Ensure gui-agent-memory directory exists")
        print("   3. Run with administrator privileges if needed")
        sys.exit(1)