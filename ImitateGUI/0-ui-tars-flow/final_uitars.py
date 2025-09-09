# 版权所有 (C) 2025 bytedance technical flow 模块 - UI-TARS版本
# 本文件仅用于个人研究目的，禁止商业用途。
# Author: Pengchen Chen
# 使用UI-TARS模型替换原有的界面理解流程
# 
# 更新说明：
# - 将经验检索从全局任务级别改为每一步子任务级别
# - 新增 retrieve_step_experiences 函数用于步骤级经验检索
# - 修改 generate_subtask_simple 函数以接受和使用检索到的经验
# - 在每步操作中进行经验检索，提供更精准的操作指导
# --------------------------------------

import os
import subprocess
from datetime import datetime
from PIL import Image
import json
import time
import shutil
from pathlib import Path
import csv
import functools
from typing import Callable, Any
import threading
import signal
# 加载环境变量
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ 已加载环境变量文件: {env_path}")
    else:
        print(f"⚠️ 环境变量文件不存在: {env_path}")
except ImportError:
    print("⚠️ python-dotenv 未安装，跳过环境变量加载")

# 导入ui-tars模型相关功能（所有文件现在都在同一目录）
from uitars import run as uitars_run, parse_action_output, coordinates_convert, draw_box_and_show, generate_save_path

# 导入评估和历史记录功能
from compare import evaluate_task_success
from check_unloaded_content import check_and_handle_unloaded_content
from utils_history import load_all_entries, append_entry_to_jsonl
from history import build_action_summaries, generate_guidance_prompt
from comprehension import encode_image
from openai import OpenAI

# 导入记忆系统
try:
    from gui_agent_memory import MemorySystem, ExperienceRecord, FactRecord, ActionStep
    MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Memory system not available: {e}")
    print("Continuing without memory functionality...")
    MEMORY_AVAILABLE = False

# 控制是否启用经验学习功能（已集成反思更新机制）
ENABLE_EXPERIENCE_LEARNING = True


def api_retry(max_retries: int = 3, delay: float = 1.0):
    """
    API调用重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试间隔时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        print(f"⚠️ API调用重试 {attempt}/{max_retries}...")
                        time.sleep(delay * attempt)  # 递增延迟
                    
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # 检查是否为网络相关错误
                    if any(keyword in error_msg for keyword in [
                        'connection', 'timeout', 'network', 'ssl', 'tls',
                        'read timeout', 'connect timeout', 'connection error',
                        'connection refused', 'name resolution failed',
                        'temporary failure', 'service unavailable',
                        '连接', '超时', '网络', '网络错误', 'api', 'openai'
                    ]):
                        print(f"❌ API调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                        if attempt < max_retries:
                            continue
                    else:
                        # 非网络错误，直接抛出
                        print(f"❌ API调用出现非网络错误: {e}")
                        raise e
            
            # 所有重试都失败了
            print(f"💥 API调用连续失败 {max_retries + 1} 次，任务终止")
            raise last_exception
            
        return wrapper
    return decorator


def mark_task_failed(task_output_dir: str, reason: str = "API调用连续失败"):
    """
    标记任务失败
    
    Args:
        task_output_dir: 任务输出目录
        reason: 失败原因
    """
    try:
        # 创建失败标记文件
        fail_marker_path = os.path.join(task_output_dir, "TASK_FAILED.txt")
        with open(fail_marker_path, 'w', encoding='utf-8') as f:
            f.write(f"任务失败时间: {datetime.now().isoformat()}\n")
            f.write(f"失败原因: {reason}\n")
        
        # 更新任务信息文件
        task_info_file = os.path.join(task_output_dir, "task_info.json")
        if os.path.exists(task_info_file):
            with open(task_info_file, 'r', encoding='utf-8') as f:
                task_info = json.load(f)
            task_info["status"] = "failed"
            task_info["failed_at"] = datetime.now().isoformat()
            task_info["failure_reason"] = reason
            with open(task_info_file, 'w', encoding='utf-8') as f:
                json.dump(task_info, f, ensure_ascii=False, indent=2)
        
        print(f"🚫 任务已标记为失败: {fail_marker_path}")
        
    except Exception as e:
        print(f"⚠️ 标记任务失败时出错: {e}")


def load_tasks_from_csv(csv_file_path: str) -> list:
    """
    从CSV文件加载任务列表
    CSV格式: task_description, app_name (可选)
    """
    tasks = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row_num, row in enumerate(csv_reader, start=2):  # 从第2行开始计数（第1行是标题）
                task_description = (row.get('task_description') or '').strip()
                app_name = (row.get('app_name') or '').strip() or None
                
                if not task_description:
                    print(f"⚠️ 第{row_num}行任务描述为空，跳过")
                    continue
                
                tasks.append({
                    'task_description': task_description,
                    'app_name': app_name,
                    'row_number': row_num
                })
        
        print(f"✅ 成功从CSV文件加载 {len(tasks)} 个任务")
        return tasks
    
    except FileNotFoundError:
        print(f"❌ CSV文件不存在: {csv_file_path}")
        return []
    except Exception as e:
        print(f"❌ 读取CSV文件时出错: {e}")
        return []


def create_csv_template(csv_file_path: str):
    """
    创建CSV任务文件模板
    """
    try:
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['task_description', 'app_name'])
            writer.writerow(['打开设置页面', '设置'])
            writer.writerow(['查看网络设置', '设置'])
            writer.writerow(['返回主页', ''])
        
        print(f"✅ CSV模板文件已创建: {csv_file_path}")
        return True
    except Exception as e:
        print(f"❌ 创建CSV模板文件时出错: {e}")
        return False


def list_connected_devices() -> list:
    """获取所有已连接且状态正常的ADB设备列表
    
    Returns:
        list: 设备ID列表
    """
    devices = []
    try:
        output = subprocess.check_output(['adb', 'devices'], stderr=subprocess.DEVNULL)
        lines = output.decode().strip().splitlines()[1:]
        
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'device':
                devices.append(parts[0])
                
    except subprocess.CalledProcessError:
        pass
    return devices


def get_connected_device(target_device_id: str = None) -> str:
    """获取ADB设备ID
    
    Args:
        target_device_id: 指定的设备ID，如果为None则自动获取第一个已连接的设备
    
    Returns:
        str: 设备ID，如果未找到则返回None
    """
    try:
        output = subprocess.check_output(['adb', 'devices'], stderr=subprocess.DEVNULL)
        lines = output.decode().strip().splitlines()[1:]
        
        # 如果指定了目标设备ID，检查该设备是否连接且状态正常
        if target_device_id:
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == target_device_id and parts[1] == 'device':
                    print(f"✅ 找到指定设备: {target_device_id}")
                    return parts[0]
            print(f"❌ 指定设备 {target_device_id} 未连接或状态异常")
            return None
        
        # 如果未指定设备ID，返回第一个状态正常的设备
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'device':
                return parts[0]
                
    except subprocess.CalledProcessError:
        pass
    return None


def get_device_resolution(adb_device_id: str) -> tuple:
    """通过 adb 获取设备分辨率"""
    try:
        output = subprocess.check_output(
            ['adb', '-s', adb_device_id, 'shell', 'wm', 'size'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        # 输出示例: 'Physical size: 1080x1920'
        if ':' in output:
            size = output.split(':', 1)[1].strip()
        else:
            size = output
        width, height = size.split('x')
        return int(width), int(height)
    except Exception:
        # 默认分辨率
        return 1080, 1920


def capture_screenshot(adb_device_id: str, save_path: str) -> str:
    """通过 ADB 截取设备屏幕截图并保存"""
    try:
        subprocess.run(
            ['adb', '-s', adb_device_id, 'shell', 'screencap', '-p', '/sdcard/screenshot.png'],
            check=True
        )
        subprocess.run(
            ['adb', '-s', adb_device_id, 'pull', '/sdcard/screenshot.png', save_path],
            check=True
        )
        print(f"截图已保存至: {save_path}")
        return save_path
    except subprocess.CalledProcessError as e:
        print(f"ADB 截图失败: {e}")
        return None


def get_history_knowledge_simple(task_base_dir: str = None):
    """
    简化版的历史知识获取，不依赖output.json文件
    
    Args:
        task_base_dir: 任务基础目录，如果提供则只读取该任务的历史记录
    """
    try:
        entries = load_all_entries(task_base_dir)
        summary = build_action_summaries(entries)
        if task_base_dir:
            print(f"\n✅当前任务历史操作记录（{task_base_dir}）如下：\n")
        else:
            print("\n✅历史操作记录（全部）如下：\n")
        print(summary)
        guidance = generate_guidance_prompt(None, summary)
        # print("\n✅ 给执行器生成的提示词如下：\n")
        # print(guidance)
        return {
            "subtask_id": None,
            "history_summary": summary,
            #"guidance": guidance
        }
    except Exception as e:
        print(f"获取历史知识失败: {e}")
        return {
            "subtask_id": None,
            "history_summary": "暂无历史记录",
            "guidance": "这是第一次操作，请根据任务描述执行相应操作"
        }


def retrieve_step_experiences(memory_system, current_subtask: str, whole_task: str, step_count: int):
    """
    为当前步骤检索相关经验    
    Args:
        memory_system: 记忆系统实例
        current_subtask: 当前子任务描述        
        whole_task: 全局任务描述
        step_count: 当前步骤数    
    Returns:
        dict: 包含检索到的经验和事实的字典    """
    if not memory_system:
        print(f"\n🔍 为第{step_count}步检索相关经验: '{current_subtask}'")
        print("⚠️ 记忆系统不可用，无法检索相关经验")
        return {"experiences": [], "facts": [], "experience_guidance": ""}
    

    try:
        # 构建查询字符串，结合当前子任务和全局任务
        query = f"{current_subtask} {whole_task}"
        print(f"\n🔍 为第{step_count}步检索相关经验: '{current_subtask}'")
        
        # 使用超时机制检索相关经验
        memories = None
        timeout_seconds = 30  # 30秒超时
        
        def retrieve_with_timeout():
            nonlocal memories
            try:
                memories = memory_system.retrieve_memories(query, top_n=2)
            except Exception as e:
                print(f"⚠️ 经验检索过程中出现异常: {e}")
                memories = None
        
        # 创建并启动检索线程
        retrieve_thread = threading.Thread(target=retrieve_with_timeout)
        retrieve_thread.daemon = True
        retrieve_thread.start()
        
        # 等待检索完成或超时
        retrieve_thread.join(timeout=timeout_seconds)
        
        if retrieve_thread.is_alive():
            print(f"⏰ 经验检索超时({timeout_seconds}秒)，跳过经验检索")
            return {"experiences": [], "facts": [], "experience_guidance": ""}
        
        if memories is None:
            print("⚠️ 经验检索失败，跳过经验检索")
            return {"experiences": [], "facts": [], "experience_guidance": ""}
        

        experience_guidance = ""
        if memories.experiences:
            print(f"\n✅ 找到 {len(memories.experiences)} 条相关经验")
            experience_texts = []
            for i, exp in enumerate(memories.experiences, 1):
                success_indicator = "✅" if exp.is_successful else "❌"
                print(f"\n   === 经验 {i} ===")
                print(f"{success_indicator} 任务描述: {exp.task_description}")
                print(f"🔑 关键词: {', '.join(exp.keywords)}")
                print(f"📝 步骤总数: {len(exp.action_flow)}")
                print(f"📱 应用名称: {getattr(exp, 'app_name', '未知')}")
                print(f"🆔 来源任务ID: {getattr(exp, 'source_task_id', '未知')}")
                
                # 打印前置条件
                if hasattr(exp,'preconditions') and exp.preconditions:
                    print(f"⚙️ 前置条件: {exp.preconditions}")
                
                # 打印后置条件
                if hasattr(exp,'postconditions') and exp.postconditions:
                    print(f"✅ 后置条件: {exp.postconditions}")
                
                # 显示详细的操作步骤
                if exp.action_flow:
                    print(f"🔘 详细操作步骤:")
                    for j, step in enumerate(exp.action_flow, 1):
                        print(f"{j}. 思考: {getattr(step, 'thought', '无')}")
                        print(f"操作: {getattr(step, 'action_type', getattr(step, 'action', '未知'))}")
                        print(f"目标: {getattr(step, 'target_element_description', getattr(step, 'description', '未知'))}")
                        if hasattr(step, 'coordinates') and step.coordinates:
                            print(f"坐标: {step.coordinates}")
                        if hasattr(step, 'text') and step.text:
                            print(f"文本: {step.text}")
                        print()
                                # 构建经验指导文本
                exp_text = f"经验{i}: {exp.task_description} ({'成功' if exp.is_successful else '失败'})\n"
                if exp.action_flow:
                    exp_text += "主要步骤:\n"
                    for j, step in enumerate(exp.action_flow[:5], 1):  
                        # 显示前5步                        
                        action_type = getattr(step, 'action_type', getattr(step, 'action', '未知'))
                        description = getattr(step, 'target_element_description', getattr(step, 'description', '未知'))
                        exp_text += f"  {j}. {action_type}: {description}\n"
                if hasattr(exp, 'preconditions') and exp.preconditions:
                    exp_text += f"前置条件: {exp.preconditions}\n"
                experience_texts.append(exp_text)
            
            experience_guidance = "\n".join(experience_texts)
        else:
            print("📑 未找到相关历史经验")
        
        if memories.facts:
            print(f"\n📎 找到 {len(memories.facts)} 个相关事实")
            for i, fact in enumerate(memories.facts, 1):
                print(f"\n   === 事实 {i} ===")
                print(f"   📄 内容: {fact.content}")
                print(f"   🔑️ 关键词: {', '.join(fact.keywords)}")
                print(f"   📍 来源: {getattr(fact, 'source', '未知')}")
                print(f"   🆔 事实ID: {getattr(fact, 'fact_id', '未知')}")
                if hasattr(fact, 'confidence_score'):
                    print(f"   📊 置信度: {fact.confidence_score}")
                if hasattr(fact, 'created_at'):
                    print(f"   📅 创建时间: {fact.created_at}")
        else:
            print("\n📎 未找到相关事实")
        
        return {
            "experiences": memories.experiences if memories.experiences else [],
            "facts": memories.facts if memories.facts else [],
            "experience_guidance": experience_guidance
        }
        
    except Exception as e:
        print(f"⚠️ 检索步骤经验失败: {e}")
        return {"experiences": [], "facts": [], "experience_guidance": ""}


@api_retry(max_retries=3, delay=1.0)
def _call_subtask_generation_api(client, system_prompt: str, prompt: str, image_base64: str):
    """
    调用子任务生成API的内部函数
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }
        ],
        max_tokens=2048
    )
    return response.choices[0].message.content.strip()


