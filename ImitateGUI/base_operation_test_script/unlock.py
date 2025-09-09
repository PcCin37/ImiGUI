import subprocess
import time
import os

# 唤醒设备
def wake_up_device(adb_device_id):
    """通过 ADB 唤醒设备"""
    try:
        # 模拟按下电源键，唤醒设备
        subprocess.run(f"adb -s {adb_device_id} shell input keyevent 26", shell=True, check=True)
        print("设备已唤醒")
    except subprocess.CalledProcessError as e:
        print(f"唤醒设备失败: {e}")

# 滑动解锁设备
def unlock_device(adb_device_id):
    """模拟从屏幕最下方向上滑动解锁设备"""
    try:
        # 获取屏幕分辨率（如果需要可以动态获取）
        # 这里假设屏幕分辨率为 1080x1920，滑动从屏幕底部（y=screen_height-100）到屏幕中央（y=screen_height//2）
        # 根据设备的实际分辨率调整这些值
        screen_width = 1080  # 假设屏幕宽度
        screen_height = 1920  # 假设屏幕高度

        # 起点从屏幕最下方（y=screen_height-100），终点滑动到中间位置（y=screen_height//2）
        start_x = screen_width // 2  # 中心 x 坐标
        start_y = screen_height - 100  # 滑动起点 y 坐标（屏幕底部）
        end_x = start_x  # x 坐标不变
        end_y = screen_height // 2  # 滑动终点 y 坐标（屏幕中部）

        # 模拟滑动解锁
        subprocess.run(f"adb -s {adb_device_id} shell input swipe {start_x} {start_y} {end_x} {end_y} 1500", shell=True, check=True)
        print("设备已解锁")
    except subprocess.CalledProcessError as e:
        print(f"解锁设备失败: {e}")

# 主函数
def main():
    # 设置设备 ID（可以通过 adb devices 获取设备 ID）
    adb_device_id = "9306db29"  # 替换为你的设备 ID

    # 唤醒设备
    wake_up_device(adb_device_id)
    
    # 等待设备唤醒并进入解锁界面
    time.sleep(2)  # 等待 2 秒，确保设备唤醒
    
    # 解锁设备
    unlock_device(adb_device_id)

if __name__ == "__main__":
    main()
