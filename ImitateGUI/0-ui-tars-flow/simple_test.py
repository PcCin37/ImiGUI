#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("🔍 Testing Python environment...")

try:
    import sys
    print(f"✅ Python version: {sys.version}")
except Exception as e:
    print(f"❌ Python test failed: {e}")

try:
    from gui_agent_memory import MemorySystem
    print("✅ gui_agent_memory import successful")
except ImportError as e:
    print(f"❌ gui_agent_memory import failed: {e}")

try:
    import pydantic
    print("✅ pydantic available")
except ImportError:
    print("❌ pydantic not available")

try:
    import chromadb
    print("✅ chromadb available")
except ImportError:
    print("❌ chromadb not available")

print("\n📋 Test completed.")