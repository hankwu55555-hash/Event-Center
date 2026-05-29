#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""簡單測試 - 直接顯示結果"""

import os
import time
from datetime import datetime

print("=" * 70)
print("🎮 自動截圖 - 簡單測試")
print("=" * 70 + "\n")

try:
    print("Step 1: 導入 adb_shell...")
    from adb_shell.adb_device import AdbDeviceTcp
    print("✅ 成功\n")

    print("Step 2: 連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("✅ 連接成功\n")

    print("Step 3: 啟動應用...")
    device.shell("am start com.spinxgames.coalonline")
    time.sleep(4)
    print("✅ 應用已啟動\n")

    print("Step 4: 執行截圖...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_file = f"screenshot_{timestamp}.png"
    device.shell(f"screencap -p /sdcard/{screenshot_file}")
    time.sleep(1)
    print(f"✅ 截圖成功: {screenshot_file}\n")

    print("Step 5: 拉取檔案...")
    local_path = r"C:\Users\hankwu\Desktop\screen_shoot\CF" + "\\" + screenshot_file
    device.pull(f"/sdcard/{screenshot_file}", local_path)
    print(f"✅ 檔案已拉取: {local_path}\n")

    # 檢查檔案
    if os.path.exists(local_path):
        file_size = os.path.getsize(local_path)
        print(f"✅ 檔案確認存在")
        print(f"   檔案大小: {file_size} bytes\n")
    else:
        print(f"❌ 檔案不存在\n")

    device.close()
    print("=" * 70)
    print("✅ 全部成功！")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 錯誤: {e}\n")
    import traceback
    traceback.print_exc()

print("\n按 Enter 鍵結束...")
input()