def generate_subtask_simple(screenshot_path: str, whole_task: str, history_knowledge: dict, step_experiences: dict = None):
    """
    使用大模型API生成子任务，基于截图、全局任务、历史记录和步骤经验

    Args:
        screenshot_path: 截图路径
        whole_task: 全局任务描述
        history_knowledge: 历史知识字典
        step_experiences: 当前步骤的经验检索结果
    """
    try:
        # 读取历史记录，过滤已成功的子任务
        history_entries = load_all_entries()
        finished_subtasks = set()
        for entry in history_entries:
            if entry.get("subtask_id") and entry.get("success") is True:
                finished_subtasks.add(entry["subtask_id"])

        # 编码图片
        image_base64 = encode_image(screenshot_path)
        
        # 历史摘要内容
        history_summary = history_knowledge.get("history_summary", "暂无历史记录")
        
        # 经验指导内容
        experience_guidance = ""
        if step_experiences and step_experiences.get("experience_guidance"):
            experience_guidance = f"""

3. 相关经验参考：
{step_experiences['experience_guidance']}

【经验指导】：
- 参考上述相关经验中的成功案例，避免失败案例中的错误
- 如果有相似的操作步骤，可以借鉴其操作方式
- 注意前置条件是否满足"""

        # 构造prompt
        prompt = f"""
你是一个UI任务分解专家。全局任务是：{whole_task}

请根据以下内容，推理并生成本页面的【单步交互操作】（task）：
1. 当前界面截图（已上传）
2. 历史操作记录摘要：
{history_summary}{experience_guidance}

【要求】：
- task应该是这个页面需要执行的操作，具体如何操作如"点击xx按钮"会在后续步骤中输出，无需在当前task生成中输出。
- 不要输出"查看价格""确认信息""评估商品质量"等非交互行为。
- 每个 task 只描述一步当前需要进行的操作，不要合并多步操作，不要输出复合操作。
- 只输出 task 内容，不要输出多余内容。
- 不要输出"查看价格""确认信息""评估商品质量"等非交互行为。

【直接执行特殊规则】：
- 如果全局任务包含"点击底部左侧【后台进程】键查看进程"等系统功能操作，直接输出该任务，无需优化或修改
- 对于包含【后台进程】、【设置】、【系统】等系统功能的任务，保持原始描述不变
- 明确指定位置的系统操作任务应直接按原始描述执行

【重要】以下子任务已被成功执行过：{list(finished_subtasks)}。

【多商品购物车特别提醒】：
- 如果全局任务要求"将前三个商品依次加入购物车"，必须严格按照：点击商品→加入购物车→返回列表→点击下一个商品的循环流程
- 绝对禁止在同一商品详情页重复点击"加入购物车"按钮
- 每次成功加入购物车后，下一步必须是返回到商品列表页面
- 只有返回到商品列表后，才能点击下一个商品

【全局任务完整性要求】：
- 必须严格按照全局任务的要求执行，不能跳过任何必要的操作步骤
- 仔细分析全局任务中包含的所有操作要求，确保每个步骤都会被执行
- 如果全局任务包含多个操作（如"点击A，然后点击B，最后点击C"），必须确保所有操作都会被依次执行
- 当前界面如果可以执行全局任务中的下一个必要步骤，优先执行该步骤
- 绝对不允许因为"选择最关键的一步"而跳过全局任务中明确要求的操作

【具体元素识别要求】：
- 当任务涉及点击特定位置的元素时（如"点击第二个商品"、"选择第三个选项"等），必须仔细观察截图中的具体内容
- 子任务描述中应包含具体的元素信息，而不是使用序号描述
- 【重要示例】：
  * 错误："点击第二个商品卡片" → 正确："点击OPPO Reno5商品卡片"
  * 错误："选择第三个选项" → 正确："选择蓝色选项"
  * 错误："点击第一个按钮" → 正确："点击立即购买按钮"
  * 错误："滑动到第五个视频" → 正确："滑动到美食制作教程视频"
- 优先级顺序：具体名称 > 具体描述 > 位置描述
- 如果能识别出具体的商品名称、品牌、颜色、文字内容、图标名称等信息，优先使用这些具体信息
- 只有在完全无法识别具体内容时，才使用位置描述（如"第二个"、"右侧的"等）
- 【特别注意】：对于商品、视频、文章等内容卡片，务必尝试识别其标题、名称或主要特征

【详细信息场景特殊要求】：
- 在涉及具体选择的场景中，子任务必须包含详细的具体信息，包括但不限于：

【购买商品场景】：
  * 商品名称：如"点击iPhone 15 Pro商品卡片"而不是"点击第一个商品"
  * 商品规格：如"选择256GB存储容量"而不是"选择第二个规格"
  * 商品颜色：如"选择深空黑色"而不是"选择第三个颜色"
  * 价格信息：如"点击¥8999立即购买按钮"而不是"点击购买按钮"

【套餐服务场景】：
  * 套餐名称：如"选择月享套餐19元"而不是"选择第一个套餐"
  * 套餐内容：如"选择包含100分钟通话+10GB流量套餐"而不是"选择套餐"
  * 套餐价格：如"点击¥39/月套餐"而不是"点击套餐选项"

【预订服务场景】：
  * 时间信息：如"选择2024年1月15日下午2点"而不是"选择时间"
  * 服务类型：如"预订豪华双人间"而不是"选择房间类型"
  * 价格信息：如"确认¥588/晚的预订"而不是"确认预订"

【注册登录场景】：
  * 账户类型：如"选择个人账户注册"而不是"选择账户类型"
  * 服务等级：如"选择VIP会员套餐"而不是"选择会员类型"
  * 验证方式：如"选择手机号验证"而不是"选择验证方式"

【配置设置场景】：
  * 具体参数：如"设置分辨率为1920x1080"而不是"设置分辨率"
  * 功能选项：如"开启夜间模式"而不是"开启功能"
  * 数值设置：如"设置音量为80%"而不是"调整音量"

- 【通用示例对比】：
  * 错误："选择商品规格" → 正确："选择华为Mate60 Pro 12GB+256GB版本"
  * 错误："预订服务" → 正确："预订1月20日上午10点的理发服务"
  * 错误："选择支付方式" → 正确："选择微信支付方式"
  * 错误："确认订单" → 正确："确认购买iPhone 15 Pro Max 1TB天然钛金色订单"
  * 错误："注册账户" → 正确："注册企业版账户"
  * 错误："设置参数" → 正确："设置自动备份为每日凌晨2点"

【输入文本操作规范】：
- 输入文本操作必须分为两步：
  1. 第一步：点击文本输入框（如"点击搜索框"、"点击用户名输入框"等）
  2. 第二步：输入文本内容（如"输入搜索关键词"、"输入用户名"等）
- 绝对不允许将"点击输入框"和"输入文本"合并为一步操作
- 【核心原则】点击输入框后，下一步子任务必须是输入对应的文本内容，不能有任何其他操作
- 【严格执行顺序】当有多个文本需要输入时，必须严格按照以下顺序执行：
  点击第一个输入框 → 输入对应内容 → 点击第二个输入框 → 输入对应内容
- 【绝对禁止】连续点击多个输入框后再输入内容的错误操作顺序
- 【错误示例】：点击最低价输入框 → 点击最高价输入框 → 输入100 → 输入3000
- 【正确示例】：点击最低价输入框 → 输入100 → 点击最高价输入框 → 输入3000
- 【特别注意】在商城价格筛选、表单填写等多输入框场景中，严格遵循"一点一输入"原则
- 【验证规则】如果当前步骤是点击输入框，那么下一步必须是输入文本，不能是其他任何操作
- 【容错处理】当输入框被激活但输入文本失败时，优先考虑重新输入相同内容，而不是跳转到其他操作
【搜索操作规范】：
- 搜索操作必须分为两步：
  1. 第一步：点击搜索框
  2. 第二步：输入搜索内容

【其他操作规范】：
- 优先执行全局任务中明确要求的下一个操作步骤
- 如果当前界面可以执行全局任务中的多个步骤，选择按逻辑顺序应该执行的下一步
- 如果上一步操作失败（如被操作进入了错误页面），你可以考虑返回上一界面，但也可以根据实际情况判断是否需要继续当前任务
- 确保不遗漏全局任务中的任何必要操作

【最终检查要求】：
- 在输出子任务前，必须检查是否违反了"一点一输入"原则
- 如果当前子任务是点击输入框，确认下一个子任务必须是输入对应内容
- 绝对不允许出现"点击输入框A → 点击输入框B → 输入内容"的错误序列
- 商城价格筛选等多输入场景是重点检查对象
- 如果上一步输入操作失败，优先考虑重新输入而不是执行其他操作
- 确保容错处理遵循正确的重试优先级顺序

请直接输出最终的 task。"""

                # 调用大模型API（从环境变量读取配置）
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # 增强系统提示词，强调具体元素识别的重要性
        system_prompt = """
你是一个专业的UI任务分解专家，擅长识别界面中的具体元素并生成精确的子任务描述。

【核心原则】：
1. 绝对不能跳过全局任务中明确要求的任何操作步骤
2. 必须严格按照全局任务的逻辑顺序执行每个必要步骤
3. 当前界面如果可以执行全局任务中的下一个必要步骤，必须优先执行该步骤

【直接执行规则】：
4. 对于以下类型的任务，无需优化，直接按原始描述执行：
   - 包含"【后台进程】"、"【设置】"、"【系统】"等系统功能的任务
   - 明确指定位置的系统操作任务（如"点击底部左侧【后台进程】键"）
   - 涉及系统级功能访问的任务
   - 当任务描述已经足够具体和明确时，直接使用原始任务描述
5. 【特别注意】：如果全局任务是"点击底部左侧【后台进程】键查看进程"，直接输出该任务，不进行任何修改或优化

【重要指导】：
6. 当任务涉及点击或操作特定元素时，你必须仔细观察图像中的具体内容
7. 始终优先使用具体的元素名称、标题或描述，而不是位置序号
8. 例如：使用"点击OPPO Reno5商品卡片"而不是"点击第二个商品卡片"
9. 对于商品、视频、文章等内容，务必识别并包含其具体名称或主要特征
10. 只有在完全无法识别具体内容时，才使用位置描述（如"第二个"、"右侧的"等）

【详细信息场景专项要求】：
9. 在涉及具体选择的场景中，必须识别并包含详细的具体信息：
   - 购买商品：商品名称、品牌、型号、规格、颜色、价格等
   - 套餐服务：套餐名称、价格、包含内容（流量、通话时长等）
   - 预订服务：时间、服务类型、价格、规格等
   - 注册登录：账户类型、服务等级、验证方式等
   - 配置设置：具体参数、功能选项、数值设置等
10. 例如："选择iPhone 15 Pro 256GB 深空黑色"而不是"选择商品规格"
11. 例如："预订1月20日下午3点的按摩服务"而不是"预订服务"
12. 例如："设置分辨率为1920x1080"而不是"设置分辨率"
13. 所有涉及具体选择的流程中，每一步都要包含具体的详细信息

【多商品购物车操作专项指导】：
14. 当全局任务涉及"将前三个商品依次加入购物车"等多商品操作时，必须严格遵循循环流程
15. 每个商品的完整操作流程：点击商品卡片 → 加入购物车 → 返回商品列表
16. 绝对禁止在同一商品详情页面重复点击"加入购物车"按钮
17. 每次加入购物车成功后，必须立即返回到商品列表页面才能继续下一个商品
18. 严格按照商品顺序执行，确保每个商品都经历完整的操作流程

【购物车操作强制返回规则】：
19. 【最高优先级】当检测到商品已成功加入购物车时，下一步任务必须是"返回商品列表"或"返回上一页"
20. 【状态识别】如果当前页面显示"已加入购物车"、"添加成功"等提示，立即生成返回任务
21. 【循环保证】只有成功返回到商品列表页面后，才能生成点击下一个商品的任务
22. 【错误纠正】如果发现连续生成同一商品的加入购物车任务，强制插入返回商品列表任务
23. 【页面判断】通过页面内容判断当前状态：商品详情页→返回列表，商品列表页→点击下一商品

【全局任务执行保证】：
24. 仔细分析全局任务，识别其中包含的所有必要操作步骤
25. 确保每个步骤都会被依次执行，不能因为界面复杂或其他原因而跳过
26. 如果全局任务是复合任务（包含多个操作），必须确保所有操作都会被执行
27. 优先执行全局任务中明确要求的下一个步骤，而不是选择"看起来重要"的操作

【输入操作严格规范】：
28. 【绝对禁止】连续点击多个输入框的操作序列
29. 【强制要求】每次点击输入框后，下一个子任务必须是输入对应的文本内容
30. 【操作模式】严格遵循"点击输入框 → 立即输入内容"的配对模式
31. 【多输入场景】多个输入框时必须按"点击A → 输入A → 点击B → 输入B"的顺序
32. 【错误检测】如果发现连续的点击输入框操作，立即纠正为正确的交替模式
33. 【容错原则】当输入框激活但输入失败时，优先重新输入而非执行其他操作
34. 【重试策略】输入失败的处理优先级：重新输入 → 重新激活输入框 → 状态检查 → 其他操作

【多商品购物车操作规范】：
35. 【核心原则】当全局任务要求"将前三个商品依次加入购物车"或类似多商品操作时，必须严格按照以下流程执行：
36. 【标准流程】点击第N个商品 → 加入购物车 → 确认加入成功 → 返回商品列表 → 点击第N+1个商品
37. 【强制返回】每次成功将商品加入购物车后，下一步必须是返回到商品列表页面，绝对不能重复点击同一商品的加入购物车按钮
38. 【返回确认】返回商品列表后，必须确认能看到商品列表界面，然后才能点击下一个商品
39. 【循环控制】严格按照商品顺序执行：第一个商品完整流程 → 第二个商品完整流程 → 第三个商品完整流程
40. 【错误纠正】如果发现连续多次点击同一商品的加入购物车按钮，立即执行返回操作回到商品列表
41. 【状态检查】在点击下一个商品前，必须确认当前处于商品列表页面，而不是商品详情页面
42. 【完整性保证】确保每个商品都经历完整的"点击商品→加入购物车→返回列表"流程，不能跳过任何步骤
"""
        
        # 使用带重试机制的API调用
        subtask = _call_subtask_generation_api(client, system_prompt, prompt, image_base64)
        
        print(f"生成的子任务: {subtask}")
        return subtask
        
    except Exception as e:
        print(f"生成子任务失败: {e}")
        # 降级处理：返回基于全局任务的默认子任务
        if not finished_subtasks:
            subtask = f"开始执行任务：{whole_task}"
        else:
            subtask = f"继续执行任务：{whole_task}"
        return subtask


