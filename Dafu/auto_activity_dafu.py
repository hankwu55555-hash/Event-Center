#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大福Online 活動中心自動化 - 像素比較版
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp
from PIL import Image

print("=" * 70)
print("大福Online 活動中心自動化 - 像素比較版")
print("=" * 70)

JPEG_QUALITY = 10

def png_to_jpg(png_path, jpg_path, quality=JPEG_QUALITY):
    img = Image.open(png_path).convert("RGB")
    img.save(jpg_path, "JPEG", quality=quality)
    try:
        os.remove(png_path)
    except:
        pass

def compare_images(img_path1, img_path2):
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
        return similarity > 99.0, similarity
    except Exception as e:
        print(f"    比較失敗：{e}")
        return False, 0

try:
    today = datetime.now().strftime("%Y%m%d")
    SCREENSHOT_DIR = os.path.join(r"C:\Users\hankwu\Desktop\Event_Center\Dafu", today)
    PACKAGE_NAME = "com.grandegames.slots.dafu.casino"
    APP_TAP_X = 785
    APP_TAP_Y = 747
    ACTIVITY_CENTER_X = 2590
    ACTIVITY_CENTER_Y = 55

    tabs = [
        {"name": "頁籤1", "x": 315, "y": 400},
        {"name": "頁籤2", "x": 315, "y": 613},
        {"name": "頁籤3", "x": 315, "y": 835},
        {"name": "頁籤4", "x": 315, "y": 1055},
    ]

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
    REPEAT_TAP_X = 587
    REPEAT_TAP_Y = 1300

    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)

    print("正在連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("ADB 連接成功！\n")

    # print("【步驟 1】回到模擬器大廳...")
    # device.shell("input keyevent 3")
    # time.sleep(2)

    # print("【步驟 2】強制關閉所有第三方應用...")
    # pkg_output = device.shell("pm list packages -3")
    # packages = [line.replace("package:", "").strip() for line in pkg_output.splitlines() if line.strip()]
    # print(f"   共發現 {len(packages)} 個第三方應用，逐一關閉中...")
    # for pkg in packages:
    #     device.shell(f"am force-stop {pkg}")
    # time.sleep(1)
    # device.shell("input keyevent 3")
    # time.sleep(1)
    # print("   所有第三方應用已強制關閉")

    # print("【步驟 3】點擊大福Online...")
    # device.shell(f"input tap {APP_TAP_X} {APP_TAP_Y}")
    # print("   等待應用加載（40秒）...")
    # time.sleep(40)

    # print("【步驟 4】X 彈窗偵測略過（參數待補）")

    print("正在進入活動中心...")
    device.shell(f"input tap {ACTIVITY_CENTER_X} {ACTIVITY_CENTER_Y}")
    time.sleep(3)

    for tab_index, tab in enumerate(tabs):
        print("\n" + "=" * 70)
        print(f"【頁籤 {tab_index + 1}】 {tab['name']}")
        print("=" * 70)

        device.shell(f"input tap {tab['x']} {tab['y']}")
        time.sleep(2)

        previous_path = None
        reached_end = False

        for item_index, item in enumerate(ACTIVITY_ITEMS):
            screenshot_count = item_index + 1
            print(f"\n  【截圖 {screenshot_count}】{item['name']} (X={item['x']}, Y={item['y']})")
            device.shell(f"input tap {item['x']} {item['y']}")
            time.sleep(1)

            base = f"tab{tab_index + 1}_{screenshot_count}"
            screenshot_path = os.path.join(SCREENSHOT_DIR, base + ".jpg")
            tmp_png = os.path.join(SCREENSHOT_DIR, base + "_tmp.png")
            sdcard_path = f"/sdcard/{base}_tmp.png"

            device.shell(f"screencap -p {sdcard_path}")
            time.sleep(0.5)
            device.pull(sdcard_path, tmp_png)
            time.sleep(0.3)
            png_to_jpg(tmp_png, screenshot_path)

            if previous_path is not None:
                is_same, similarity = compare_images(previous_path, screenshot_path)
                print(f"    與上一張相似度：{similarity:.2f}%")
                if similarity > 90.0:
                    print(f"    畫面相同，刪除並切換下一頁籤")
                    try:
                        os.remove(screenshot_path)
                    except:
                        pass
                    reached_end = True
                    break
                else:
                    print(f"    新內容，已保存：{base}.jpg")
            else:
                print(f"    第一張，已保存：{base}.jpg")

            previous_path = screenshot_path

        if reached_end:
            print(f"\n  頁籤 {tab_index + 1} 完成（階段一偵測到末尾）")
            continue

        print(f"\n  持續點擊 X={REPEAT_TAP_X}, Y={REPEAT_TAP_Y}，直到畫面無新內容...")
        previous_path = screenshot_path
        screenshot_count = len(ACTIVITY_ITEMS)

        while True:
            device.shell(f"input tap {REPEAT_TAP_X} {REPEAT_TAP_Y}")
            time.sleep(1)
            screenshot_count += 1

            base = f"tab{tab_index + 1}_{screenshot_count}"
            screenshot_path = os.path.join(SCREENSHOT_DIR, base + ".jpg")
            tmp_png = os.path.join(SCREENSHOT_DIR, base + "_tmp.png")
            sdcard_path = f"/sdcard/{base}_tmp.png"

            print(f"\n  【截圖 {screenshot_count}】")
            device.shell(f"screencap -p {sdcard_path}")
            time.sleep(0.5)
            device.pull(sdcard_path, tmp_png)
            time.sleep(0.3)
            png_to_jpg(tmp_png, screenshot_path)

            is_same, similarity = compare_images(previous_path, screenshot_path)
            print(f"    與上一張相似度：{similarity:.2f}%")

            if similarity > 90.0:
                print(f"    畫面相同，刪除並切換下一頁籤")
                try:
                    os.remove(screenshot_path)
                except:
                    pass
                break
            else:
                print(f"    新內容，已保存：{base}.jpg")
                previous_path = screenshot_path

            if screenshot_count > 100:
                print(f"    達到安全上限，停止")
                break

        print(f"\n  頁籤 {tab_index + 1} 完成，共截圖 {screenshot_count - 1} 張")

    device.close()
    print("\n" + "=" * 70)
    print("全部完成！")
    print("=" * 70)
    print(f"所有截圖已保存到：{SCREENSHOT_DIR}\n")

except Exception as e:
    print(f"\n錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n提示：如果出現 PIL 錯誤，請先執行：pip install Pillow")
