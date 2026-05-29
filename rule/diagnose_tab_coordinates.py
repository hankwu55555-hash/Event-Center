#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診斷左側頁籤點擊座標 - 找出正確的頁籤位置
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🔍 診斷左側頁籤點擊座標")
print("=" * 70 + "\n")

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\diagnose_tabs"
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

    # 關閉可能的彈窗
    print("🗑️  關閉彈窗...")
    device.shell("input tap 2880 60")
    time.sleep(1)

    print("\n" + "=" * 70)
    print("🧪 開始測試左側頁籤座標...")
    print("=" * 70 + "\n")

    # 根據紅框位置，左側頁籤區域大約在 X: 20-200
    # 第一個頁籤應該在 Y: 150-300 之間

    # 我們測試不同的 X 和 Y 座標組合
    test_coordinates = [
        # 不同的 X 坐標，固定 Y
        (100, 180, "X=100, Y=180 - 中心偏左"),
        (120, 180, "X=120, Y=180 - 中心"),
        (150, 180, "X=150, Y=180 - 中心偏右"),
        (80, 180, "X=80, Y=180 - 更靠左"),
        (200, 180, "X=200, Y=180 - 邊界右邊"),

        # 不同的 Y 坐標，固定 X
        (120, 150, "X=120, Y=150 - 靠上"),
        (120, 200, "X=120, Y=200 - 標準"),
        (120, 250, "X=120, Y=250 - 靠下"),
        (120, 300, "X=120, Y=300 - 更靠下"),

        # 第二個頁籤位置測試
        (120, 350, "X=120, Y=350 - 第二個頁籤位置?"),
        (120, 400, "X=120, Y=400 - 第三個頁籤位置?"),
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    success_coordinates = []

    for index, (x, y, description) in enumerate(test_coordinates):
        print(f"\n【測試 {index + 1}/{len(test_coordinates)}】")
        print(f"  座標: X={x}, Y={y}")
        print(f"  描述: {description}")

        print(f"  正在點擊座標 ({x}, {y})...")
        device.shell(f"input tap {x} {y}")
        time.sleep(2)

        # 截圖當前狀態
        screenshot_name = f"tab_test_{index + 1:02d}_X{x}_Y{y}_{timestamp}.png"
        screenshot_path = f"/sdcard/{screenshot_name}"

        device.shell(f"screencap -p {screenshot_path}")
        time.sleep(1)

        local_path = os.path.join(SCREENSHOT_DIR, screenshot_name)
        device.pull(screenshot_path, local_path)

        print(f"  ✓ 截圖已保存: {screenshot_name}")

    device.close()

    print("\n" + "=" * 70)
    print("✅ 診斷完成！")
    print("=" * 70)
    print(f"\n📁 所有截圖已保存到: {SCREENSHOT_DIR}")
    print("\n💡 請查看截圖，找出：")
    print("   1. 第一個頁籤的正確座標")
    print("   2. 頁籤之間的間距")
    print("   然後告訴我結果")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
