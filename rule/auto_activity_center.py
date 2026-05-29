#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心自動截圖 - 完整自動化版本
自動點擊活動中心，逐個頁籤截圖所有活動
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp

print("=" * 70)
print("🎮 煤有錢Online 活動中心自動截圖程式")
print("=" * 70)

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\CF"
    PACKAGE_NAME = "com.spinxgames.coalonline"

    # 屏幕分辨率（BlueStacks 虛擬分辨率）
    SCREEN_WIDTH = 2960
    SCREEN_HEIGHT = 1440

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
    time.sleep(5)

    # 第一步：點擊「活動中心」按鈕
    print("\n📌 正在點擊「活動中心」按鈕...")
    # 根據診斷結果，活動中心按鈕座標已確認
    # 座標：X=2500, Y=120
    activity_button_x = 2500
    activity_button_y = 120
    device.shell(f"input tap {activity_button_x} {activity_button_y}")
    time.sleep(2)
    print("✅ 活動中心窗口已打開\n")

    # 第二步：關閉彈窗（如果有）
    print("🗑️  關閉彈窗...")
    close_button_x = 2880
    close_button_y = 60

    # 嘗試多次關閉彈窗
    for i in range(5):
        try:
            device.shell(f"input tap {close_button_x} {close_button_y}")
            time.sleep(0.5)
            print(f"  點擊關閉按鈕 #{i+1}")
        except:
            break

    time.sleep(1)
    print("✅ 彈窗清理完成\n")

    # 第三步：獲取當前時間戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 第四步：截圖主要內容
    print("📸 正在截圖活動中心...")
    screenshot_file = f"activity_center_{timestamp}.png"
    device.shell(f"screencap -p /sdcard/{screenshot_file}")
    time.sleep(1)

    local_path = os.path.join(SCREENSHOT_DIR, screenshot_file)
    device.pull(f"/sdcard/{screenshot_file}", local_path)
    print(f"✅ 主要截圖完成: {screenshot_file}\n")

    # 第五步：自動遍歷頁籤並多次截圖
    print("🔄 正在遍歷所有頁籤...")

    # 左側頁籤區域座標
    tab_list_x_start = 60      # 左側頁籤列表左邊界
    tab_list_x_center = 150    # 頁籤中心 X 坐標
    tab_list_y_start = 250     # 頁籤開始 Y 坐標
    tab_height = 100           # 每個頁籤高度

    # 假設最多有 10 個頁籤（可根據實際調整）
    max_tabs = 10

    for tab_index in range(max_tabs):
        tab_y = tab_list_y_start + (tab_index * tab_height)

        # 檢查是否超出屏幕範圍
        if tab_y > 1200:
            print(f"  達到頁籤列表底部，共遍歷 {tab_index} 個頁籤\n")
            break

        print(f"📍 正在點擊第 {tab_index + 1} 個頁籤...")
        device.shell(f"input tap {tab_list_x_center} {tab_y}")
        time.sleep(1)

        # 關閉可能出現的彈窗
        device.shell(f"input tap {close_button_x} {close_button_y}")
        time.sleep(0.5)

        # 右側內容區域的截圖
        # 計算滾動次數（假設每次需要截 3 次來捕捉所有活動）
        scroll_count = 3

        for scroll_index in range(scroll_count):
            screenshot_name = f"activity_tab_{tab_index + 1}_scroll_{scroll_index + 1}_{timestamp}.png"
            device.shell(f"screencap -p /sdcard/{screenshot_name}")
            time.sleep(0.5)

            local_screenshot = os.path.join(SCREENSHOT_DIR, screenshot_name)
            device.pull(f"/sdcard/{screenshot_name}", local_screenshot)
            print(f"  ✓ 截圖: {screenshot_name}")

            # 向下滾動查看更多活動
            if scroll_index < scroll_count - 1:
                scroll_x = 1500  # 右側內容區域中心
                scroll_y_start = 600
                scroll_y_end = 300
                device.shell(f"input swipe {scroll_x} {scroll_y_start} {scroll_x} {scroll_y_end} 500")
                time.sleep(0.8)

    device.close()

    print("\n" + "=" * 70)
    print("✅ 執行完成！")
    print("=" * 70)
    print(f"✅ 所有截圖已保存到: {SCREENSHOT_DIR}\n")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
