import requests
import ssl
import socket
import urllib3
from urllib3.exceptions import InsecureRequestWarning

def debug_connection():
    """调试网络连接问题"""
    
    print("=== 网络连接调试信息 ===")
    
    # 1. 检查SSL配置
    print(f"SSL版本: {ssl.OPENSSL_VERSION}")
    print(f"SSL默认上下文: {ssl.create_default_context()}")
    print(f"SSL支持的协议: {ssl.PROTOCOL_TLS}")
    
    # 2. 检查urllib3版本和配置
    print(f"urllib3版本: {urllib3.__version__}")
    print(f"requests版本: {requests.__version__}")
    
    # 3. 测试基本的HTTPS连接
    try:
        print("\n=== 测试基本HTTPS连接 ===")
        response = requests.get('https://httpbin.org/get', timeout=10)
        print(f"httpbin.org连接成功: {response.status_code}")
    except Exception as e:
        print(f"httpbin.org连接失败: {e}")
    
    # 4. 测试目标服务器的SSL握手
    try:
        print("\n=== 测试SSL握手 ===")
        context = ssl.create_default_context()
        with socket.create_connection(('poloai.top', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='poloai.top') as ssock:
                print(f"SSL握手成功")
                print(f"SSL版本: {ssock.version()}")
                print(f"证书信息: {ssock.getpeercert()['subject']}")
    except Exception as e:
        print(f"SSL握手失败: {e}")
    
    # 5. 测试不同的请求方式
    print("\n=== 测试不同请求方式 ===")
    
    # 5.1 使用session
    try:
        session = requests.Session()
        session.proxies = {'http': None, 'https': None}
        response = session.get('https://poloai.top/v1/models', 
                             headers={'Authorization': 'Bearer sk-b2np5XZBDSzyoYHm7RUSt6bB4bxbUTR13LGRyFbQVilHXeGu'},
                             timeout=30)
        print(f"Session请求成功: {response.status_code}")
    except Exception as e:
        print(f"Session请求失败: {e}")
    
    # 5.2 禁用SSL验证测试
    try:
        urllib3.disable_warnings(InsecureRequestWarning)
        response = requests.get('https://poloai.top/v1/models',
                              headers={'Authorization': 'Bearer sk-b2np5XZBDSzyoYHm7RUSt6bB4bxbUTR13LGRyFbQVilHXeGu'},
                              verify=False,
                              timeout=30,
                              proxies={'http': None, 'https': None})
        print(f"禁用SSL验证请求成功: {response.status_code}")
    except Exception as e:
        print(f"禁用SSL验证请求失败: {e}")
    
    # 6. 检查网络适配器和路由
    print("\n=== 网络配置信息 ===")
    try:
        import subprocess
        result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True, shell=True)
        lines = result.stdout.split('\n')
        for line in lines[:20]:  # 只显示前20行
            if 'DNS' in line or 'Gateway' in line or 'DHCP' in line:
                print(line.strip())
    except Exception as e:
        print(f"获取网络配置失败: {e}")

if __name__ == "__main__":
    debug_connection()