@api_retry(max_retries=3, delay=1.0)
def _learn_from_task_with_retry(memory_system, raw_history: list, task_description: str,
                               is_successful: bool, source_task_id: str, app_name: str = "unknown_app"):
    """
    带重试机制的经验学习内部函数
    
    Args:
        memory_system: 记忆系统实例
        raw_history: 原始任务历史记录
        task_description: 任务描述
        is_successful: 任务是否成功
        source_task_id: 源任务ID
        app_name: 应用名称
        
    Returns:
        str: 经验学习结果ID
    """
    return memory_system.learn_from_task(
        raw_history=raw_history,
        task_description=task_description,
        is_successful=is_successful,
        source_task_id=source_task_id,
        app_name=app_name
    )


def learn_from_task_with_reflection(memory_system, raw_history: list, task_description: str, 
                                   is_successful: bool, source_task_id: str, app_name: str = "unknown_app"):
    """
    带有反思更新功能的经验学习函数
    
    该函数集成了记忆系统的反思更新机制，能够：
    1. 检索相似的历史经验
    2. 使用LLM判断是否需要更新现有经验
    3. 根据判断结果进行添加新经验或更新现有经验
    4. 提供详细的学习过程日志
    
    Args:
        memory_system: 记忆系统实例
        raw_history: 原始任务历史记录
        task_description: 任务描述
        is_successful: 任务是否成功
        source_task_id: 源任务ID
        app_name: 应用名称
        
    Returns:
        str: 学习结果描述
    """
    if not memory_system:
        return "memory_system_unavailable"
        
    try:
        print(f"\n🧠 开始反思学习过程...")
        print(f"📝 任务描述: {task_description}")
        print(f"📊 任务结果: {'成功' if is_successful else '失败'}")
        print(f"🔍 应用名称: {app_name}")
        
        # 1. 首先检索相似的历史经验
        print(f"\n🔍 检索相似历史经验...")
        try:
            # 使用记忆系统的检索功能查找相似经验
            retrieval_result = memory_system.retrieve_memories(
                query=task_description,
                top_n=3  # 获取最相似的3个经验
            )
            similar_experiences = retrieval_result.experiences if retrieval_result.experiences else []
            
            if similar_experiences:
                print(f"✅ 找到 {len(similar_experiences)} 个相似经验")
                for i, exp in enumerate(similar_experiences, 1):
                    task_desc = getattr(exp, 'task_description', 'N/A')
                    print(f"  {i}. {task_desc[:50]}... (任务ID: {getattr(exp, 'source_task_id', 'N/A')})")
            else:
                print(f"📝 未找到相似经验，将添加新经验")
                
        except Exception as e:
            print(f"⚠️ 检索相似经验时出错: {e}")
            similar_experiences = []
        
        # 2. 使用记忆系统的learn_from_task方法（内置反思更新逻辑）
        print(f"\n🎯 执行经验学习...")
        experience_id = _learn_from_task_with_retry(
            memory_system=memory_system,
            raw_history=raw_history,
            task_description=task_description,
            is_successful=is_successful,
            source_task_id=source_task_id,
            app_name=app_name
        )
        
        # 3. 分析学习结果
        if "already exists" in experience_id:
            print(f"🔄 经验已存在，跳过重复学习")
            learning_type = "duplicate_skipped"
        elif "Successfully learned" in experience_id:
            print(f"✅ 成功学习新经验")
            learning_type = "new_experience_added"
        else:
            print(f"📝 经验学习完成")
            learning_type = "experience_processed"
            
        # 4. 提供反思总结
        print(f"\n🎯 反思学习总结:")
        print(f"  📋 学习类型: {learning_type}")
        print(f"  🆔 经验ID: {experience_id}")
        print(f"  📊 任务步骤数: {len(raw_history)}")
        print(f"  🎯 成功状态: {'✅ 成功' if is_successful else '❌ 失败'}")
        
        # 5. 如果是失败的任务，提供额外的反思信息
        if not is_successful:
            print(f"\n🔍 失败任务反思:")
            print(f"  - 该失败经验将帮助避免未来的类似错误")
            print(f"  - 建议分析失败原因并在后续任务中改进")
            
        return experience_id
        
    except Exception as e:
        error_msg = f"反思学习过程中出错: {e}"
        print(f"❌ {error_msg}")
        return f"reflection_learning_failed: {error_msg}"


