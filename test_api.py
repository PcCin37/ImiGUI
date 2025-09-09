import requests
import json
import base64
from PIL import Image
import io

def test_openai_api():
    """测试OpenAI API的聊天完成功能"""
    
    # API配置
    api_key = "sk-b2np5XZBDSzyoYHm7RUSt6bB4bxbUTR13LGRyFbQVilHXeGu"
    base_url = "https://poloai.top/v1"
    
    # 创建一个简单的测试图片
    img = Image.new('RGB', (100, 100), color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # 测试聊天完成API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "你是一个UI任务分解专家。"
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请描述这个界面并生成一个简单的操作任务。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }
        ],
        "max_tokens": 500
    }
    
    try:
        print("正在测试聊天完成API...")
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=60,
            proxies={'http': None, 'https': None}
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("API调用成功!")
            print(f"响应内容: {result['choices'][0]['message']['content']}")
            return True
        else:
            print(f"API调用失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"API调用异常: {e}")
        return False

if __name__ == "__main__":
    success = test_openai_api()
    if success:
        print("\n✅ API测试通过，可以正常使用")
    else:
        print("\n❌ API测试失败，需要检查配置")