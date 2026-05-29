#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心完整自動化
- 自動點擊所有頁籤
- 逐個截圖每個活動
- 檢測重複截圖判定換頁籤
"""

import os
import time
import hashlib
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎮 煤有錢Online 活動中心完整自動化")
print("=" * 70)

def get_file_hash(filepath):
    """計算文件的 MD5 哈希值"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None

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

    # 內容區域座標（右側活動內容區域 - 根據紅框位置）
    SCROLL_X = 1400  # 滾動區域 X 中心
    SCROLL_Y_START = 800  # 滾動開始位置（較低）
    SCROLL_Y_END = 400    # 滾動結束位置（較高）- 向上滾動
    SCROLL_DURATION = 800  # 滾動持續時間（毫秒）

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
    device.shell(f"input tap {ACTIVITY_CENTER_X} {ACTIVITY_CENTER_Y}")
    time.sleep(3)

    # 關閉彈窗
    print("🗑️  關閉彈窗...")
    for _ in range(3):
        device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
        time.sleep(0.3)
    time.sleep(1)

    # 獲取時間戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 遍歷所有頁籤
    for tab_index, tab in enumerate(tabs):
        print(f"\n" + "=" * 70)
        print(f"📍 正在處理：{tab['name']}")
        print("=" * 70)

        # 點擊頁籤
        print(f"  點擊頁籤（X={tab['x']}, Y={tab['y']}）...")
        device.shell(f"input tap {tab['x']} {tab['y']}")
        time.sleep(2)

        # 關閉可能的彈窗
        for _ in range(2):
            device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
            time.sleep(0.3)
        time.sleep(1)

        # 該頁籤的截圖序列
        screenshot_count = 0
        previous_hash = None
        consecutive_duplicates = 0

        while True:
            screenshot_count += 1
            print(f"\n  【截圖 {screenshot_count}】")

            # 構建截圖文件名
            screenshot_filename = f"activity_tab{tab_index + 1}_activity{screenshot_count}_{timestamp}.png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
            sdcard_path = f"/sdcard/{screenshot_filename}"

            # 截圖
            print(f"    正在截圖...")
            device.shell(f"screencap -p {sdcard_path}")
            time.sleep(0.5)

            # 拉取文件
            device.pull(sdcard_path, screenshot_path)
            print(f"    ✓ 截圖已保存：{screenshot_filename}")

            # 計算哈希值
            current_hash = get_file_hash(screenshot_path)
            if current_hash:
                print(f"    📊 哈希值：{current_hash[:16]}...")
            else:
                print(f"    ⚠️  無法計算哈希值")

            # 檢查是否與前一個截圖完全相同
            if previous_hash is not None:
                if previous_hash == current_hash:
                    consecutive_duplicates += 1
                    print(f"    ⚠️  完全相同的截圖！（連續 {consecutive_duplicates} 次）")

                    # 連續 2 次相同 = 已到末尾
                    if consecutive_duplicates >= 2:
                        print(f"    ✅ 連續 2 次完全相同，該頁籤已到末尾")
                        print(f"    🔄 準備切換頁籤...")
                        break
                else:
                    consecutive_duplicates = 0
                    print(f"    ✓ 新內容（與前一張不同）")
            else:
                print(f"    ✓ 第一張截圖")

            # 更新前一個哈希值
            previous_hash = current_hash

            # 安全上限：防止無限循環
            if screenshot_count > 50:
                print(f"    ⚠️  達到安全上限（50 張截圖），停止該頁籤")
                break

            # 向上滾動（從下往上滑動）
            print(f"    ⬆️  向上滾動...")
            device.shell(f"input swipe {SCROLL_X} {SCROLL_Y_START} {SCROLL_X} {SCROLL_Y_END} {SCROLL_DURATION}")
            time.sleep(1.5)

        print(f"\n  ✅ {tab['name']} 完成！共截圖 {screenshot_count} 張")

    device.close()

    print("\n" + "=" * 70)
    print("✅ 全部完成！")
    print("=" * 70)
    print(f"✅ 所有截圖已保存到：{SCREENSHOT_DIR}\n")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