def process_screenshot_with_uitars(screenshot_path: str, task_description: str, step_count: int, width: int, height: int, custom_prompt: str = "", memory_system=None, task_base_dir: str = None, adb_device_id: str = None, use_experience_optimization: bool = True):
    """
    使用UI-TARS模型处理截图并生成操作
    
    Args:
        screenshot_path: 截图路径
        task_description: 任务描述
        step_count: 当前步骤数
        width: 设备宽度
        height: 设备高度
        custom_prompt: 自定义提示词
        memory_system: 记忆系统实例
        task_base_dir: 任务基础目录
        adb_device_id: ADB设备ID
        use_experience_optimization: 是否启用经验优化，默认True
    
    Returns:
        dict: 包含模型输出和处理结果的字典
    """
    print(f"使用UI-TARS模型分析截图: {screenshot_path}")
    print(f"全局任务描述: {task_description}")
    
    # 第一步：获取历史知识
    print("获取历史摘要和建议信息..")
    history_knowledge = get_history_knowledge_simple(task_base_dir)
    
    # 第二步：生成初步子任务
    print("生成初步子任务..")
    preliminary_subtask = generate_subtask_simple(screenshot_path, task_description, history_knowledge)
    print(f"生成的子任务: {preliminary_subtask}")
    
    # 验证初步子任务是否生成成功
    if not preliminary_subtask or preliminary_subtask.strip() == "":
        print("警告：初步子任务生成失败，使用默认任务描述")
        preliminary_subtask = f"执行任务：{task_description}"
    
    # 根据用户选择决定是否进行经验优化
    if use_experience_optimization:
        # 第三步：检索相关经验
        step_experiences = retrieve_step_experiences(memory_system, preliminary_subtask, task_description, step_count)
        
        # 第四步：结合经验重新生成优化的子任务
        print("结合检索到的经验重新生成优化子任务...")
        current_subtask = generate_subtask_simple(screenshot_path, task_description, history_knowledge, step_experiences)
        print(f"优化后的子任务: {current_subtask}")
        
        # 验证优化子任务是否生成成功
        if not current_subtask or current_subtask.strip() == "":
            print("警告：优化子任务生成失败，使用初步子任务")
            current_subtask = preliminary_subtask
    else:
        # 不使用经验优化，直接使用初步子任务
        print("🚫 经验优化已禁用，直接使用初步子任务规划")
        current_subtask = preliminary_subtask
        step_experiences = {"experiences": [], "facts": [], "experience_guidance": ""}
    
    # 第五步：使用优化后的子任务作为UI-TARS模型的输入
    print(f"当前子任务: {current_subtask}")
    
    # 调用UI-TARS模型，传入子任务和自定义提示词
    try:
        model_response = uitars_run(screenshot_path, current_subtask, custom_prompt)
        print("模型原始响应:")
        print(model_response)
        
        # 解析模型输出
        parsed_output = json.loads(parse_action_output(model_response))
        print("解析后的输出:")
        print(json.dumps(parsed_output, ensure_ascii=False, indent=2))
        
        # 加载图片获取尺寸
        image = Image.open(screenshot_path)
        img_width, img_height = image.size
        
        # 转换坐标（如果存在）
        start_abs = None
        end_abs = None
        if parsed_output.get("start_box"):
            start_abs = coordinates_convert(parsed_output["start_box"], image.size)
            print(f"起始框绝对坐标 {start_abs}")
        
        if parsed_output.get("end_box"):
            end_abs = coordinates_convert(parsed_output["end_box"], image.size)
            print(f"结束框绝对坐标 {end_abs}")
        
                # 创建输出文件夹（按照test_task结构）
        image_name = os.path.splitext(os.path.basename(screenshot_path))[0]
        
        # 获取当前任务的基础目录（从截图路径推断）
        screenshot_dir = os.path.dirname(screenshot_path)
        if screenshot_dir.endswith('/img') or screenshot_dir.endswith('\\img'):
            # 如果截图在img文件夹中，则outputs文件夹应该在同级
            base_dir = os.path.dirname(screenshot_dir)
            outputs_folder = os.path.join(base_dir, "outputs")
        else:
            # 否则在当前目录创建outputs文件夹
            outputs_folder = "screenshots/outputs"
        
        image_folder = os.path.join(outputs_folder, image_name)
        os.makedirs(image_folder, exist_ok=True)
        
        # 保存可视化结果
        annotated_save_path = os.path.join(image_folder, f"{image_name}_annotated.png")
        draw_box_and_show(
            image, 
            start_abs, 
            end_abs, 
            parsed_output.get("direction"),
            save_path=annotated_save_path,
            show_image=False
        )
        
        # 序列化步骤经验数据
        serializable_step_experiences = {
            "experiences": [],
            "facts": [],
            "experience_guidance": step_experiences.get("experience_guidance", "")
        }
        
        # 将ExperienceRecord对象转换为可序列化的字典
        if step_experiences.get("experiences"):
            for exp in step_experiences["experiences"]:
                exp_dict = {
                    "task_description": exp.task_description,
                    "keywords": exp.keywords,
                    "action_flow": [{
                        "thought": getattr(step, 'thought', ''),
                        "action": getattr(step, 'action_type', getattr(step, 'action', '')),
                        "target_element_description": getattr(step, 'target_element_description', getattr(step, 'description', '')),
                        "coordinates": getattr(step, 'coordinates', None),
                        "text": getattr(step, 'text', None)
                    } for step in exp.action_flow],
                    "preconditions": exp.preconditions,
                    "is_successful": exp.is_successful,
                    "usage_count": exp.usage_count,
                    "last_used_at": exp.last_used_at.isoformat() if hasattr(exp.last_used_at, 'isoformat') else str(exp.last_used_at),
                    "source_task_id": exp.source_task_id
                }
                serializable_step_experiences["experiences"].append(exp_dict)
        
        # 序列化事实记录
        if step_experiences.get("facts"):
            for fact in step_experiences["facts"]:
                fact_dict = {
                    "content": fact.content,
                    "keywords": fact.keywords,
                    "source": fact.source,
                    "usage_count": fact.usage_count,
                    "last_used_at": fact.last_used_at.isoformat() if hasattr(fact.last_used_at, 'isoformat') else str(fact.last_used_at)
                }
                serializable_step_experiences["facts"].append(fact_dict)
        
        # 构建分析结果
        analysis_result = {
            "step_id": step_count,
            "global_task": task_description,
            "current_subtask": current_subtask,
            "history_knowledge": history_knowledge,
            "step_experiences": serializable_step_experiences,  # 使用序列化后的版本
            "screenshot_path": screenshot_path,
            "model_response": model_response,
            "parsed_action": parsed_output,
            "absolute_coordinates": {
                "start_box": start_abs,
                "end_box": end_abs,
                "direction": parsed_output.get("direction")
            },
            "device_resolution": {"width": width, "height": height},
            "image_size": {"width": img_width, "height": img_height},
            "annotated_image": annotated_save_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        analysis_json_path = os.path.join(image_folder, f"{image_name}_analysis.json")
        with open(analysis_json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        print(f"分析结果已保存到: {analysis_json_path}")
        print(f"可视化图片已保存到 {annotated_save_path}")
        
        # 生成ADB命令
        adb_commands = generate_adb_commands_from_action(parsed_output, start_abs, end_abs, adb_device_id)
        
                # 保存ADB命令
        adb_commands_path = os.path.join(image_folder, f"{image_name}_adb_commands.json")
        with open(adb_commands_path, 'w', encoding='utf-8') as f:
            json.dump(adb_commands, f, ensure_ascii=False, indent=2)
        
        print(f"ADB命令已保存到: {adb_commands_path}")
        
        return {
            "analysis_result": analysis_result,
            "analysis_json_path": analysis_json_path,
            "adb_commands": adb_commands,
            "adb_commands_path": adb_commands_path,
            "image_folder": image_folder,
            "annotated_screenshot_path": annotated_save_path
        }
        
    except Exception as e:
        print(f"处理截图失败: {e}")
        return None


def generate_adb_commands_from_action(parsed_action: dict, start_abs: list, end_abs: list, adb_device_id: str) -> dict:
    """
    根据UI-TARS模型的输出生成ADB命令
    
    Args:
        parsed_action: 解析后的动作字典
        start_abs: 起始坐标 [x1, y1, x2, y2]
        end_abs: 结束坐标 [x1, y1, x2, y2]
        adb_device_id: ADB设备ID
    
    Returns:
        dict: 包含ADB命令的字典
    """
    action_type = parsed_action.get("action", "")
    commands = []
    
    if action_type == "click":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            commands.append(f"adb -s {adb_device_id} shell input tap {center_x} {center_y}")
    
    elif action_type == "left_double":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            commands.append(f"adb -s {adb_device_id} shell input tap {center_x} {center_y}")
            commands.append("sleep 0.1")
            commands.append(f"adb -s {adb_device_id} shell input tap {center_x} {center_y}")
    
    elif action_type == "right_single":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            # 长按模拟右键
            commands.append(f"adb -s {adb_device_id} shell input swipe {center_x} {center_y} {center_x} {center_y} 1000")
    
    elif action_type == "drag":
        if start_abs and end_abs:
            start_x = (start_abs[0] + start_abs[2]) // 2
            start_y = (start_abs[1] + start_abs[3]) // 2
            end_x = (end_abs[0] + end_abs[2]) // 2
            end_y = (end_abs[1] + end_abs[3]) // 2
            commands.append(f"adb -s {adb_device_id} shell input swipe {start_x} {start_y} {end_x} {end_y} 500")
    
    elif action_type == "scroll":
        if start_abs:
            center_x = (start_abs[0] + start_abs[2]) // 2
            center_y = (start_abs[1] + start_abs[3]) // 2
            direction = parsed_action.get("direction", "down")
            
            if direction == "down":
                commands.append(f"adb -s {adb_device_id} shell input swipe {center_x} {center_y} {center_x} {center_y - 500} 300")
            elif direction == "up":
                commands.append(f"adb -s {adb_device_id} shell input swipe {center_x} {center_y} {center_x} {center_y + 500} 300")
            elif direction == "left":
                commands.append(f"adb -s {adb_device_id} shell input swipe {center_x} {center_y} {center_x + 500} {center_y} 300")
            elif direction == "right":
                commands.append(f"adb -s {adb_device_id} shell input swipe {center_x} {center_y} {center_x - 500} {center_y} 300")
    
    elif action_type == "type":
        content = parsed_action.get("content", "")
        if content:
            # 使用 am broadcast 方式输入文本，避免中文字符输入问题
            commands.append(f'adb -s {adb_device_id} shell am broadcast -a ADB_INPUT_TEXT --es msg "{content}"')
    
    elif action_type == "hotkey":
        key = parsed_action.get("key", "")
        key_mapping = {
            "enter": "KEYCODE_ENTER",
            "back": "KEYCODE_BACK",
            "home": "KEYCODE_HOME",
            "menu": "KEYCODE_MENU",
            "escape": "KEYCODE_ESCAPE",
            "delete": "KEYCODE_DEL",
            "backspace": "KEYCODE_DEL"
        }
        if key.lower() in key_mapping:
            commands.append(f"adb -s {adb_device_id} shell input keyevent {key_mapping[key.lower()]}")
    
    elif action_type == "wait":
        commands.append("sleep 5")
    
    elif action_type == "finished":
        commands.append("echo 'Task completed'")
    
    return {
        "action_type": action_type,
        "parsed_action": parsed_action,
        "coordinates": {
            "start_abs": start_abs,
            "end_abs": end_abs
        },
        "commands": commands,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def execute_adb_commands(adb_commands: dict, adb_device_id: str) -> bool:
    """
    执行ADB命令
    
    Args:
        adb_commands: ADB命令字典
        adb_device_id: ADB设备ID
    
    Returns:
        bool: 执行是否成功
    """
    commands = adb_commands.get("commands", [])
    if not commands:
        print("没有需要执行的ADB命令")
        return True
    
    print("开始执行ADB命令:")
    for i, cmd in enumerate(commands):
        print(f"  {i+1}. {cmd}")
        
        if cmd.startswith("sleep"):
            # 处理sleep命令
            sleep_time = float(cmd.split()[1])
            time.sleep(sleep_time)
        elif cmd.startswith("echo"):
            # 处理echo命令
            print(cmd)
        else:
            # 处理adb命令
            if not cmd.startswith("adb"):
                cmd = f"adb -s {adb_device_id} {cmd}"
            else:
                # 检查命令是否已经包含设备ID参数
                if "-s " not in cmd:
                    # 在adb后添加设备ID
                    cmd = cmd.replace("adb ", f"adb -s {adb_device_id} ")
            
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"命令执行失败: {cmd}")
                    print(f"错误信息: {result.stderr}")
                    return False
                else:
                    print(f"命令执行成功: {cmd}")
            except Exception as e:
                print(f"执行命令时出错: {e}")
                return False
    
    print("所有ADB命令执行完成")
    return True


def append_step_log(step_log_path, step_id, before_img, after_img, reason, action_info):
    """
    追加写入每步的图像路径和操作描述到step_log.jsonl
    """
    log_entry = {
        "step_id": step_id,
        "before_img": before_img,
        "after_img": after_img,
        "reason": reason,
        "action_info": action_info,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(step_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def create_task_specific_storage(task_description: str, task_id: str, app_name: str = None, device_id: str = None):
    """
    创建任务特定的存储目录和标识
    """
    # 创建任务特定的输出目录（支持设备特定结构）
    if device_id:
        device_safe_id = device_id.replace(':', '_').replace('.', '_')
        task_output_dir = Path(f"test_task/device_{device_safe_id}/task_{task_id}")
    else:
        task_output_dir = Path(f"test_task/task_{task_id}")
    task_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建任务信息文件
    task_info = {
        "task_id": task_id,
        "global_task": task_description,
        "app_name": app_name or "unknown_app",
        "created_at": datetime.now().isoformat(),
        "status": "in_progress"
    }
    
    task_info_file = task_output_dir / "task_info.json"
    with open(task_info_file, 'w', encoding='utf-8') as f:
        json.dump(task_info, f, ensure_ascii=False, indent=2)

    print(f"📁 任务存储目录: {task_output_dir}")
    return task_output_dir

def save_step_to_task_storage(task_output_dir: Path, step_data: dict):
    """
    保存步骤信息到任务特定的存储目录
    """
    step_file = task_output_dir / f"step_{step_data['step_id']:02d}.json"
    with open(step_file, 'w', encoding='utf-8') as f:
        json.dump(step_data, f, ensure_ascii=False, indent=2)

@api_retry(max_retries=3, delay=1.0)
def _call_task_completion_api(client, prompt: str, latest_screenshot_base64: str):
    """
    调用任务完成判断API的内部函数
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{latest_screenshot_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=500,
        temperature=0.1
    )
    return response.choices[0].message.content.strip()


def check_global_task_completion_with_llm(task_history, whole_task, step_count, latest_screenshot_path):
    """
    使用大模型判断全局任务是否完成
    """
    if not task_history or step_count < 1:  
        return {
            "is_completed": False,
            "reason": "步骤数不足，无法判断任务完成状态",
            "confidence": 0.0
        }
    
    try:
        # 准备历史记录摘要
        history_summary = []
        for i, step in enumerate(task_history[-10:], 1):  # 只取最近10步
            step_info = {
                "step": i,
                "action": step.get('action', 'unknown'),
                "reason": step.get('reason', ''),
                "success": step.get('success', False),
                "target_element_description": step.get('target_element_description', ''),
                "thought": step.get('thought', '')
            }
            history_summary.append(step_info)
        
        # 编码最新截图
        latest_screenshot_base64 = encode_image(latest_screenshot_path)
        
        # 构建判断提示
        prompt = f"""
你是一个任务完成度评估专家。请根据以下信息判断全局任务是否已经完成：

全局任务：{whole_task}

最近的操作历史：
{json.dumps(history_summary, ensure_ascii=False, indent=2)}

当前步骤数：{step_count}

请查看当前截图，结合任务描述和操作历史，判断全局任务是否已经完成。

判断标准：
1. 任务的主要目标是否已经达成
2. 界面是否显示了任务完成的状态或结果
3. 是否已经到达了任务的最终状态
4. **重要：完整流程判断逻辑**：
   - 必须严格按照任务描述的完整流程进行判断
   - 仅仅回到桌面不代表任务完成，除非任务的最后一步就是回到桌面
   - 如果任务包含多个连续步骤，必须确保所有步骤都已执行完毕
5. **清除进程任务的特殊判断**：
   **重要：一旦操作历史中提到了点击X键清除进程，立即判断任务完成**
   如果任务包含「点击x键清除进程」、「清除进程」、「后台进程」等清理操作：
   - **只要操作历史中的任何一步提到了"点击x键清除进程"、"清除进程"、"清理进程"等操作**
   - **无论是在reason字段、thought字段还是target_element_description字段中**
   - **立即判断为任务完成，completed: true**
   - **不需要等待回到桌面或其他后续操作**
6. **桌面界面识别标准**：
   - ✅ 显示手机桌面壁纸背景
   - ✅ 显示多个应用图标整齐排列
   - ✅ 显示底部导航栏（通常包含返回、主页、多任务按钮）
   - ✅ 显示状态栏（时间、电量、信号等）
   - ❌ 没有特定应用的标题栏、菜单栏
   - ❌ 没有应用内的具体功能界面
7. **关键：避免误判的检查点**：
   - 如果任务流程是："...点击【Home】键回到桌面-点击【后台进程】键-点击x键清除进程"
   - 当执行完"点击【Home】键回到桌面"后，虽然界面显示桌面，但任务尚未完成
   - 当执行完"点击【后台进程】键"后，虽然进入了后台进程界面，但任务仍未完成
   - **必须严格检查操作历史的最后几步操作**：
     * 检查操作历史中的reason、thought、target_element_description字段是否包含"x键"、"清除"、"关闭"、"删除"、"清理"、"清除进程"等明确的清理关键词
     * 仅仅是"点击【后台进程】键"不算完成，必须有后续的清除动作
     * 如果操作历史中已经存在清除操作，且当前截图显示桌面界面，则判断为完成
   - **重要：操作历史完整性检查**：
     * 不仅检查最后一步，还要检查最近几步操作中是否包含清除动作
     * 特别注意检查reason字段中的操作描述，如"点击x键清除进程"、"清除进程操作成功"等
     * 如果历史记录显示已执行清除操作并返回桌面，即使不是最后一步，也应判断为完成
   - **操作描述关键词识别**：
     * 在reason、thought、target_element_description字段中查找："点击x键清除进程"、"清除进程"、"内存已释放"、"清理操作"、"清理进程"、"删除进程"等描述
     * **关键：一旦发现这些关键描述，立即判断任务完成，无需检查界面状态**
     * **优先级最高：清除进程操作的存在比界面状态更重要**


**重要：请严格按照以下JSON格式返回结果，不要添加任何其他文本、解释或markdown格式：**

{{
    "completed": true,
    "reason": "具体的判断理由",
    "confidence": "具体数值"
}}

或者：

{{
    "completed": false,
    "reason": "具体的判断理由",
    "confidence": "具体数值"
}}

请确保返回的是纯JSON格式，completed字段为布尔值，confidence字段为0.0到1.0之间的数值。
"""
        
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        
        # 使用带重试机制的API调用
        result_text = _call_task_completion_api(client, prompt, latest_screenshot_base64)
        print(f"🤖 大模型判断结果: {result_text}")
        
        # 解析JSON结果 - 支持多种格式
        import re
        result = None
        
        # 清理文本
        cleaned_text = result_text.strip()
        
        # 方法1: 直接解析JSON
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            pass
        
        # 方法2: 提取markdown代码块中的JSON
        if result is None:
            json_patterns = [
                r'```json\s*({[\s\S]*?})\s*```',  # ```json {content} ```
                r'```\s*({[\s\S]*?})\s*```',      # ``` {content} ```
                r'`({[\s\S]*?})`',                # `{content}`
            ]
            
            for pattern in json_patterns:
                json_match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1).strip())
                        break
                    except json.JSONDecodeError:
                        continue
        
        # 方法3: 提取任何JSON格式的内容（最宽松的匹配）
        if result is None:
            # 查找最外层的大括号内容
            brace_patterns = [
                r'({\s*"completed"[\s\S]*?})',     # 包含completed字段的JSON
                r'({[\s\S]*?"completed"[\s\S]*?})', # 包含completed字段的JSON（任意位置）
                r'({[\s\S]*?})',                   # 任何大括号内容
            ]
            
            for pattern in brace_patterns:
                matches = re.findall(pattern, cleaned_text)
                for match in matches:
                    try:
                        result = json.loads(match.strip())
                        if 'completed' in result:  # 优先选择包含completed字段的结果
                            break
                    except json.JSONDecodeError:
                        continue
                if result and 'completed' in result:
                    break
        
        # 如果所有方法都失败
        if result is None:
            print(f"⚠️ 大模型返回结果解析失败，原始内容: {result_text}")
            print("⚠️ 尝试了多种解析方法但都失败，默认任务未完成")
            return {
                "is_completed": False,
                "reason": "大模型返回结果解析失败",
                "confidence": 0.0
            }
        
        # 提取结果字段
        completed = result.get('completed', False)
        reason = result.get('reason', '')
        confidence = result.get('confidence', 0.0)
        
        if completed and confidence > 0.7:
            print(f"🎯 大模型判断任务已完成 (置信度: {confidence:.2f}): {reason}")
            return {
                "is_completed": True,
                "reason": reason,
                "confidence": confidence
            }
        else:
            print(f"⏳ 大模型判断任务未完成 (置信度: {confidence:.2f}): {reason}")
            return {
                "is_completed": False,
                "reason": reason,
                "confidence": confidence
            }
            
    except Exception as e:
        print(f"❌ 大模型判断出错: {e}")
        return {
            "is_completed": False,
            "reason": f"大模型判断出错: {e}",
            "confidence": 0.0
        }

def main(device_id=None):
    print("🎮 UI-TARS Automation System with Enhanced Memory")
    print("=" * 50)
    
    # 初始化记忆系统
    memory_system = None
    task_history = []  # 用于记录任务执行历史
    task_saved_to_memory = False  # 标记任务是否已保存到记忆系统
    if MEMORY_AVAILABLE:
        try:
            memory_system = MemorySystem()
            print("✅ Memory system initialized successfully")
            
            # 获取系统统计
            stats = memory_system.get_system_stats()
            print(f"📊 当前记忆系统状态:")
            print(f"   - 经验记录数: {stats['storage']['experiential_memories']}")
            print(f"   - 事实记录数: {stats['storage']['declarative_memories']}")
            print(f"   - 总记录数: {stats['storage']['total']}")
            
        except Exception as e:
            print(f"❌ Failed to initialize memory system: {e}")
            print("Continuing without memory functionality...")
            memory_system = None  # 确保设置为None
    
    # 选择任务输入模式
    print("\n📋 请选择任务输入模式:")
    print("1. 单任务模式 - 手动输入一个任务")
    print("2. CSV批量模式 - 从CSV文件读取多个任务")
    print("3. 创建CSV模板 - 生成CSV任务文件模板")
    
    while True:
        try:
            mode_choice = input("\n请选择模式 (1/2/3): ").strip()
            if mode_choice in ['1', '2', '3']:
                break
            else:
                print("❌ 请输入 1、2 或 3")
        except KeyboardInterrupt:
            print("\n❌ 操作已取消")
            return
    
    # 处理CSV模板创建
    if mode_choice == '3':
        template_path = input("\n请输入CSV模板文件路径 (默认: tasks_template.csv): ").strip()
        if not template_path:
            template_path = "tasks_template.csv"
        
        if create_csv_template(template_path):
            print(f"\n✅ CSV模板已创建，请编辑文件后重新运行程序")
            print(f"📁 文件位置: {os.path.abspath(template_path)}")
        return
    
    # 初始化任务队列
    task_queue = []
    current_task_index = 0
    
    if mode_choice == '1':
        # 单任务模式
        print("\n请输入全局任务描述（支持多行，输入单独一行 END 结束）：")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        whole_task = "\n".join(lines)
        
        # 获取应用名称（可选）
        app_name = input("\n📱 请输入应用名称(可选): ").strip() or None
        
        # 添加到任务队列
        task_queue.append({
            'task_description': whole_task,
            'app_name': app_name,
            'source': 'manual'
        })
        
    elif mode_choice == '2':
        # CSV批量模式
        csv_path = input("\n请输入CSV文件路径: ").strip()
        if not csv_path:
            print("❌ 未输入CSV文件路径")
            return
        
        # 去除路径中的双引号（如果有的话）
        csv_path = csv_path.strip('"').strip("'")
        
        # 加载CSV任务
        csv_tasks = load_tasks_from_csv(csv_path)
        if not csv_tasks:
            print("❌ 未能加载任何任务，程序退出")
            return
        
        # 转换为任务队列格式
        for task in csv_tasks:
            task_queue.append({
                'task_description': task['task_description'],
                'app_name': task['app_name'],
                'source': 'csv',
                'row_number': task['row_number']
            })
        
        print(f"\n📋 已加载 {len(task_queue)} 个任务，将按顺序执行")
    
    # 获取当前任务
    current_task = task_queue[current_task_index]
    whole_task = current_task['task_description']
    app_name = current_task['app_name']
    
    # 生成任务ID
    if current_task['source'] == 'csv':
        task_id = f"csv_task_{current_task_index + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n🆔 当前任务 ({current_task_index + 1}/{len(task_queue)}): {task_id}")
        print(f"📝 任务描述: {whole_task}")
        if app_name:
            print(f"📱 应用名称: {app_name}")
    else:
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🆔 Task ID: {task_id}")

    # 设备选择功能 - 支持参数、环境变量和交互式选择
    adb_device_id = None
    
    # 1. 优先使用传入的device_id参数
    if device_id:
        adb_device_id = device_id
        print(f"🎯 使用指定的设备ID: {adb_device_id}")
    
    # 2. 其次检查环境变量
    elif os.environ.get('UITARS_DEVICE_ID'):
        adb_device_id = os.environ.get('UITARS_DEVICE_ID')
        print(f"🌍 使用环境变量中的设备ID: {adb_device_id}")
    
    # 3. 验证指定的设备是否连接
    if adb_device_id:
        connected_devices = list_connected_devices()
        if not connected_devices:
            print("❌ 未检测到已连接的 ADB 设备，请检查连接后重试。")
            return
        
        if adb_device_id not in connected_devices:
            print(f"❌ 指定的设备 '{adb_device_id}' 未连接或不可用")
            print(f"📱 当前已连接的设备: {', '.join(connected_devices)}")
            return
        
        print(f"✅ 设备连接验证成功: {adb_device_id}")
    
    # 4. 如果没有指定设备，则进行交互式选择
    else:
        connected_devices = list_connected_devices()
        if not connected_devices:
            print("❌ 未检测到已连接的 ADB 设备，请检查连接后重试。")
            return
        
        if len(connected_devices) == 1:
            # 只有一个设备，直接使用
            adb_device_id = connected_devices[0]
            print(f"✅ 检测到设备ID: {adb_device_id}")
        else:
            # 多个设备，让用户选择
            print(f"\n📱 检测到 {len(connected_devices)} 个已连接的设备:")
            for i, device_id in enumerate(connected_devices, 1):
                print(f"  {i}. {device_id}")
            
            while True:
                try:
                    choice = input(f"\n请选择要使用的设备 (1-{len(connected_devices)}) 或输入完整设备ID: ").strip()
                    
                    # 检查是否是数字选择
                    if choice.isdigit():
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(connected_devices):
                            adb_device_id = connected_devices[choice_num - 1]
                            print(f"✅ 已选择设备: {adb_device_id}")
                            break
                        else:
                            print(f"❌ 请输入 1-{len(connected_devices)} 之间的数字")
                            continue
                    
                    # 检查是否是完整设备ID
                    if choice in connected_devices:
                        adb_device_id = choice
                        print(f"✅ 已选择设备: {adb_device_id}")
                        break
                    else:
                        print(f"❌ 设备ID '{choice}' 不在已连接设备列表中")
                        
                except (ValueError, KeyboardInterrupt):
                    print("\n❌ 操作已取消")
                    return

    # 确保设备ID已正确设置
    if not adb_device_id:
        print("❌ 设备ID未正确设置，程序退出")
        return

    # 创建任务特定的存储目录
    task_output_dir = create_task_specific_storage(whole_task, task_id, app_name, adb_device_id)

    # 记忆系统已准备就绪，将在每一步中进行经验检索
    if memory_system:
        print("\n🧠 记忆系统已启动，将在每一步操作中检索相关经验")

    # 设置默认的自定义提示词，专门处理输入文本操作和系统按键操作
    default_custom_prompt = """## 输入文本操作特殊规则
当接收到以"输入"开头的子任务时，请严格遵循以下规则：

【直接输入规则】：
1. 当子任务是"输入xxx"时，直接使用type(content='xxx')命令
2. 不要先点击输入框，直接执行输入操作
3. 例如：子任务"输入100" → 直接执行type(content='100')
4. 例如：子任务"输入搜索关键词" → 直接执行type(content='搜索关键词')

【避免重复点击】：
- 不要执行：点击输入框 → 输入文本
- 直接执行：type(content='文本内容')

这样可以避免重复点击输入框的问题，直接完成文本输入操作。

## 系统按键操作特殊规则
当需要执行系统按键操作时，请严格遵循以下规则：

【系统按键操作】：
1. 对于Home键操作：必须输出具体的Action命令
2. 对于Back键操作：必须输出具体的Action命令
3. 对于Menu键操作：必须输出具体的Action命令
4. 绝对不允许输出描述性文字，如"返回桌面"、"点击Home键"等

【正确示例】：
- 任务："点击Home键返回桌面" → 输出：hotkey(key='home')
- 任务："点击返回键" → 输出：hotkey(key='back')
- 任务："点击菜单键" → 输出：hotkey(key='menu')

【错误示例】：
- 不要输出："返回到桌面"
- 不要输出："点击Home按钮"
- 不要输出："执行返回操作"

必须确保系统按键操作输出具体的Action命令格式。"""
    
    # 获取自定义提示词（可选）
    print("\n（请输入自定义提示词（可选），直接回车使用默认提示词）：")
    user_custom_prompt = input().strip()
    if user_custom_prompt:
        custom_prompt = user_custom_prompt
        print(f"自定义提示词: {custom_prompt}")
    else:
        custom_prompt = default_custom_prompt
        print("使用默认提示词（针对输入文本操作优化）")
    
    # 添加截图等待时间配置
    print("\n请输入截图等待时间（秒，默认0.5秒，范围0.3-2.0）：")
    screenshot_wait_input = input().strip()
    try:
        screenshot_wait_time = float(screenshot_wait_input) if screenshot_wait_input else 0.5
        # 限制在合理范围内
        screenshot_wait_time = max(0.3, min(2.0, screenshot_wait_time))
    except ValueError:
        screenshot_wait_time = 0.5
    print(f"截图等待时间设置为: {screenshot_wait_time}秒")
    
    # 添加经验优化全局选择
    use_experience_optimization = True  # 默认启用
    if memory_system:
        print("\n🧠 经验优化设置:")
        print("1. 启用经验优化 - 根据历史经验优化子任务规划（推荐）")
        print("2. 禁用经验优化 - 直接使用初步子任务规划")
        
        while True:
            try:
                choice = input("\n请选择是否启用经验优化 (1/2，默认1): ").strip()
                if choice == '' or choice == '1':
                    use_experience_optimization = True
                    print("✅ 已启用经验优化，将根据历史经验优化子任务规划")
                    break
                elif choice == '2':
                    use_experience_optimization = False
                    print("⚠️ 已禁用经验优化，将直接使用初步子任务规划")
                    break
                else:
                    print("❌ 请输入 1 或 2")
            except KeyboardInterrupt:
                print("\n❌ 操作已取消")
                return
    else:
        use_experience_optimization = False
        print("\n⚠️ 记忆系统不可用，将直接使用初步子任务规划")

    # 自动获取分辨率
    width, height = get_device_resolution(adb_device_id)
    print(f"设备分辨率: {width}x{height}")

    # 文件夹设置（使用task_output_dir统一管理）
    task_base_dir = str(task_output_dir)
    img_folder = os.path.join(task_base_dir, "img")
    outputs_folder = os.path.join(task_base_dir, "outputs")
    os.makedirs(img_folder, exist_ok=True)
    os.makedirs(outputs_folder, exist_ok=True)
    
    print(f"📁 任务目录: {task_base_dir}")
    print(f"📷 截图目录: {img_folder}")
    print(f"📊 输出目录: {outputs_folder}")

    step_count = 1
    current_screenshot = None  # 用于存储当前需要处理的截图
    
    # 开始循环执行
    while True:
        print(f"\n=== 第 {step_count} 步操作 ===")
        print(f"全局任务: {whole_task}")
        
        # 如果没有当前截图，则进行初始截图
        if current_screenshot is None:
            screenshot_path = os.path.join(img_folder, f"screenshot_step{step_count}.png")
            current_screenshot = capture_screenshot(adb_device_id, screenshot_path)
            if not current_screenshot:
                print("截图失败，停止执行")
                break
        else:
            # 使用上一步处理完ADB操作后的截图
            screenshot_path = current_screenshot

        # 使用UI-TARS模型处理截图（包含步骤级经验检索）
        process_result = process_screenshot_with_uitars(
            screenshot_path, 
            whole_task, 
            step_count, 
            width, 
            height,
            custom_prompt,
            memory_system,
            task_base_dir,
            adb_device_id,
            use_experience_optimization
        )
        
        if not process_result:
            print("UI-TARS模型处理失败，跳过当前步骤")
            break
        
        # 获取带标注的截图路径
        annotated_before_img = process_result.get("annotated_screenshot_path", screenshot_path)
        
        # 执行ADB命令
        print("开始执行生成的ADB命令...")
        success = execute_adb_commands(process_result["adb_commands"], adb_device_id)
        
        # 记录步骤到记忆系统和任务特定存储（暂时不调用evaluate_task_success，等截图后再调用）
        if memory_system:
            try:
                analysis_result = process_result["analysis_result"]
                parsed_action = analysis_result["parsed_action"]
                
                step_data = {
                    "step_id": step_count,
                    "timestamp": datetime.now().isoformat(),
                    "action": parsed_action.get("action", "unknown"),
                    "target_element_description": parsed_action.get("target", "unknown"),
                    "thought": parsed_action.get("thought", ""),
                    "success": success,  # 暂时使用ADB执行结果
                    "reason": "",  # 稍后更新
                    "coordinates": parsed_action.get("coordinates"),
                    "absolute_coordinates": analysis_result.get("absolute_coordinates"),
                    "error": None if success else "ADB command execution failed",
                    "task_id": task_id,
                    "app_name": app_name if app_name is not None else "unknown_app",
                    "screenshot_before": annotated_before_img,
                    "adb_commands": process_result["adb_commands"],
                    "current_subtask": analysis_result.get("current_subtask", "")  # 添加子任务描述
                }
                
                # 显示步骤记录
                status = "✅" if success else "❌"
                print(f"{status} Step {step_count}: {step_data['action']} on '{step_data['target_element_description']}'")
                if step_data['thought']:
                    print(f"   🧠 推理: {step_data['thought']}")
                if step_data['coordinates']:
                    print(f"   📍 坐标: {step_data['coordinates']}")
                if step_data['error']:
                    print(f"   ⚠️ 错误: {step_data['error']}")
                    
            except Exception as e:
                print(f"⚠️ Failed to record step: {e}")
        
        if not success:
            print("ADB命令执行失败")
            # 询问是否继续
            user_input = input("ADB命令执行失败，是否继续下一步？(y/n): ").strip().lower()
            if user_input not in ['y', 'yes', '']:
                break
        
        print(f"\n第 {step_count} 步操作处理完成")
        print(f"等待界面切换...({screenshot_wait_time}秒)")
        
        # 等待界面切换（使用可配置时间）
        time.sleep(screenshot_wait_time)
        
        # 截图捕获新界面
        print("正在截图捕获新界面...")
        next_screenshot_path = os.path.join(img_folder, f"screenshot_step{step_count + 1}.png")
        next_screenshot = capture_screenshot(adb_device_id, next_screenshot_path)
        
        if not next_screenshot:
            print("新界面截图失败")
            current_screenshot = None
        else:
            print(f"新界面截图已保存: {next_screenshot}")
            
            # 评估本轮任务是否执行成功
            print(f"\n=== 开始评估第 {step_count} 步任务执行结果 ===")
            print(f"操作前截图(带标注): {annotated_before_img}")
            print(f"操作后截图: {next_screenshot}")
            print(f"分析结果文件: {process_result['analysis_json_path']}")
            
            # 现在可以调用evaluate_task_success了
            if memory_system:
                try:
                    result = evaluate_task_success(annotated_before_img, next_screenshot, process_result["analysis_json_path"])
                    print(f"本轮子任务执行判定：{result}")
                    
                    # 更新step_data中的success和reason字段
                    step_data["success"] = result.get("success", success)
                    step_data["reason"] = result.get("reason", "")
                    
                    # 现在将完整的step_data添加到task_history
                    task_history.append(step_data)
                    
                    # 保存步骤到任务特定存储
                    save_step_to_task_storage(task_output_dir, step_data)
                    
                except Exception as e:
                    print(f"⚠️ Failed to evaluate task success: {e}")
                    # 如果评估失败，仍然保存基本信息
                    task_history.append(step_data)
                    save_step_to_task_storage(task_output_dir, step_data)
            
            print("=== 任务评估完成 ===\n")
            
            # 记录历史
            analysis_result = process_result["analysis_result"]
            parsed_action = analysis_result["parsed_action"]
            entry = {
                "task_id": whole_task,
                "subtask_id": analysis_result.get("current_subtask", ""),
                "step_id": step_count,
                "ui_context": {
                    "subtask": analysis_result.get("current_subtask", ""),
                    "comprehension": parsed_action.get("thought", ""),
                    "global_task": whole_task
                },
                "action": {
                    "interaction_object": parsed_action.get("action", ""),
                    "type": parsed_action.get("action", ""),
                    "coordinates": analysis_result["absolute_coordinates"]
                },
                "before_img": annotated_before_img,
                "after_img": next_screenshot,
                "response_json": process_result["analysis_json_path"],
                "success": result.get("success"),
                "reason": result.get("reason")
            }
            append_entry_to_jsonl(os.path.join(outputs_folder, "history.jsonl"), entry)
            
            # 写入step_log.jsonl
            append_step_log(
                os.path.join(outputs_folder, "step_log.jsonl"), 
                step_count, 
                annotated_before_img, 
                next_screenshot, 
                result.get("reason"),
                {
                    "action_type": parsed_action.get("action"),
                    "thought": parsed_action.get("thought"),
                    "coordinates": analysis_result["absolute_coordinates"]
                }
            )
            
            # 判断未加载内容并处理
            next_screenshot = check_and_handle_unloaded_content(
                current_img_path=annotated_before_img,
                after_img_path=next_screenshot,
                response_json_path=process_result["analysis_json_path"],
                adb_device_id=adb_device_id,
                img_folder=img_folder,
                step_count=step_count
            )
            
            current_screenshot = next_screenshot
            
            # 检查是否已完成任务
            if parsed_action.get("action") == "finished":
                print("任务已完成！")
                break
        
        # 自动判断是否继续下一步
        print("\n🤖 自动判断是否继续下一步操作...")
        
        # 检查全局任务是否完成
        task_completed = check_global_task_completion_with_llm(task_history, whole_task, step_count, current_screenshot)
        
        if task_completed and task_completed.get('is_completed', False):
            print("🎯 检测到全局任务已完成，自动退出")
            
            # 自动选择不存入记忆系统
            save_to_memory = 'n'
            
            if save_to_memory == 'y' and memory_system:
                try:
                    evaluation_result = input("📊 任务是否成功完成？(y/n): ").strip().lower()
                    is_successful = evaluation_result == 'y'
                    
                    final_evaluation = input("📝 请输入最终评价(可选): ").strip() or None
                    
                    if ENABLE_EXPERIENCE_LEARNING:
                        experience_id = learn_from_task_with_reflection(
                            memory_system=memory_system,
                            raw_history=task_history,
                            task_description=whole_task,
                            is_successful=is_successful,
                            source_task_id=task_id,
                            app_name=app_name if app_name is not None else "unknown_app"
                        )
                    else:
                        experience_id = "learning_disabled"
                    
                    # 更新任务状态
                    task_info_file = task_output_dir / "task_info.json"
                    if task_info_file.exists():
                        with open(task_info_file, 'r', encoding='utf-8') as f:
                            task_info = json.load(f)
                        task_info["status"] = "completed"
                        task_info["completed_at"] = datetime.now().isoformat()
                        task_info["is_successful"] = is_successful
                        task_info["final_evaluation"] = final_evaluation
                        task_info["experience_id"] = experience_id
                        task_info["steps_executed"] = len(task_history)
                        with open(task_info_file, 'w', encoding='utf-8') as f:
                            json.dump(task_info, f, ensure_ascii=False, indent=2)
                    
                    # 保存最终任务总结
                    task_summary = {
                        "task_id": task_id,
                        "global_task": whole_task,
                        "app_name": app_name if app_name is not None else "unknown_app",
                        "experience_id": experience_id,
                        "is_successful": is_successful,
                        "final_evaluation": final_evaluation,
                        "steps_executed": len(task_history),
                        "completed_at": datetime.now().isoformat(),
                        "exit_reason": "user_quit"
                    }
                    
                    summary_file = task_output_dir / "task_summary.json"
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        json.dump(task_summary, f, ensure_ascii=False, indent=2)
                    
                    if ENABLE_EXPERIENCE_LEARNING:
                        print(f"\n🧠 Experience learned: {experience_id}")
                    else:
                        print(f"\n🚫 经验学习已禁用")
                    print(f"📊 Task result: {'Success' if is_successful else 'Failed'}")
                    print(f"📝 Steps executed: {len(task_history)}")
                    print(f"💾 任务结果保存: {summary_file}")
                    
                    task_saved_to_memory = True  # 标记任务已保存到记忆系统
                    
                except Exception as e:
                    print(f"⚠️ Failed to learn from task: {e}")
            elif save_to_memory == 'y' and not memory_system:
                print("⚠️ 记忆系统不可用，无法保存任务经验")
            else:
                print("📝 任务未保存到记忆系统")
            
            break
        else:
            # 自动继续下一步
            print("✅ 自动继续下一步操作")
            step_count += 1
            print("准备处理新界面...")
            continue
    
    # 任务结束处理
    if memory_system and task_history and not task_saved_to_memory:
        try:
            print("\n🎯 任务执行完成，自动处理...")
            # 自动判断任务成功
            is_successful = True  # 既然任务完成，默认为成功
            final_evaluation = "自动完成的任务"
            
            if ENABLE_EXPERIENCE_LEARNING:
                experience_id = learn_from_task_with_reflection(
                    memory_system=memory_system,
                    raw_history=task_history,
                    task_description=whole_task,
                    is_successful=is_successful,
                    source_task_id=task_id,
                    app_name=app_name if app_name is not None else "unknown_app"
                )
            else:
                experience_id = "learning_disabled"
            
            # 更新任务信息
            task_info_file = task_output_dir / "task_info.json"
            if task_info_file.exists():
                with open(task_info_file, 'r', encoding='utf-8') as f:
                    task_info = json.load(f)
                task_info["status"] = "completed"
                task_info["completed_at"] = datetime.now().isoformat()
                task_info["is_successful"] = is_successful
                task_info["final_evaluation"] = final_evaluation
                task_info["experience_id"] = experience_id
                task_info["steps_executed"] = len(task_history)
                with open(task_info_file, 'w', encoding='utf-8') as f:
                    json.dump(task_info, f, ensure_ascii=False, indent=2)
            
            # 生成任务总结
            task_summary = {
                "task_id": task_id,
                "global_task": whole_task,
                "app_name": app_name if app_name is not None else "unknown_app",
                "experience_id": experience_id,
                "is_successful": is_successful,
                "final_evaluation": final_evaluation,
                "steps_executed": len(task_history),
                "completed_at": datetime.now().isoformat(),
                "exit_reason": "task_finished"
            }
            
            summary_file = task_output_dir / "task_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(task_summary, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 任务已完成")
            if ENABLE_EXPERIENCE_LEARNING:
                print(f"🧠 Experience learned: {experience_id}")
            else:
                print(f"🚫 经验学习已禁用")
            print(f"📊 Task result: {'Success' if is_successful else 'Failed'}")
            print(f"📝 Steps executed: {len(task_history)}")
            print(f"📁 任务目录: {task_output_dir}")
            print(f"💾 任务总结保存: {summary_file}")
            
        except Exception as e:
            print(f"⚠️ Failed to learn from task: {e}")
    
    # 检查是否还有下一个任务（CSV批量模式）
    if len(task_queue) > 1 and current_task_index < len(task_queue) - 1:
        current_task_index += 1
        print(f"\n🔄 准备执行下一个任务 ({current_task_index + 1}/{len(task_queue)})")
        print("=" * 60)
        
        # 递归调用main函数执行下一个任务
        # 但需要传递任务队列和当前索引
        execute_next_task_from_queue(task_queue, current_task_index, adb_device_id, memory_system, screenshot_wait_time, use_experience_optimization)
    else:
        if len(task_queue) > 1:
            print(f"\n🎉 所有任务已完成！共执行了 {len(task_queue)} 个任务")
        else:
            print(f"\n🎉 任务执行完成！")


def execute_next_task_from_queue(task_queue, current_task_index, adb_device_id, memory_system, screenshot_wait_time=0.5, use_experience_optimization=True):
    """
    执行任务队列中的下一个任务
    """
    if current_task_index >= len(task_queue):
        print("\n🎉 所有任务已完成！")
        return
    
    # 获取当前任务
    current_task = task_queue[current_task_index]
    whole_task = current_task['task_description']
    app_name = current_task['app_name']
    
    # 生成任务ID
    task_id = f"csv_task_{current_task_index + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n🆔 当前任务 ({current_task_index + 1}/{len(task_queue)}): {task_id}")
    print(f"📝 任务描述: {whole_task}")
    if app_name:
        print(f"📱 应用名称: {app_name}")
    
    # 创建任务存储
    task_output_dir = create_task_specific_storage(whole_task, task_id, app_name, adb_device_id)
    
    # 创建img和outputs子文件夹（与main函数保持一致）
    img_folder = task_output_dir / "img"
    outputs_folder = task_output_dir / "outputs"
    img_folder.mkdir(exist_ok=True)
    outputs_folder.mkdir(exist_ok=True)
    
    print(f"📁 任务目录: {task_output_dir}")
    print(f"📷 截图目录: {img_folder}")
    print(f"📊 输出目录: {outputs_folder}")
    
    # 自动获取分辨率（与main函数保持一致）
    width, height = get_device_resolution(adb_device_id)
    print(f"设备分辨率: {width}x{height}")
    
    # 初始化任务历史
    task_history = []
    task_saved_to_memory = False
    step_count = 1
    
    # 设置默认的自定义提示词（与main函数保持一致）
    default_custom_prompt = """## 输入文本操作特殊规则
当接收到以"输入"开头的子任务时，请严格遵循以下规则：

【直接输入规则】：
1. 当子任务是"输入xxx"时，直接使用type(content='xxx')命令
2. 不要先点击输入框，直接执行输入操作
3. 例如：子任务"输入100" → 直接执行type(content='100')
4. 例如：子任务"输入搜索关键词" → 直接执行type(content='搜索关键词')

【避免重复点击】：
- 不要执行：点击输入框 → 输入文本
- 直接执行：type(content='文本内容')

这样可以避免重复点击输入框的问题，直接完成文本输入操作。

## 系统按键操作特殊规则
当需要执行系统按键操作时，请严格遵循以下规则：

【系统按键操作】：
1. 对于Home键操作：必须输出具体的Action命令
2. 对于Back键操作：必须输出具体的Action命令
3. 对于Menu键操作：必须输出具体的Action命令
4. 绝对不允许输出描述性文字，如"返回桌面"、"点击Home键"等

【正确示例】：
- 任务："点击Home键返回桌面" → 输出：hotkey(key='home')
- 任务："点击返回键" → 输出：hotkey(key='back')
- 任务："点击菜单键" → 输出：hotkey(key='menu')

【错误示例】：
- 不要输出："返回到桌面"
- 不要输出："点击Home按钮"
- 不要输出："执行返回操作"

必须确保系统按键操作输出具体的Action命令格式。"""
    custom_prompt = default_custom_prompt  # 批量任务执行使用默认提示词
    
    print(f"\n🚀 开始执行任务: {whole_task}")
    print("使用默认提示词（针对输入文本操作优化）")
    
    # 执行任务的主循环（复制main函数中的核心逻辑）
    while True:
        try:
            # 获取当前截图（保存到img子文件夹）
            screenshot_filename = f"screenshot_step_{step_count:02d}.png"
            screenshot_path = img_folder / screenshot_filename
            screenshot_cmd = f"adb -s {adb_device_id} exec-out screencap -p > {screenshot_path}"
            result = subprocess.run(screenshot_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ 截图失败: {result.stderr}")
                break
            
            print(f"\n📸 已获取第 {step_count} 步截图: {screenshot_path}")
            
            # 检查任务是否完成
            if step_count > 1:  # 从第二步开始检查
                completion_result = check_global_task_completion_with_llm(
                    task_history, whole_task, step_count, screenshot_path
                )
                
                if completion_result and completion_result.get('is_completed', False):
                    print(f"\n🎯 大模型判断任务已完成: {completion_result.get('reason', '未提供原因')}")
                    
                    # 保存任务完成信息
                    if memory_system and task_history and not task_saved_to_memory:
                        try:
                            is_successful = True
                            final_evaluation = completion_result.get('reason', '自动完成的任务')
                            
                            if ENABLE_EXPERIENCE_LEARNING:
                                experience_id = learn_from_task_with_reflection(
                                    memory_system=memory_system,
                                    raw_history=task_history,
                                    task_description=whole_task,
                                    is_successful=is_successful,
                                    source_task_id=task_id,
                                    app_name=app_name if app_name is not None else "unknown_app"
                                )
                            else:
                                experience_id = "learning_disabled"
                            
                            # 更新任务信息
                            task_info_file = task_output_dir / "task_info.json"
                            if task_info_file.exists():
                                with open(task_info_file, 'r', encoding='utf-8') as f:
                                    task_info = json.load(f)
                                task_info["status"] = "completed"
                                task_info["completed_at"] = datetime.now().isoformat()
                                task_info["is_successful"] = is_successful
                                task_info["final_evaluation"] = final_evaluation
                                task_info["experience_id"] = experience_id
                                task_info["steps_executed"] = len(task_history)
                                with open(task_info_file, 'w', encoding='utf-8') as f:
                                    json.dump(task_info, f, ensure_ascii=False, indent=2)
                            
                            # 生成任务总结
                            task_summary = {
                                "task_id": task_id,
                                "global_task": whole_task,
                                "app_name": app_name if app_name is not None else "unknown_app",
                                "experience_id": experience_id,
                                "is_successful": is_successful,
                                "final_evaluation": final_evaluation,
                                "steps_executed": len(task_history),
                                "completed_at": datetime.now().isoformat(),
                                "exit_reason": "task_finished"
                            }
                            
                            summary_file = task_output_dir / "task_summary.json"
                            with open(summary_file, 'w', encoding='utf-8') as f:
                                json.dump(task_summary, f, ensure_ascii=False, indent=2)
                            
                            print(f"\n✅ 任务已完成")
                            if ENABLE_EXPERIENCE_LEARNING:
                                print(f"🧠 Experience learned: {experience_id}")
                            else:
                                print(f"🚫 经验学习已禁用")
                            print(f"📊 Task result: {'Success' if is_successful else 'Failed'}")
                            print(f"📝 Steps executed: {len(task_history)}")
                            print(f"📁 任务目录: {task_output_dir}")
                            print(f"💾 任务总结保存: {summary_file}")
                            
                        except Exception as e:
                            print(f"⚠️ Failed to learn from task: {e}")
                    
                    # 检查是否还有下一个任务
                    if current_task_index < len(task_queue) - 1:
                        current_task_index += 1
                        print(f"\n🔄 准备执行下一个任务 ({current_task_index + 1}/{len(task_queue)})")
                        print("=" * 60)
                        execute_next_task_from_queue(task_queue, current_task_index, adb_device_id, memory_system, screenshot_wait_time, use_experience_optimization)
                    else:
                        print(f"\n🎉 所有任务已完成！共执行了 {len(task_queue)} 个任务")
                    
                    return
            
            # 处理当前截图
            result = process_screenshot_with_uitars(
                str(screenshot_path), whole_task, step_count, width, height,
                custom_prompt,  # 使用定义的custom_prompt变量，与main函数保持一致
                memory_system=memory_system, task_base_dir=str(task_output_dir), adb_device_id=adb_device_id, use_experience_optimization=use_experience_optimization
            )
            
            if not result:
                print(f"❌ 处理截图失败")
                break
            
            # 执行ADB命令
            adb_success = False
            if result.get("adb_commands"):
                print(f"🔄 执行ADB命令...")
                adb_success = execute_adb_commands(result["adb_commands"], adb_device_id)
                if adb_success:
                    print(f"✅ ADB命令执行成功")
                else:
                    print(f"❌ ADB命令执行失败")
            else:
                print(f"⚠️ 未找到ADB命令")
            
            # 获取下一步截图用于评估
            time.sleep(screenshot_wait_time)  # 等待界面更新
            next_screenshot_filename = f"screenshot_step_{step_count + 1:02d}.png"
            next_screenshot_path = img_folder / next_screenshot_filename
            next_screenshot_cmd = f"adb -s {adb_device_id} exec-out screencap -p > {next_screenshot_path}"
            next_result = subprocess.run(next_screenshot_cmd, shell=True, capture_output=True, text=True)
            
            next_screenshot = str(next_screenshot_path) if next_result.returncode == 0 else str(screenshot_path)
            
            # 判断未加载内容并处理（与main函数保持一致）
            next_screenshot = check_and_handle_unloaded_content(
                current_img_path=str(screenshot_path),
                after_img_path=next_screenshot,
                response_json_path=result.get("analysis_json_path", ""),
                adb_device_id=adb_device_id,
                img_folder=str(img_folder),
                step_count=step_count
            )
            
            # 解析操作结果
            analysis_result = result["analysis_result"]
            parsed_action = analysis_result["parsed_action"]
            
            # 构建步骤数据（与main函数保持一致）
            step_data = {
                "step_id": step_count,
                "timestamp": datetime.now().isoformat(),
                "action": parsed_action.get("action", "unknown"),
                "target_element_description": parsed_action.get("target", "unknown"),
                "thought": parsed_action.get("thought", ""),
                "success": adb_success,  # 临时值，稍后更新
                "reason": "",  # 临时值，稍后更新
                "coordinates": parsed_action.get("coordinates"),
                "absolute_coordinates": analysis_result.get("absolute_coordinates"),
                "error": None if adb_success else "ADB command execution failed",
                "task_id": task_id,
                "app_name": app_name if app_name is not None else "unknown_app",
                "screenshot_before": str(screenshot_path),
                "adb_commands": result["adb_commands"],
                "current_subtask": analysis_result.get("current_subtask", "")  # 添加子任务描述
            }
            
            # 添加到任务历史
            task_history.append(step_data)
            
            # 评估任务成功性（与main函数保持一致）
            try:
                # 需要analysis_json_path参数，从result中获取
                analysis_json_path = result.get("analysis_json_path", "")
                evaluation_result = evaluate_task_success(
                    str(screenshot_path),
                    next_screenshot,
                    analysis_json_path
                )
                
                # 更新步骤数据和任务历史
                step_data["success"] = evaluation_result.get("success", adb_success)
                step_data["reason"] = evaluation_result.get("reason", "")
                task_history[-1] = step_data  # 更新任务历史中的最后一条记录
                
            except Exception as e:
                print(f"⚠️ 评估任务成功性失败: {e}")
                step_data["reason"] = f"评估失败: {str(e)}"
                task_history[-1] = step_data
            
            # 保存步骤数据到文件
            save_step_to_task_storage(task_output_dir, step_data)
            
            # 保存历史记录到history.jsonl（与main函数保持一致）
            try:
                entry = {
                    "task_id": whole_task,
                    "subtask_id": step_data.get("current_subtask", ""),
                    "step_id": step_count,
                    "ui_context": {
                        "subtask": step_data.get("current_subtask", ""),
                        "comprehension": parsed_action.get("thought", ""),
                        "global_task": whole_task
                    },
                    "action": {
                        "interaction_object": parsed_action.get("action", ""),
                        "type": parsed_action.get("action", ""),
                        "coordinates": step_data.get("absolute_coordinates", [])
                    },
                    "before_img": str(screenshot_path),
                    "after_img": next_screenshot,
                    "response_json": "",
                    "success": step_data.get("success"),
                    "reason": step_data.get("reason")
                }
                
                # 确保outputs目录存在
                outputs_dir = os.path.join(task_output_dir, "outputs")
                os.makedirs(outputs_dir, exist_ok=True)
                
                # 保存到history.jsonl
                history_file = os.path.join(outputs_dir, "history.jsonl")
                append_entry_to_jsonl(history_file, entry)
                
                # 写入step_log.jsonl（与main函数保持一致）
                append_step_log(
                    os.path.join(outputs_dir, "step_log.jsonl"),
                    step_count,
                    str(screenshot_path),
                    next_screenshot,
                    step_data.get("reason", ""),
                    {
                        "action_type": parsed_action.get("action"),
                        "thought": parsed_action.get("thought"),
                        "coordinates": step_data.get("absolute_coordinates", [])
                    }
                )
                print(f"✅ 历史记录已保存到: {history_file}")
                
            except Exception as history_error:
                print(f"⚠️ 保存历史记录失败: {history_error}")
            
            # 显示步骤记录
            status = "✅" if step_data["success"] else "❌"
            print(f"{status} Step {step_count}: {step_data['action']} on '{step_data['target_element_description']}'")
            if step_data['thought']:
                print(f"   🧠 推理: {step_data['thought']}")
            if step_data['reason']:
                print(f"   📝 原因: {step_data['reason']}")
            if step_data['coordinates']:
                print(f"   📍 坐标: {step_data['coordinates']}")
            if step_data['error']:
                print(f"   ⚠️ 错误: {step_data['error']}")
            
            step_count += 1
            print(f"准备处理新界面...({screenshot_wait_time}秒)")
            time.sleep(screenshot_wait_time)  # 等待界面更新
            
        except Exception as e:
            print(f"❌ 执行任务时出错: {e}")
            # 如果是API重试失败，标记任务失败
            if "API调用失败" in str(e) or "连接失败" in str(e) or "网络错误" in str(e):
                print(f"🚫 API调用连续失败，标记任务失败")
                mark_task_failed(str(task_output_dir), str(e))
            break
    
    # 任务结束处理 - 添加经验学习和任务总结
    if memory_system and task_history:
        try:
            print("\n🎯 任务执行完成，开始处理经验学习...")
            # 自动判断任务成功
            is_successful = True  # 既然任务完成，默认为成功
            final_evaluation = "自动完成的任务"
            
            if ENABLE_EXPERIENCE_LEARNING:
                experience_id = learn_from_task_with_reflection(
                    memory_system=memory_system,
                    raw_history=task_history,
                    task_description=whole_task,
                    is_successful=is_successful,
                    source_task_id=task_id,
                    app_name=app_name if app_name is not None else "unknown_app"
                )
            else:
                experience_id = "learning_disabled"
            
            # 更新任务信息
            task_info_file = task_output_dir / "task_info.json"
            if task_info_file.exists():
                with open(task_info_file, 'r', encoding='utf-8') as f:
                    task_info = json.load(f)
                task_info["status"] = "completed"
                task_info["completed_at"] = datetime.now().isoformat()
                task_info["is_successful"] = is_successful
                task_info["final_evaluation"] = final_evaluation
                task_info["experience_id"] = experience_id
                task_info["steps_executed"] = len(task_history)
                with open(task_info_file, 'w', encoding='utf-8') as f:
                    json.dump(task_info, f, ensure_ascii=False, indent=2)
            
            # 生成任务总结
            task_summary = {
                "task_id": task_id,
                "global_task": whole_task,
                "app_name": app_name if app_name is not None else "unknown_app",
                "experience_id": experience_id,
                "is_successful": is_successful,
                "final_evaluation": final_evaluation,
                "steps_executed": len(task_history),
                "completed_at": datetime.now().isoformat(),
                "exit_reason": "task_finished"
            }
            
            summary_file = task_output_dir / "task_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(task_summary, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 任务已完成")
            if ENABLE_EXPERIENCE_LEARNING:
                print(f"🧠 Experience learned: {experience_id}")
            else:
                print(f"🚫 经验学习已禁用")
            print(f"📊 Task result: {'Success' if is_successful else 'Failed'}")
            print(f"📝 Steps executed: {len(task_history)}")
            print(f"📁 任务目录: {task_output_dir}")
            print(f"💾 任务总结保存: {summary_file}")
            
        except Exception as e:
            print(f"⚠️ Failed to learn from task: {e}")
    
    # 检查是否还有下一个任务
    if len(task_queue) > 1 and current_task_index < len(task_queue) - 1:
        current_task_index += 1
        print(f"\n🔄 准备执行下一个任务 ({current_task_index + 1}/{len(task_queue)})")
        print("=" * 60)
        
        # 递归调用执行下一个任务
        execute_next_task_from_queue(task_queue, current_task_index, adb_device_id, memory_system, screenshot_wait_time, use_experience_optimization)
    else:
        if len(task_queue) > 1:
            print(f"\n🎉 所有任务已完成！共执行了 {len(task_queue)} 个任务")
        else:
            print(f"\n🎉 任务执行完成！")


if __name__ == "__main__":
    main()