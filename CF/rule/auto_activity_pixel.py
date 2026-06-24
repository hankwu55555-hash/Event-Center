#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
煤有錢Online 活動中心自動化 - 像素比較版
使用 PIL 比較圖像像素，判斷截圖是否相同
"""

import os
import glob
import time
import warnings
from datetime import datetime

# EasyOCR 在 CPU 上會一直印 pin_memory 的 UserWarning，純洗版、無害，過濾掉
warnings.filterwarnings("ignore", message=".*pin_memory.*")
from adb_shell.adb_device import AdbDeviceTcp
from PIL import Image
import hashlib
import cv2
import numpy as np
import easyocr

print("=" * 70)
print("🎮 煤有錢Online 活動中心自動化 - 像素比較版")
print("=" * 70)

def convert_to_jpg(png_path, quality=10):
    """將 PNG 轉成 JPG，回傳新的 JPG 路徑"""
    jpg_path = os.path.splitext(png_path)[0] + ".jpg"
    try:
        img = Image.open(png_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=quality)
        os.remove(png_path)  # 刪除原始 PNG
    except Exception as e:
        print(f"    ⚠️  轉換 JPG 失敗：{e}")
        return png_path  # 失敗就保留 PNG
    return jpg_path

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
    SCREENSHOT_DIR = os.path.join(r"C:\Users\hankwu\Desktop\Event_Center\CF", today)
    PACKAGE_NAME = "com.spinxgames.coalonline"
    X_BUTTON_REF = r"C:\Users\hankwu\Desktop\Event_Center\CF\basic\x_button.png"

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

    print("🔍 【步驟 4】偵測並關閉彈窗（X 按鈕 + 自動領取登入獎勵）...")
    # 載入 basic/ 底下所有 x_button*.png 作為 X 參考圖（支援不同顏色的 X，例如深紫/白色）
    BASIC_DIR = os.path.dirname(X_BUTTON_REF)
    x_template_paths = sorted(glob.glob(os.path.join(BASIC_DIR, "x_button*.png")))

    x_templates = []   # 每個元素：{"name", "gray", "mask", "th", "tw"}
    for tpath in x_template_paths:
        raw = cv2.imread(tpath, cv2.IMREAD_UNCHANGED)
        if raw is None:
            print(f"   ⚠️  讀取失敗，略過：{os.path.basename(tpath)}")
            continue
        if raw.ndim == 3 and raw.shape[2] == 4:
            t_gray = cv2.cvtColor(raw[:, :, :3], cv2.COLOR_BGR2GRAY)
            t_mask = raw[:, :, 3]               # Alpha 通道作為遮罩
            note = "Alpha遮罩"
        elif raw.ndim == 3:
            t_gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            t_mask = None
            note = "一般比對"
        else:
            t_gray = raw
            t_mask = None
            note = "灰階"
        h, w = t_gray.shape[:2]
        x_templates.append({"name": os.path.basename(tpath), "gray": t_gray,
                            "mask": t_mask, "th": h, "tw": w})
        print(f"   ✅ 載入 X 參考圖：{os.path.basename(tpath)}（{note}）")

    if not x_templates:
        print(f"   ⚠️  basic/ 底下找不到任何 x_button*.png，X 偵測將失效")

    def take_screenshot(tag):
        sdcard = f"/sdcard/temp_{tag}.png"
        local = os.path.join(SCREENSHOT_DIR, f"temp_{tag}.png")
        device.shell(f"screencap -p {sdcard}")
        time.sleep(0.5)
        device.pull(sdcard, local)
        time.sleep(0.3)
        return local

    # X 按鈕搜尋範圍（固定座標）；下緣擴到 260 以完整涵蓋較大的白 X
    ROI_X1, ROI_Y1 = 2531, 33
    ROI_X2, ROI_Y2 = 2944, 260

    # X 信心門檻：CCOEFF 分數 >= 此值才認定「畫面上真的有 X」
    # 實測：有X約 1.0、無X約 0.31，故取 0.5
    X_CONF_THRESHOLD = 0.5

    def find_x_button(local_path):
        """逐一比對所有 X 參考圖，取最像的那張
        回傳 (信心分數0~1, 點擊x, 點擊y, 命中圖名)"""
        screenshot = cv2.imread(local_path)
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        roi = gray[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]

        best_val = -1.0
        best_x, best_y = ROI_X1, ROI_Y1
        best_name = None
        for tpl in x_templates:
            # 模板不能比搜尋範圍大，否則 matchTemplate 會報錯
            if tpl["th"] > roi.shape[0] or tpl["tw"] > roi.shape[1]:
                continue
            try:
                if tpl["mask"] is not None:
                    result = cv2.matchTemplate(roi, tpl["gray"], cv2.TM_CCOEFF_NORMED, mask=tpl["mask"])
                else:
                    result = cv2.matchTemplate(roi, tpl["gray"], cv2.TM_CCOEFF_NORMED)
            except cv2.error:
                continue
            # 遮罩比對偶爾會產生 nan/inf，先清理再取最大值
            result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_x = ROI_X1 + max_loc[0] + tpl["tw"] // 2
                best_y = ROI_Y1 + max_loc[1] + tpl["th"] // 2
                best_name = tpl["name"]
        return best_val, best_x, best_y, best_name

    def screen_changed(path_before, path_after, threshold=25.0):
        """只比對 X 按鈕範圍內的區域，門檻拉高以排除背景動畫
        （實測：真關閉彈窗約 97%，純背景動畫約 6~9%，故門檻取 25%）"""
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

    def screen_changed_full(path_before, path_after, threshold=20.0):
        """比對整張畫面的變化率，用於判斷「領取」按鈕點下去後是否真的關掉了彈窗
        （彈窗消失會造成大面積變化；若只是主畫面常駐的「領取」字，點了畫面幾乎不變）"""
        img1 = cv2.imread(path_before, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(path_after, cv2.IMREAD_GRAYSCALE)
        if img1 is None or img2 is None or img1.shape != img2.shape:
            return True
        diff = cv2.absdiff(img1, img2)
        changed_pixels = np.count_nonzero(diff > 15)
        change_ratio = changed_pixels / diff.size * 100
        print(f"      （全畫面變化率：{change_ratio:.2f}%）")
        return change_ratio > threshold

    # ---- OCR：自動辨識「登入獎勵」這類強制領取畫面的按鈕 ----
    # 按鈕上常見的字樣，越偏「領取/收下」越優先；確認/確定等放後面當備援
    CLAIM_KEYWORDS = [
        "領取", "收下", "立即領取", "一鍵領取", "全部領取", "免費領取",
        "確認", "確定", "好的", "知道了", "我知道了",
    ]
    OCR_MIN_CONF = 0.4   # OCR 信心門檻，低於此值不採用

    print("   🔤 正在初始化 OCR 文字辨識引擎（首次執行會下載模型，請稍候）...")
    ocr_reader = easyocr.Reader(["ch_tra", "en"], gpu=False, verbose=False)
    print("   ✅ OCR 引擎就緒")

    def find_claim_button(image_path):
        """用 OCR 找畫面上的領取/確認按鈕，回傳 (中心x, 中心y, 文字) 或 None"""
        try:
            results = ocr_reader.readtext(image_path)
        except Exception as e:
            print(f"      ⚠️  OCR 辨識失敗：{e}")
            return None
        # 依關鍵字優先順序尋找，確保「領取」優先於「確認」
        for keyword in CLAIM_KEYWORDS:
            for bbox, text, conf in results:
                if conf < OCR_MIN_CONF:
                    continue
                if keyword in text.replace(" ", ""):
                    xs = [p[0] for p in bbox]
                    ys = [p[1] for p in bbox]
                    cx = int(sum(xs) / len(xs))
                    cy = int(sum(ys) / len(ys))
                    return cx, cy, text.strip()
        return None

    # ---- 統一清彈窗迴圈 ----
    # 策略：有 X 先按 X（直接關掉、跳過廣告獎勵）；沒 X 才按「領取」（真正強制領取）。
    # 終止：連續 2 次「既無 X 也無領取」就判定彈窗已清空。
    MAX_ATTEMPTS = 20
    clean_count = 0   # 連續判定「畫面乾淨、無彈窗」的次數

    prev_path = take_screenshot("clear_0")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        x_score, click_x, click_y, x_name = find_x_button(prev_path)

        if x_score >= X_CONF_THRESHOLD:
            # 有 X → 直接按 X 關閉（優先，避免點到會跳廣告的「領取」）
            print(f"   [{attempt}] ✖️ 偵測到 X（信心 {x_score:.2f}，{x_name}），按 X 關閉 ({click_x}, {click_y})")
            device.shell(f"input tap {click_x} {click_y}")
            time.sleep(0.8)
            clean_count = 0
            prev_path_old = prev_path
            prev_path = take_screenshot(f"clear_{attempt}")
        else:
            # 沒有可信的 X → 找「領取」這類強制領取按鈕
            claim = find_claim_button(prev_path)
            if claim is not None:
                cx, cy, text = claim
                print(f"   [{attempt}] 🎁 無 X，偵測到領取按鈕「{text}」，點擊領取 ({cx}, {cy})")
                device.shell(f"input tap {cx} {cy}")
                time.sleep(1.0)
                clean_count = 0
                prev_path_old = prev_path
                prev_path = take_screenshot(f"clear_{attempt}")
            else:
                # 既無 X 也無領取 → 畫面乾淨
                clean_count += 1
                print(f"   [{attempt}] ✅ 無 X、無領取（X信心 {x_score:.2f}）→ 畫面乾淨（連續 {clean_count} 次）")
                if clean_count >= 2:
                    print(f"   ✅ 連續 2 次無彈窗，判斷所有彈窗已清除")
                    break
                prev_path_old = prev_path
                prev_path = take_screenshot(f"clear_{attempt}")

        try:
            os.remove(prev_path_old)
        except Exception:
            pass
    else:
        print(f"   ⚠️  已達最大嘗試次數 {MAX_ATTEMPTS} 次，繼續下一步")

    # 清除最後暫存
    try:
        os.remove(prev_path)
    except Exception:
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
            screenshot_path = convert_to_jpg(screenshot_path, quality=10)
            screenshot_filename = os.path.basename(screenshot_path)

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
            screenshot_path = convert_to_jpg(screenshot_path, quality=10)
            screenshot_filename = os.path.basename(screenshot_path)

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

print("\n💡 提示：若缺少套件，請先執行：")
print("   pip install Pillow opencv-python numpy easyocr")
