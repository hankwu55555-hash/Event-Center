#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心自動化 - 簡化版
使用文件大小判斷是否為相同截圖
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎮 煤有錢Online 活動中心自動化 - 簡化版")
print("=" * 70)

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\CF"
    PACKAGE_NAME = "com.spinxgames.coalonline"

    # 按鈕座標
    ACTIVITY_CENTER_X = 2500
    ACTIVITY_CENTER_Y = 120
    CLOSE_BUTTON_X = 2880
    CLOSE_BUTTON_Y = 60

    # 頁籤座標
    tabs = [
        {"name": "第一個頁籤", "x": 115, "y": 290},
        {"name": "第二個頁籤", "x": 115, "y": 520},
        {"name": "第三個頁籤", "x": 115, "y": 750},
    ]

    # 滾動座標
    SCROLL_X = 1400
    SCROLL_Y_START = 800
    SCROLL_Y_END = 400
    SCROLL_DURATION = 800

    # 確保資料夾存在
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)

    print("🔌 正在連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("✅ ADB 連接成功！\n")

    print("🎮 正在啟動應用...")
    device.shell(f"am start {PACKAGE_NAME}")
    time.sleep(5)

    print("📌 正在進入活動中心...")
    device.shell(f"input tap {ACTIVITY_CENTER_X} {ACTIVITY_CENTER_Y}")
    time.sleep(3)

    # 關閉彈窗
    print("🗑️  關閉彈窗...")
    for _ in range(5):
        device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
        time.sleep(0.2)
    time.sleep(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 遍歷所有頁籤
    for tab_index, tab in enumerate(tabs):
        print(f"\n" + "=" * 70)
        print(f"📍 【頁籤 {tab_index + 1}】 {tab['name']}")
        print("=" * 70)

        # 點擊頁籤
        print(f"🖱️  點擊頁籤（X={tab['x']}, Y={tab['y']}）...")
        device.shell(f"input tap {tab['x']} {tab['y']}")
        time.sleep(2)

        # 關閉彈窗
        print("🗑️  關閉彈窗...")
        for _ in range(3):
            device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
            time.sleep(0.2)
        time.sleep(1)

        # 該頁籤的截圖序列
        screenshot_count = 0
        previous_size = None
        same_size_count = 0

        while True:
            screenshot_count += 1
            print(f"\n  【截圖 {screenshot_count}】")

            # 構建截圖文件名
            screenshot_filename = f"tab{tab_index + 1}_activity{screenshot_count}_{timestamp}.png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
            sdcard_path = f"/sdcard/{screenshot_filename}"

            # 截圖
            print(f"    📸 正在截圖...")
            device.shell(f"screencap -p {sdcard_path}")
            time.sleep(0.5)

            # 拉取文件
            device.pull(sdcard_path, screenshot_path)
            time.sleep(0.3)

            # 獲取文件大小
            try:
                file_size = os.path.getsize(screenshot_path)
                print(f"    ✓ 已保存：{screenshot_filename}")
                print(f"    📊 文件大小：{file_size} bytes")
            except Exception as e:
                print(f"    ⚠️  無法獲取文件大小：{e}")
                break

            # 檢查文件大小是否與前一個相同
            if previous_size is not None:
                if previous_size == file_size:
                    same_size_count += 1
                    print(f"    ⚠️  【相同大小】與前一張相同！（連續 {same_size_count} 次）")

                    # 連續 2 次相同大小 = 已到末尾
                    if same_size_count >= 2:
                        print(f"    ✅ 該頁籤已到末尾")
                        print(f"    ✓ 共截圖 {screenshot_count} 張")
                        print(f"    🔄 切換到下一個頁籤...\n")
                        time.sleep(1)
                        break
                else:
                    same_size_count = 0
                    size_diff = file_size - previous_size
                    print(f"    ✓ 【新內容】文件大小不同")
                    print(f"       前一張：{previous_size} bytes")
                    print(f"       本張：  {file_size} bytes（差異：{size_diff:+d} bytes）")
            else:
                print(f"    ✓ 【第一張截圖】開始追蹤")

            # 更新前一個大小
            previous_size = file_size

            # 安全上限
            if screenshot_count > 100:
                print(f"    ⚠️  達到安全上限，停止")
                break

            # 向上滾動
            print(f"    ⬆️  向上滾動...")
            device.shell(f"input swipe {SCROLL_X} {SCROLL_Y_START} {SCROLL_X} {SCROLL_Y_END} {SCROLL_DURATION}")
            time.sleep(1)

    device.close()

    print("\n" + "=" * 70)
    print("✅ 全部完成！")
    print("=" * 70)
    print(f"✅ 所有截圖已保存到：{SCREENSHOT_DIR}\n")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
