#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心完整自動化 - 最終版
使用 OpenCV 模板匹配自動關閉彈窗
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp
from PIL import Image
import cv2
import numpy as np

print("=" * 70)
print("🎮 煤有錢Online 活動中心完整自動化 - 最終版")
print("=" * 70)

def find_and_click_x_button(device, x_template_path, max_attempts=10):
    """
    使用模板匹配找到並點擊 X 按鈕
    返回：是否找到並點擊了 X 按鈕
    """
    try:
        # 檢查模板文件是否存在
        if not os.path.exists(x_template_path):
            print(f"    ⚠️  模板文件不存在：{x_template_path}")
            return False

        # 截圖
        screenshot_path = "/tmp/screen_for_detection.png"
        device.shell(f"screencap -p {screenshot_path}")
        time.sleep(0.5)

        # 拉取截圖
        local_screenshot = "/tmp/current_screen.png"
        device.pull(screenshot_path, local_screenshot)

        # 讀取模板和截圖
        template = cv2.imread(x_template_path)
        screenshot = cv2.imread(local_screenshot)

        if template is None:
            print(f"    ⚠️  無法讀取模板圖像")
            return False

        if screenshot is None:
            print(f"    ⚠️  無法讀取截圖")
            return False

        # 模板匹配（使用多種方法）
        methods = [cv2.TM_CCOEFF, cv2.TM_CCORR, cv2.TM_SQDIFF_NORMED]
        best_method = None
        best_score = None
        best_location = None

        for method in methods:
            result = cv2.matchTemplate(screenshot, template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # 根據方法選擇最高分
            if method in [cv2.TM_CCOEFF, cv2.TM_CCORR]:
                score = max_val
                location = max_loc
            else:
                score = -min_val  # SQDIFF_NORMED 越小越好
                location = min_loc

            if best_score is None or score > best_score:
                best_score = score
                best_location = location
                best_method = method

        # 較寬鬆的閾值
        if best_score < 0.3:
            print(f"    ✓ 未找到 X 按鈕（匹配分數：{best_score:.2f} < 0.3）")
            return False

        # 計算點擊座標
        template_h, template_w = template.shape[:2]
        click_x = best_location[0] + template_w // 2
        click_y = best_location[1] + template_h // 2

        print(f"    🎯 找到 X 按鈕！")
        print(f"       座標：({click_x}, {click_y})")
        print(f"       匹配分數：{best_score:.2f}")
        print(f"    🖱️  點擊 X 按鈕...")

        # 點擊 X 按鈕
        device.shell(f"input tap {click_x} {click_y}")
        time.sleep(1)

        return True

    except Exception as e:
        print(f"    ⚠️  模板匹配失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def close_all_popups(device, x_template_path, max_attempts=10):
    """
    循環關閉所有彈窗
    """
    print("🗑️  開始關閉彈窗...")
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        print(f"\n  【關閉嘗試 {attempts}/{max_attempts}】")

        found_x = find_and_click_x_button(device, x_template_path)

        if not found_x:
            print(f"  ✅ 彈窗全部關閉！\n")
            return True

        time.sleep(1)

    print(f"  ⚠️  達到最大嘗試次數，停止關閉")
    return False

try:
    # 設定
    SCREENSHOT_DIR = r"C:\Users\hankwu\Desktop\screen_shoot\CF"
    X_TEMPLATE_PATH = r"C:\Users\hankwu\Desktop\screen_shoot\CF\basic\x_button.png"
    PACKAGE_NAME = "com.spinxgames.coalonline"

    # 按鈕座標
    CLICK_APP_X = 298
    CLICK_APP_Y = 734
    ACTIVITY_CENTER_X = 2478
    ACTIVITY_CENTER_Y = 66

    # 頁籤座標
    tabs = [
        {"name": "第一個頁籤", "x": 115, "y": 290},
        {"name": "第二個頁籤", "x": 115, "y": 520},
        {"name": "第三個頁籤", "x": 115, "y": 750},
    ]

    # 滾動座標
    SCROLL_X = 2944
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

    print("🎮 【步驟 1】點擊「爆有錢Online」...")
    print(f"   座標：X={CLICK_APP_X}, Y={CLICK_APP_Y}")
    device.shell(f"input tap {CLICK_APP_X} {CLICK_APP_Y}")
    print("   ⏳ 等待應用加載...\n")

    # 增加等待時間確保完全加載（40 秒）
    print("   第 1 階段：等待 15 秒...")
    time.sleep(15)

    print("   第 2 階段：等待 15 秒...")
    time.sleep(15)

    print("   第 3 階段：等待 10 秒...\n")
    time.sleep(10)

    print("✅ 應用加載完成（總共 40 秒）！\n")

    # 關閉彈窗
    close_all_popups(device, X_TEMPLATE_PATH)

    # 進入活動中心（確保不會亂點）
    print("📌 【步驟 2】確認已進入大廳，準備進入活動中心...\n")

    # 等待額外 5 秒確保完全進入
    print("   ⏳ 再等待 5 秒確保完全進入...\n")
    time.sleep(5)

    print(f"   點擊活動中心座標：X={ACTIVITY_CENTER_X}, Y={ACTIVITY_CENTER_Y}\n")
    device.shell(f"input tap {ACTIVITY_CENTER_X} {ACTIVITY_CENTER_Y}")
    time.sleep(3)

    print("   等待活動中心加載...\n")
    time.sleep(3)

    # 再次關閉彈窗
    close_all_popups(device, X_TEMPLATE_PATH)

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
        close_all_popups(device, X_TEMPLATE_PATH)

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

                    if same_size_count >= 1:
                        print(f"    🗑️  【刪除】正在刪除此截圖...")
                        try:
                            os.remove(screenshot_path)
                            print(f"    ✓ 已刪除：{screenshot_filename}")
                        except Exception as e:
                            print(f"    ⚠️  刪除失敗：{e}")

                        print(f"    ✅ 該頁籤已到末尾")
                        print(f"    ✓ 共截圖 {screenshot_count - 1} 張（已刪除相似截圖）")
                        print(f"    🔄 切換到下一個頁籤...\n")
                        time.sleep(1)
                        break
                else:
                    same_size_count = 0
                    print(f"    ✓ 【新內容】文件大小不同")
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
