#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""詳細調試版 - 把所有輸出寫到檔案"""

import os
import time
from datetime import datetime

log_file = r"C:\Users\hankwu\Desktop\screen_shoot\debug_log.txt"

with open(log_file, 'w', encoding='utf-8') as f:
    f.write("=" * 70 + "\n")
    f.write("自動截圖 - 詳細調試日誌\n")
    f.write(f"執行時間: {datetime.now()}\n")
    f.write("=" * 70 + "\n\n")

    try:
        f.write("Step 1: 導入 adb_shell 模組...\n")
        from adb_shell.adb_device import AdbDeviceTcp
        f.write("✅ 成功\n\n")

        f.write("Step 2: 連接 127.0.0.1:5555...\n")
        device = AdbDeviceTcp("127.0.0.1", 5555)
        device.connect()
        f.write("✅ 連接成功\n\n")

        f.write("Step 3: 啟動應用 com.spinxgames.coalonline...\n")
        device.shell("am start com.spinxgames.coalonline")
        f.write("✅ 啟動成功\n")
        f.write("   等待 4 秒...\n")
        time.sleep(4)
        f.write("✅ 等待完成\n\n")

        f.write("Step 4: 執行截圖命令...\n")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_file = f"screenshot_{timestamp}.png"
        f.write(f"   截圖文件名: {screenshot_file}\n")

        device.shell(f"screencap -p /sdcard/{screenshot_file}")
        f.write("✅ 截圖命令執行成功\n")
        time.sleep(1)
        f.write("✅ 等待完成\n\n")

        f.write("Step 5: 拉取檔案到本地...\n")
        local_path = r"C:\Users\hankwu\Desktop\screen_shoot\CF" + "\\" + screenshot_file
        f.write(f"   源檔案: /sdcard/{screenshot_file}\n")
        f.write(f"   目標路徑: {local_path}\n")

        device.pull(f"/sdcard/{screenshot_file}", local_path)
        f.write("✅ 檔案拉取成功\n\n")

        # 檢查檔案是否存在
        if os.path.exists(local_path):
            file_size = os.path.getsize(local_path)
            f.write(f"✅ 檔案確認存在\n")
            f.write(f"   檔案大小: {file_size} bytes\n\n")
        else:
            f.write(f"❌ 檔案不存在於: {local_path}\n\n")

        device.close()

        f.write("=" * 70 + "\n")
        f.write("✅ 所有步驟成功完成！\n")
        f.write("=" * 70 + "\n")

    except Exception as e:
        f.write(f"\n❌ 錯誤發生在某個步驟\n")
        f.write(f"錯誤訊息: {str(e)}\n\n")

        import traceback
        f.write("詳細錯誤追蹤:\n")
        f.write(traceback.format_exc())

print("✅ 調試完成！")
print(f"   日誌檔案: {log_file}")
print("\n請打開日誌檔案查看詳細結果")
