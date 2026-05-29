#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試三個頁籤座標
座標：(75, 170)、(75, 280)、(75, 390)
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🧪 直接測試頁籤座標")
print("=" * 70 + "\n")

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\test_tabs"
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
    print("🧪 開始測試三個頁籤座標")
    print("=" * 70 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 要測試的三個座標
    test_coordinates = [
        (75, 170, "第一個頁籤"),
        (75, 280, "第二個頁籤"),
        (75, 390, "第三個頁籤"),
    ]

    for index, (x, y, description) in enumerate(test_coordinates):
        print(f"\n【測試 {index + 1}/3】")
        print(f"  座標: X={x}, Y={y}")
        print(f"  描述: {description}")

        print(f"  正在點擊 ({x}, {y})...")
        device.shell(f"input tap {x} {y}")
        time.sleep(2)

        # 關閉可能出現的彈窗
        device.shell("input tap 2880 60")
        time.sleep(0.5)

        # 截圖
        screenshot_name = f"test_{index + 1}_X{x}_Y{y}_{description}_{timestamp}.png"
        screenshot_path = f"/sdcard/{screenshot_name}"

        device.shell(f"screencap -p {screenshot_path}")
        time.sleep(1)

        local_path = os.path.join(SCREENSHOT_DIR, screenshot_name)
        device.pull(screenshot_path, local_path)

        print(f"  ✓ 截圖已保存: {screenshot_name}")

    device.close()

    print("\n" + "=" * 70)
    print("✅ 測試完成！")
    print("=" * 70)
    print(f"\n📁 截圖已保存到: {SCREENSHOT_DIR}")
    print("\n💡 請查看三張截圖：")
    print("   1. test_1 - 檢查是否點擊了第一個頁籤")
    print("   2. test_2 - 檢查是否點擊了第二個頁籤")
    print("   3. test_3 - 檢查是否點擊了第三個頁籤")
    print("\n然後告訴我結果！")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
