#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 每日自動截圖 - 最終可用版本
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎮 煤有錢Online 自動截圖程式")
print("=" * 70)

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\CF"
    PACKAGE_NAME = "com.spinxgames.coalonline"

    # 確保資料夾存在
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
        print(f"✅ 已建立資料夾: {SCREENSHOT_DIR}\n")

    print("🔌 正在連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("✅ ADB 連接成功！\n")

    print("🎮 正在啟動應用...")
    device.shell(f"am start {PACKAGE_NAME}")
    print("⏳ 等待應用加載...")
    time.sleep(4)

    # 截圖
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_file = f"screenshot_{timestamp}.png"
    local_path = os.path.join(SCREENSHOT_DIR, screenshot_file)

    print(f"\n📸 正在截圖...")
    device.shell(f"screencap -p /sdcard/{screenshot_file}")
    time.sleep(1)

    # 拉取檔案
    print("📥 正在拉取檔案...")
    device.pull(f"/sdcard/{screenshot_file}", local_path)

    print(f"\n✅ 截圖已成功保存！")
    print(f"   路徑: {local_path}\n")

    device.close()

    print("=" * 70)
    print("✅ 執行完成！")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
