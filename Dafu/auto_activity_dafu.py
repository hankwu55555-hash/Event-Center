#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大福Online 活動中心自動化 - 像素比較版
使用 PIL 比較圖像像素，判斷截圖是否相同
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp
from PIL import Image
import cv2
import numpy as np

print("=" * 70)
print("🎮 大福Online 活動中心自動化 - 像素比較版")
print("=" * 70)

def compare_images(img_path1, img_path2):
    """
    比較兩張圖像是否相同
    返回：(是否相同, 相似度百分比)
    """
    try:
        img1 = Image.open(img_path1)
        img2 = Image.open(img_path2)

        if img1.size != img2.size:
            return False, 0

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        if len(pixels1) != len(pixels2):
            return False, 0

        same_pixels = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 == p2)
        similarity = (same_pixels / len(pixels1)) * 100
        is_same = similarity > 99.0

        return is_same, similarity

    except Exception as e:
        print(f"    ⚠️  比較失敗：{e}")
        return False, 0

try:
    # ── 設定 ──────────────────────────────────────────────────────────────
    today = datetime.now().strftime("%Y%m%d")
    SCREENSHOT_DIR = os.path.join(r"C:\Users\hankwu\OneDrive - International Games System\Event_Center\Dafu", today)
    PACKAGE_NAME = "com.grandegames.slots.dafu.casino"

    # APP 在模擬器大廳的座標
    APP_TAP_X = 785
    APP_TAP_Y = 747

    # 活動中心按鈕座標
    ACTIVITY_CENTER_X = 2590
    ACTIVITY_CENTER_Y = 55

    # ── TODO：X 彈窗相關（目前略過） ─────────────────────────────────────
    # X_BUTTON_REF  = r"TODO: X按鈕參考圖路徑"
    # ROI_X1, ROI_Y1 = TODO, TODO
    # ROI_X2, ROI_Y2 = TODO, TODO
    # CLOSE_BUTTON_X = TODO
    # CLOSE_BUTTON_Y = TODO

    # 頁籤座標（共 4 個）
    tabs = [
        {"name": "頁籤1", "x": 315, "y": 400},
        {"name": "頁籤2", "x": 315, "y": 613},
        {"name": "頁籤3", "x": 315, "y": 835},
        {"name": "頁籤4", "x": 315, "y": 1055},
    ]

    # 活動項目固定點擊座標（共 10 個）
    ACTIVITY_ITEMS = [
        {"name": "活動1",  "x": 587, "y": 395},
        {"name": "活動2",  "x": 587, "y": 575},
        {"name": "活動3",  "x": 587, "y": 780},
        {"name": "活動4",  "x": 587, "y": 960},
        {"name": "活動5",  "x": 587, "y": 960},
        {"name": "活動6",  "x": 587, "y": 960},
        {"name": "活動7",  "x": 587, "y": 960},
        {"name": "活動8",  "x": 587, "y": 960},
        {"name": "活動9",  "x": 587, "y": 1098},
        {"name": "活動10", "x": 587, "y": 1300},
    ]
    # 第 10 張之後持續點擊的座標
    REPEAT_TAP_X = 587
    REPEAT_TAP_Y = 1300

    # 確保資料夾存在
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)

    print("🔌 正在連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("✅ ADB 連接成功！\n")

    print("🏠 【步驟 1】回到模擬器大廳...")
    device.shell("input keyevent 3")
    time.sleep(2)

    print("🧹 【步驟 2】強制關閉所有第三方應用...")
    pkg_output = device.shell("pm list packages -3")
    packages = [line.replace("package:", "").strip() for line in pkg_output.splitlines() if line.strip()]
    print(f"   📦 共發現 {len(packages)} 個第三方應用，逐一關閉中...")
    for pkg in packages:
        device.shell(f"am force-stop {pkg}")
    time.sleep(1)
    device.shell("input keyevent 3")
    time.sleep(1)
    print("   ✅ 所有第三方應用已強制關閉")

    print("🎮 【步驟 3】點擊「大福Online」APP...")
    print(f"   座標：X={APP_TAP_X}, Y={APP_TAP_Y}")
    device.shell(f"input tap {APP_TAP_X} {APP_TAP_Y}")
    print("   ⏳ 等待應用加載...")
    time.sleep(40)

    # ── TODO：步驟 4 偵測並關閉 X 彈窗（待補參數後啟用） ─────────────────
    print("⏭️  【步驟 4】X 彈窗偵測略過（參數待補）")

    print("📌 正在進入活動中心...")
    device.shell(f"input tap {ACTIVITY_CENTER_X} {ACTIVITY_CENTER_Y}")
    time.sleep(3)

    # ── TODO：關閉彈窗（待補參數後啟用） ─────────────────────────────────
    # print("🗑️  關閉彈窗...")
    # for _ in range(5):
    #     device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
    #     time.sleep(0.2)
    # time.sleep(1)

    # 遍歷所有頁籤
    for tab_index, tab in enumerate(tabs):
        print(f"\n" + "=" * 70)
        print(f"📍 【頁籤 {tab_index + 1}】 {tab['name']}")
        print("=" * 70)

        print(f"🖱️  點擊頁籤（X={tab['x']}, Y={tab['y']}）...")
        device.shell(f"input tap {tab['x']} {tab['y']}")
        time.sleep(2)

        # 【階段一】依序點擊 10 個固定座標並截圖
        previous_path = None
        reached_end = False

        for item_index, item in enumerate(ACTIVITY_ITEMS):
            screenshot_count = item_index + 1
            print(f"\n  【截圖 {screenshot_count}】點擊 {item['name']}（X={item['x']}, Y={item['y']}）")

            device.shell(f"input tap {item['x']} {item['y']}")
            time.sleep(1)

            screenshot_filename = f"tab{tab_index + 1}_{screenshot_count}.png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
            sdcard_path = f"/sdcard/{screenshot_filename}"

            print(f"    📸 正在截圖...")
            device.shell(f"screencap -p {sdcard_path}")
            time.sleep(0.5)
            device.pull(sdcard_path, screenshot_path)
            time.sleep(0.3)

            if previous_path is not None:
                is_same, similarity = compare_images(previous_path, screenshot_path)
                print(f"    🖼️  與上一張相似度：{similarity:.2f}%")
                if similarity > 70.0:
                    print(f"    ⚠️  畫面相同（{similarity:.2f}% > 70%），刪除並切換下一頁籤")
                    try:
                        os.remove(screenshot_path)
                    except:
                        pass
                    reached_end = True
                    break
                else:
                    print(f"    ✓ 新內容，已保存：{screenshot_filename}")
            else:
                print(f"    ✓ 【第一張】已保存：{screenshot_filename}")

            previous_path = screenshot_path

        if reached_end:
            print(f"\n  ✅ 頁籤 {tab_index + 1} 完成（階段一偵測到末尾）")
            continue

        # 【階段二】從第 11 張起，持續點擊 Y=1300，直到畫面與上一張相同
        print(f"\n  🔁 開始持續點擊 X={REPEAT_TAP_X}, Y={REPEAT_TAP_Y}，直到畫面無新內容...")
        previous_path = screenshot_path
        screenshot_count = len(ACTIVITY_ITEMS)

        while True:
            device.shell(f"input tap {REPEAT_TAP_X} {REPEAT_TAP_Y}")
            time.sleep(1)

            screenshot_count += 1
            screenshot_filename = f"tab{tab_index + 1}_{screenshot_count}.png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
            sdcard_path = f"/sdcard/{screenshot_filename}"

            print(f"\n  【截圖 {screenshot_count}】")
            print(f"    📸 正在截圖...")
            device.shell(f"screencap -p {sdcard_path}")
            time.sleep(0.5)
            device.pull(sdcard_path, screenshot_path)
            time.sleep(0.3)

            is_same, similarity = compare_images(previous_path, screenshot_path)
            print(f"    🖼️  與上一張相似度：{similarity:.2f}%")

            if similarity > 70.0:
                print(f"    ⚠️  畫面相同（{similarity:.2f}% > 70%），刪除此張並切換下一頁籤")
                try:
                    os.remove(screenshot_path)
                except:
                    pass
                break
            else:
                print(f"    ✓ 新內容，已保存：{screenshot_filename}")
                previous_path = screenshot_path

            if screenshot_count > 100:
                print(f"    ⚠️  達到安全上限，停止")
                break

        print(f"\n  ✅ 頁籤 {tab_index + 1} 完成，共截圖 {screenshot_count - 1} 張")

    device.close()

    print("\n" + "=" * 70)
    print("✅ 全部完成！")
    print("=" * 70)
    print(f"✅ 所有截圖已保存到：{SCREENSHOT_DIR}\n")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n💡 提示：如果出現 PIL 錯誤，請先執行：")
print("   pip install Pillow")
