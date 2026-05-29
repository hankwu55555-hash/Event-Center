#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X軸掃描 - 找出正確的頁籤 X 座標
固定 Y=280，測試不同的 X 值
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🧭 X 軸掃描 - 尋找正確的頁籤 X 座標")
print("=" * 70 + "\n")

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\scan_x_axis"
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
    print("🧪 開始 X 軸掃描（Y 固定在 280）")
    print("=" * 70 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 固定 Y=280，掃描不同的 X 值
    y_coordinate = 280
    x_values = [30, 50, 75, 100, 120, 150, 180, 200, 250, 300]

    for index, x in enumerate(x_values):
        print(f"\n【X 軸測試 {index + 1}/{len(x_values)}】")
        print(f"  座標: X={x}, Y={y_coordinate}")

        print(f"  正在點擊 ({x}, {y_coordinate})...")
        device.shell(f"input tap {x} {y_coordinate}")
        time.sleep(2)

        # 關閉可能出現的彈窗
        device.shell("input tap 2880 60")
        time.sleep(0.5)

        # 截圖
        screenshot_name = f"x_scan_{index + 1:02d}_X{x}_Y{y_coordinate}_{timestamp}.png"
        screenshot_path = f"/sdcard/{screenshot_name}"

        device.shell(f"screencap -p {screenshot_path}")
        time.sleep(1)

        local_path = os.path.join(SCREENSHOT_DIR, screenshot_name)
        device.pull(screenshot_path, local_path)

        print(f"  ✓ 截圖已保存: {screenshot_name}")

    device.close()

    print("\n" + "=" * 70)
    print("✅ X 軸掃描完成！")
    print("=" * 70)
    print(f"\n📁 截圖已保存到: {SCREENSHOT_DIR}")
    print("\n💡 請查看所有截圖：")
    print("   找出哪個 X 值成功點擊了頁籤（頁籤應該會改變顏色或反應）")
    print("   然後告訴我成功的 X 座標！")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
