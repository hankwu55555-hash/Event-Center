#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診斷「活動中心」按鈕座標 - 尋找正確點擊位置
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🔍 診斷「活動中心」按鈕座標")
print("=" * 70 + "\n")

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\diagnose"
    PACKAGE_NAME = "com.spinxgames.coalonline"

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

    # 根據紅框位置，「活動中心」應該在右上角
    # 我們測試多個可能的座標

    print("\n" + "=" * 70)
    print("🧪 開始測試不同座標...")
    print("=" * 70 + "\n")

    # 定義要測試的座標（X, Y）
    # 基於 2960x1440 分辨率，右上角應該是 X: 2600-2900, Y: 80-200
    test_coordinates = [
        (2700, 120, "右上角 - 估算位置1"),
        (2750, 120, "右上角 - 估算位置2"),
        (2800, 120, "右上角 - 估算位置3"),
        (2850, 120, "右上角 - 估算位置4"),
        (2700, 100, "右上角 - 位置靠上1"),
        (2750, 100, "右上角 - 位置靠上2"),
        (2800, 100, "右上角 - 位置靠上3"),
        (2700, 150, "右上角 - 位置靠下1"),
        (2750, 150, "右上角 - 位置靠下2"),
        (2800, 150, "右上角 - 位置靠下3"),
        (2900, 120, "最右邊 - 標準高度"),
        (2650, 120, "稍靠左邊 - 標準高度"),
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for index, (x, y, description) in enumerate(test_coordinates):
        print(f"\n【測試 {index + 1}/{len(test_coordinates)}】")
        print(f"  座標: X={x}, Y={y}")
        print(f"  描述: {description}")

        # 先返回主畫面（按Home鍵或返回）
        if index > 0:
            print("  正在返回主畫面...")
            device.shell("input keyevent 3")  # Home 鍵
            time.sleep(2)

        print(f"  正在點擊座標 ({x}, {y})...")
        device.shell(f"input tap {x} {y}")
        time.sleep(2)

        # 截圖當前狀態
        screenshot_name = f"test_{index + 1:02d}_X{x}_Y{y}_{timestamp}.png"
        screenshot_path = f"/sdcard/{screenshot_name}"

        device.shell(f"screencap -p {screenshot_path}")
        time.sleep(1)

        local_path = os.path.join(SCREENSHOT_DIR, screenshot_name)
        device.pull(screenshot_path, local_path)

        print(f"  ✓ 截圖已保存: {screenshot_name}")
        print(f"  📁 本地路徑: {local_path}")

    device.close()

    print("\n" + "=" * 70)
    print("✅ 診斷完成！")
    print("=" * 70)
    print(f"\n📁 所有截圖已保存到: {SCREENSHOT_DIR}")
    print("\n💡 請查看截圖，找出哪個座標成功進入了活動中心")
    print("   然後告訴我成功的座標 (X, Y) 值")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
