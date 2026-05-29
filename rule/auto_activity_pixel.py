#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心自動化 - 像素比較版
使用 PIL 比較圖像像素，判斷截圖是否相同
"""

import os
import time
from datetime import datetime
from adb_shell.adb_device import AdbDeviceTcp
from PIL import Image
import hashlib
import cv2
import numpy as np

print("=" * 70)
print("🎮 煤有錢Online 活動中心自動化 - 像素比較版")
print("=" * 70)

def compare_images(img_path1, img_path2):
    """
    比較兩張圖像是否相同
    返回：(是否相同, 相似度百分比)
    """
    try:
        img1 = Image.open(img_path1)
        img2 = Image.open(img_path2)

        # 確保尺寸相同
        if img1.size != img2.size:
            return False, 0

        # 比較像素
        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        if len(pixels1) != len(pixels2):
            return False, 0

        # 計算相同像素數
        same_pixels = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 == p2)
        similarity = (same_pixels / len(pixels1)) * 100

        # 如果相似度大於 99%，認為相同
        is_same = similarity > 99.0

        return is_same, similarity

    except Exception as e:
        print(f"    ⚠️  比較失敗：{e}")
        return False, 0

try:
    # 設定
    today = datetime.now().strftime("%Y%m%d")
    SCREENSHOT_DIR = os.path.join(r"C:\Users\hankwu\Desktop\screen_shoot\CF", today)
    PACKAGE_NAME = "com.spinxgames.coalonline"
    X_BUTTON_REF = r"C:\Users\hankwu\Desktop\screen_shoot\CF\basic\x_button.png"

    # 按鈕座標
    ACTIVITY_CENTER_X = 2478  # 精準座標
    ACTIVITY_CENTER_Y = 66    # 精準座標
    CLOSE_BUTTON_X = 2880
    CLOSE_BUTTON_Y = 60

    # 頁籤座標
    tabs = [
        {"name": "第一個頁籤", "x": 115, "y": 290},
        {"name": "第二個頁籤", "x": 115, "y": 520},
        {"name": "第三個頁籤", "x": 115, "y": 750},
        {"name": "第四個頁籤", "x": 120, "y": 975},
    ]

    # 活動項目固定點擊座標（前 6 個）
    ACTIVITY_ITEMS = [
        {"name": "活動1", "x": 387, "y": 290},
        {"name": "活動2", "x": 387, "y": 520},
        {"name": "活動3", "x": 387, "y": 740},
        {"name": "活動4", "x": 387, "y": 960},
        {"name": "活動5", "x": 387, "y": 1200},
        {"name": "活動6", "x": 387, "y": 1300},
    ]
    # 第 6 張之後持續點擊的座標
    REPEAT_TAP_X = 387
    REPEAT_TAP_Y = 1300

    # 確保資料夾存在
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)

    print("🔌 正在連接 127.0.0.1:5555...")
    device = AdbDeviceTcp("127.0.0.1", 5555)
    device.connect()
    print("✅ ADB 連接成功！\n")

    print("🏠 【步驟 1】回到模擬器大廳...")
    device.shell("input keyevent 3")  # Home 鍵回到大廳
    time.sleep(2)

    print("🧹 【步驟 2】強制關閉所有第三方應用...")
    # 取得所有使用者安裝的 APP 清單，逐一 force-stop
    pkg_output = device.shell("pm list packages -3")
    packages = [line.replace("package:", "").strip() for line in pkg_output.splitlines() if line.strip()]
    print(f"   📦 共發現 {len(packages)} 個第三方應用，逐一關閉中...")
    for pkg in packages:
        device.shell(f"am force-stop {pkg}")
    time.sleep(1)
    device.shell("input keyevent 3")   # 回到大廳
    time.sleep(1)
    print("   ✅ 所有第三方應用已強制關閉")

    print("🎮 【步驟 3】點擊「爆有錢Online」APP...")
    print("   座標：X=325, Y=763")
    device.shell("input tap 325 763")
    print("   ⏳ 等待應用加載...")
    time.sleep(40)

    print("🔍 【步驟 4】偵測並關閉 X 彈窗...")
    # 載入含透明度的模板（UNCHANGED 保留 Alpha 通道）
    template_raw = cv2.imread(X_BUTTON_REF, cv2.IMREAD_UNCHANGED)
    if template_raw.shape[2] == 4:
        template_gray = cv2.cvtColor(template_raw[:, :, :3], cv2.COLOR_BGR2GRAY)
        template_mask = template_raw[:, :, 3]   # Alpha 通道作為遮罩
        print("   ✅ 使用 Alpha 遮罩精準比對 X 形狀")
    else:
        template_gray = cv2.cvtColor(template_raw, cv2.COLOR_BGR2GRAY)
        template_mask = None
        print("   ⚠️  無 Alpha 通道，使用一般比對")
    th, tw = template_gray.shape[:2]

    def take_screenshot(tag):
        sdcard = f"/sdcard/temp_{tag}.png"
        local = os.path.join(SCREENSHOT_DIR, f"temp_{tag}.png")
        device.shell(f"screencap -p {sdcard}")
        time.sleep(0.5)
        device.pull(sdcard, local)
        time.sleep(0.3)
        return local

    # X 按鈕搜尋範圍（固定座標）
    ROI_X1, ROI_Y1 = 2531, 33
    ROI_X2, ROI_Y2 = 2944, 230

    def find_x_button(local_path):
        screenshot = cv2.imread(local_path)
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        roi = gray[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]
        if template_mask is not None:
            result = cv2.matchTemplate(roi, template_gray, cv2.TM_CCORR_NORMED, mask=template_mask)
        else:
            result = cv2.matchTemplate(roi, template_gray, cv2.TM_CCORR_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        click_x = ROI_X1 + max_loc[0] + tw // 2
        click_y = ROI_Y1 + max_loc[1] + th // 2
        return max_val * 100, click_x, click_y

    def screen_changed(path_before, path_after, threshold=5.0):
        """只比對 X 按鈕範圍內的區域，避免動畫干擾"""
        img1 = cv2.imread(path_before, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(path_after, cv2.IMREAD_GRAYSCALE)
        if img1 is None or img2 is None or img1.shape != img2.shape:
            return True
        region1 = img1[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]
        region2 = img2[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]
        diff = cv2.absdiff(region1, region2)
        changed_pixels = np.count_nonzero(diff > 15)
        change_ratio = changed_pixels / diff.size * 100
        print(f"      （X區域變化率：{change_ratio:.2f}%）")
        return change_ratio > threshold

    MAX_ATTEMPTS = 15
    no_change_count = 0

    prev_path = take_screenshot("x_before")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        similarity, click_x, click_y = find_x_button(prev_path)
        print(f"   [{attempt}] X按鈕相似度：{similarity:.2f}%，最佳位置：({click_x}, {click_y})")

        # 點擊最佳位置
        device.shell(f"input tap {click_x} {click_y}")
        time.sleep(0.8)

        # 截圖比較 ROI 區域是否有變化
        curr_path = take_screenshot(f"x_after_{attempt}")
        changed = screen_changed(prev_path, curr_path)

        if changed:
            print(f"   ✅ 畫面有變化，X彈窗已關閉，繼續偵測...")
            no_change_count = 0
        else:
            no_change_count += 1
            print(f"   ⚠️  畫面無變化（連續 {no_change_count} 次）")
            if no_change_count >= 3:
                print(f"   ✅ 連續 3 次無變化，判斷X彈窗已全部關閉")
                try:
                    os.remove(curr_path)
                except:
                    pass
                break

        try:
            os.remove(prev_path)
        except:
            pass
        prev_path = curr_path
    else:
        print(f"   ⚠️  已達最大嘗試次數 {MAX_ATTEMPTS} 次，繼續下一步")

    try:
        os.remove(prev_path)
    except:
        pass

    # 清除最後暫存
    try:
        os.remove(prev_path)
    except:
        pass

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

        # 第一個頁籤直接執行（進入活動中心時已在第一頁，點擊不會有畫面變化）
        if tab_index == 0:
            device.shell(f"input tap {tab['x']} {tab['y']}")
            time.sleep(2)
            print(f"   ✅ 第一個頁籤，直接執行")
        else:
            # 第二個頁籤之後，點擊前後比對判斷頁籤是否存在
            before_tab_sdcard = f"/sdcard/before_tab{tab_index + 1}.png"
            before_tab_local = os.path.join(SCREENSHOT_DIR, f"before_tab{tab_index + 1}.png")
            device.shell(f"screencap -p {before_tab_sdcard}")
            time.sleep(0.5)
            device.pull(before_tab_sdcard, before_tab_local)
            time.sleep(0.3)

            device.shell(f"input tap {tab['x']} {tab['y']}")
            time.sleep(2)

            after_tab_sdcard = f"/sdcard/after_tab{tab_index + 1}.png"
            after_tab_local = os.path.join(SCREENSHOT_DIR, f"after_tab{tab_index + 1}.png")
            device.shell(f"screencap -p {after_tab_sdcard}")
            time.sleep(0.5)
            device.pull(after_tab_sdcard, after_tab_local)
            time.sleep(0.3)

            _, tab_similarity = compare_images(before_tab_local, after_tab_local)
            print(f"   📊 頁籤切換前後相似度：{tab_similarity:.2f}%")

            for f in [before_tab_local, after_tab_local]:
                try:
                    os.remove(f)
                except:
                    pass

            if tab_similarity > 70.0:
                print(f"   ⏭️  畫面相同，判斷此頁籤不存在，跳過")
                continue

            print(f"   ✅ 頁籤存在，開始截圖...")

        # 關閉彈窗
        print("🗑️  關閉彈窗...")
        for _ in range(3):
            device.shell(f"input tap {CLOSE_BUTTON_X} {CLOSE_BUTTON_Y}")
            time.sleep(0.2)
        time.sleep(1)

        # 【階段一】依序點擊前 6 個固定座標並截圖
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

        # 【階段二】從第 7 張起，持續點擊 Y=1300，直到畫面與上一張相同
        print(f"\n  🔁 開始持續點擊 X={REPEAT_TAP_X}, Y={REPEAT_TAP_Y}，直到畫面無新內容...")
        previous_path = screenshot_path  # 以第 6 張為基準
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
