#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試座標：X 固定 115
Y 序列：290 → 510 → 290 → 730 → 290
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎯 測試座標序列：X=115 固定，Y 變化")
print("=" * 70 + "\n")

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\test_x115"
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
    print("🧪 開始測試序列")
    print("=" * 70 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 固定 X=115，Y 序列
    x_coordinate = 115
    y_sequence = [290, 510, 290, 730, 290]

    for index, y in enumerate(y_sequence, 1):
        print(f"\n【測試 {index}/5】")
        print(f"  座標: X={x_coordinate}, Y={y}")

        print(f"  正在點擊 ({x_coordinate}, {y})...")
        device.shell(f"input tap {x_coordinate} {y}")
        time.sleep(2)

        # 關閉可能出現的彈窗
        device.shell("input tap 2880 60")
        time.sleep(0.5)

        # 截圖
        screenshot_name = f"test_{index}_X{x_coordinate}_Y{y}_{timestamp}.png"
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
    print("\n💡 請查看 5 張截圖：")
    print("   1. test_1 - X=115, Y=290")
    print("   2. test_2 - X=115, Y=510")
    print("   3. test_3 - X=115, Y=290")
    print("   4. test_4 - X=115, Y=730")
    print("   5. test_5 - X=115, Y=290")
    print("\n找出哪些 Y 值成功點擊了頁籤！")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
