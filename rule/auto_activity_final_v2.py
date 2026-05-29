#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心完整自動化 V2
簡化邏輯：發現重複截圖立即切換頁籤
"""

import os
import time
import hashlib
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎮 煤有錢Online 活動中心自動化 V2")
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

    # 滾動座標（右側內容區域）
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
    print("⏳ 等待應用加載 5 秒...")
    time.sleep(5)

    print("📌 正在進入活動中心...")
    device.shell(f"input tap {ACTIVITY_CENTER_X} {ACTIVITY_CENTER_Y}")
    print("⏳ 等待 3 秒...")
    time.sleep(3)

    # 關閉彈窗
    print("🗑️  關閉彈窗...")
    for _ in range(5):
        device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
        time.sleep(0.2)
    time.sleep(1)

    # 獲取時間戳
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
        previous_hash = None

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
            print(f"    ✓ 已保存：{screenshot_filename}")

            # 等待文件完全寫入
            time.sleep(0.5)

            # 計算哈希值
            current_hash = get_file_hash(screenshot_path)

            if current_hash:
                hash_short = current_hash[:12]
                print(f"    📊 哈希值：{hash_short}...")

                # 檢查是否與前一個截圖完全相同
                if previous_hash is not None:
                    if previous_hash == current_hash:
                        print(f"    ⚠️  【重複偵測】此截圖與前一張【完全相同】！")
                        print(f"    ✅ 該頁籤已到末尾")
                        print(f"    ✓ 共截圖 {screenshot_count} 張")
                        print(f"    🔄 切換到下一個頁籤...\n")
                        time.sleep(1)
                        break
                    else:
                        print(f"    ✓ 【新內容】與前一張不同")
                        print(f"       前一張：{previous_hash[:12]}...")
                        print(f"       本張：  {current_hash[:12]}...")
                else:
                    print(f"    ✓ 【第一張截圖】開始追蹤")

                # 更新前一個哈希值
                previous_hash = current_hash
            else:
                print(f"    ⚠️  無法計算哈希值，重試...")
                time.sleep(0.5)
                current_hash = get_file_hash(screenshot_path)
                if current_hash:
                    previous_hash = current_hash
                else:
                    print(f"    ❌ 仍無法計算，停止該頁籤")
                    break

            # 安全上限
            if screenshot_count > 100:
                print(f"    ⚠️  達到安全上限（100 張截圖），停止")
                print(f"    🔄 準備切換到下一個頁籤...\n")
                time.sleep(1)
                break

            # 向上滾動
            print(f"    ⬆️  向上滾動（X={SCROLL_X}, Y={SCROLL_Y_START}→{SCROLL_Y_END})...")
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
