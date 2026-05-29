#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精細 X 軸掃描
測試順序：X=150→250→350→450→550→150→...
Y 固定 250，循環 5 次
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎯 精細 X 軸掃描（X: 150→250→350→450→550）")
print("=" * 70 + "\n")

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\fine_scan_x"
    PACKAGE_NAME = "com.spinxgames.coalonline"
    ACTIVITY_BUTTON_X = 2500
    ACTIVITY_BUTTON_Y = 120

    # 確保資料夾存在
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)

    print("🔌 正在連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("✅ ADB 連接成功！\n")

    print("🎮 正在啟動應用...")
    device.shell(f"am start {PACKAGE_NAME}")
    print("⏳ 等待應用加載...")
    time.sleep(5)

    print("📌 正在進入活動中心...")
    device.shell(f"input tap {ACTIVITY_BUTTON_X} {ACTIVITY_BUTTON_Y}")
    time.sleep(3)

    # 關閉彈窗
    print("🗑️  關閉彈窗...")
    device.shell("input tap 2880 60")
    time.sleep(1)

    print("\n" + "=" * 70)
    print("🧪 開始精細掃描（Y=250，循環 5 次）")
    print("=" * 70 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Y 固定，X 的測試序列
    y_coordinate = 250
    x_sequence = [150, 250, 350, 450, 550]  # 每次 +100
    cycles = 5  # 循環 5 次

    test_count = 0
    for cycle in range(cycles):
        print(f"\n【循環 {cycle + 1}/{cycles}】")

        for x in x_sequence:
            test_count += 1
            print(f"\n  測試 {test_count}: X={x}, Y={y_coordinate}")

            print(f"  正在點擊 ({x}, {y_coordinate})...")
            device.shell(f"input tap {x} {y_coordinate}")
            time.sleep(2)

            # 關閉可能出現的彈窗
            device.shell("input tap 2880 60")
            time.sleep(0.5)

            # 截圖
            screenshot_name = f"fine_scan_{test_count:02d}_X{x}_Y{y_coordinate}_C{cycle+1}_{timestamp}.png"
            screenshot_path = f"/sdcard/{screenshot_name}"

            device.shell(f"screencap -p {screenshot_path}")
            time.sleep(1)

            local_path = os.path.join(SCREENSHOT_DIR, screenshot_name)
            device.pull(screenshot_path, local_path)

            print(f"  ✓ 截圖已保存: {screenshot_name}")

    device.close()

    print("\n" + "=" * 70)
    print("✅ 精細掃描完成！")
    print("=" * 70)
    print(f"\n📁 截圖已保存到: {SCREENSHOT_DIR}")
    print(f"📊 總共 {test_count} 張截圖")
    print("\n💡 請查看所有截圖，找出哪個 X 值成功點擊了頁籤！")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
