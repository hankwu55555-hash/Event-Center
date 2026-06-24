#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大福Online 活動中心自動化 - v2（模板偵測版）

兩段全自動：
  1) 自動偵測「登入獎勵」畫面 -> 領取 -> 關閉所有彈窗
  2) 進活動中心 -> 逐一頁籤 -> 每個活動截圖（用左側清單比對偵測末尾，抗動畫）

偵測方式：multi-scale template matching（多尺度模板比對）。
  - 「找得到才點」，沒有登入獎勵就跳過，不會亂點。
  - 解析度不一致也沒關係，腳本會自動試多個縮放比例。

用法：
  python auto_activity_dafu_v2.py            # 正式執行
  python auto_activity_dafu_v2.py --dry-run  # 只截圖+標註偵測結果，不點任何東西（建議先跑這個校正）
"""

import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np
from adb_shell.adb_device import AdbDeviceTcp

# ───────────────────────── 設定 ─────────────────────────
HOST, PORT = "127.0.0.1", 5555
BASE_DIR = r"C:\Users\hankwu\Desktop\Event_Center\Dafu"
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
PACKAGE_NAME = "com.grandegames.slots.dafu.casino"

# 裝置實際解析度（adb wm size）：2960 x 1440
ACTIVITY_BTN = (2560, 55)          # 右上角「活動」鈕

# 4 個頁籤（左側）
TABS = [
    {"name": "促銷", "x": 315, "y": 400},
    {"name": "機台", "x": 315, "y": 613},
    {"name": "活動", "x": 315, "y": 835},
    {"name": "公告", "x": 315, "y": 1055},
]

# 活動項目的點擊位置：前幾項各自位置，清單捲到底後固定點最後一個槽位
# （清單會自動往下捲，所以後面重複點同一個 Y 就能依序選到新項目）
ITEM_SLOTS = [
    (587, 395), (587, 575), (587, 780), (587, 1010), (587, 1125),
]
SCROLL_SLOT = (587, 1315)          # 捲到底後反覆點這裡帶出下一個項目
MAX_ITEMS_PER_TAB = 40             # 安全上限

# 比對用的「左側清單」區域（device 座標）——只看這塊就不會被右側動畫干擾
LIST_REGION = (170, 230, 950, 1410)   # (x0, y0, x1, y1)
SAME_THRESHOLD = 6.0               # 左側區域平均像素差 < 此值 => 視為同一畫面（到末尾）

TMP_PNG = os.path.join(BASE_DIR, "_cap_tmp.png")

# 模板的縮放搜尋範圍
SCALES_VIDEO = [round(1.25 + 0.025 * i, 3) for i in range(23)]   # 1.25..1.80（從影片裁的模板）
SCALES_WIDE = [round(0.85 + 0.05 * i, 3) for i in range(20)]      # 0.85..1.80（X 鈕：含實機與影片兩種尺度）


# ───────────────────────── 工具 ─────────────────────────
def load_templates():
    t = {}
    for name in ["login_banner", "claim_button", "close_x_dark", "close_x_purple"]:
        p = os.path.join(TEMPLATE_DIR, name + ".png")
        img = cv2.imread(p)
        if img is None:
            raise FileNotFoundError(f"找不到模板：{p}")
        t[name] = img
    return t


def grab(device):
    """截一張裝置畫面，回傳 BGR numpy array。"""
    device.shell(f"screencap -p /sdcard/_cap.png")
    device.pull("/sdcard/_cap.png", TMP_PNG)
    img = cv2.imread(TMP_PNG)
    return img


def find(screen, tpl, region=None, threshold=0.55, scales=SCALES_VIDEO):
    """
    多尺度模板比對。回傳 (center(x,y), score)；找不到則 center=None。
    region: 只在畫面這塊區域內找 (x0,y0,x1,y1)，加速又避免誤配。
    """
    sg = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    H, W = sg.shape
    ox, oy = 0, 0
    if region:
        ox, oy, x1, y1 = region
        # 夾在畫面範圍內，避免方向/解析度不符時整塊落空
        ox, oy = max(0, ox), max(0, oy)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 <= ox or y1 <= oy:
            return None, -1.0
        sg = sg[oy:y1, ox:x1]
    tg = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    th, tw = tg.shape
    best_score, best_center = -1.0, None
    for s in scales:
        w, h = int(tw * s), int(th * s)
        if w < 8 or h < 8 or w >= sg.shape[1] or h >= sg.shape[0]:
            continue
        r = cv2.resize(tg, (w, h))
        res = cv2.matchTemplate(sg, r, cv2.TM_CCOEFF_NORMED)
        _, mx, _, ml = cv2.minMaxLoc(res)
        if mx > best_score:
            best_score = mx
            best_center = (ox + ml[0] + w // 2, oy + ml[1] + h // 2)
    if best_score >= threshold:
        return best_center, best_score
    return None, best_score


def find_close_x(screen, templates):
    """在右上角找關閉鈕（兩種樣式擇一）。"""
    region = (2250, 30, 2960, 380)
    for key in ("close_x_dark", "close_x_purple"):
        center, score = find(screen, templates[key], region=region,
                             threshold=0.55, scales=SCALES_WIDE)
        if center:
            return center, score, key
    return None, score, None


def tap(device, x, y, wait=1.0):
    device.shell(f"input tap {int(x)} {int(y)}")
    time.sleep(wait)


def list_signature(screen):
    """左側清單區域的指紋：縮小+灰階，用來判斷『選到的項目有沒有換』。"""
    x0, y0, x1, y1 = LIST_REGION
    crop = screen[y0:y1, x0:x1]
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (100, 180)).astype(np.int16)


def same_screen(sig1, sig2):
    return float(np.abs(sig1 - sig2).mean()) < SAME_THRESHOLD


# ───────────────────────── 流程 ─────────────────────────
def dismiss_popups(device, templates, max_n=6):
    """連續關閉右上角彈窗，直到找不到 X 為止。"""
    closed = 0
    for _ in range(max_n):
        img = grab(device)
        center, score, key = find_close_x(img, templates)
        if center:
            print(f"   關閉彈窗 X@{center} ({key} score={score:.2f})")
            tap(device, *center, wait=1.5)
            closed += 1
        else:
            break
    if closed:
        print(f"   已關閉 {closed} 個彈窗")
    return closed


def claim_login_reward(device, templates):
    """偵測登入獎勵畫面；有就領取並關閉，沒有就跳過。"""
    print("\n【登入獎勵】偵測中...")
    img = grab(device)
    center, score = find(img, templates["login_banner"],
                         region=(600, 120, 2400, 760), threshold=0.55)
    if not center:
        print(f"   未偵測到登入獎勵畫面 (best score={score:.2f})，跳過")
        return False

    print(f"   偵測到『今日登入獎勵』(score={score:.2f})，領取中...")
    btn, bscore = find(img, templates["claim_button"],
                       region=(600, 850, 2400, 1440), threshold=0.50)
    if btn:
        print(f"   點擊『立即領取』@{btn} (score={bscore:.2f})")
        tap(device, *btn, wait=2.5)
    else:
        # 後備：在橫幅正下方點擊（依偵測到的 banner 位置推算）
        fx, fy = center[0], center[1] + 820
        print(f"   未配到按鈕，後備點擊 @({fx},{fy})")
        tap(device, fx, fy, wait=2.5)

    # 領取後可能還有 7 天獎勵格 / 明天提醒，連續關閉
    dismiss_popups(device, templates, max_n=4)
    print("   登入獎勵流程完成")
    return True


def capture_activities(device, templates, out_dir):
    print("\n【活動中心】開啟中...")
    tap(device, *ACTIVITY_BTN, wait=3.0)

    total_saved = 0
    for ti, tab in enumerate(TABS):
        print("\n" + "=" * 60)
        print(f"頁籤 {ti + 1}：{tab['name']}")
        print("=" * 60)
        tap(device, tab["x"], tab["y"], wait=2.0)

        prev_sig = None
        saved = 0
        for idx in range(MAX_ITEMS_PER_TAB):
            slot = ITEM_SLOTS[idx] if idx < len(ITEM_SLOTS) else SCROLL_SLOT
            tap(device, *slot, wait=1.2)

            img = grab(device)
            sig = list_signature(img)

            if prev_sig is not None and same_screen(sig, prev_sig):
                print(f"   左側清單無變化 -> 頁籤『{tab['name']}』已到末尾")
                break

            saved += 1
            fname = f"tab{ti + 1}_{tab['name']}_{saved:02d}.jpg"
            cv2.imwrite(os.path.join(out_dir, fname),
                        img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print(f"   截圖 {saved}：{fname}")
            prev_sig = sig

        total_saved += saved
        print(f"   頁籤『{tab['name']}』完成，共 {saved} 張")

    print(f"\n全部頁籤完成，總共 {total_saved} 張截圖")
    return total_saved


def dry_run(device, templates, out_dir):
    """只偵測+標註，不點任何東西。用來在正式跑之前校正座標/門檻。"""
    print("\n【DRY-RUN】只偵測、不操作")
    img = grab(device)
    vis = img.copy()

    def box(center, label, color):
        if center:
            x, y = center
            cv2.circle(vis, (x, y), 40, color, 4)
            cv2.putText(vis, label, (x - 60, y - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

    c1, s1 = find(img, templates["login_banner"], region=(600, 120, 2400, 760), threshold=0.0)
    c2, s2 = find(img, templates["claim_button"], region=(600, 850, 2400, 1440), threshold=0.0)
    cx, sx, key = find_close_x(img, templates)
    print(f"   login_banner  score={s1:.2f}  center={c1}")
    print(f"   claim_button  score={s2:.2f}  center={c2}")
    print(f"   close_x       score={sx:.2f}  center={cx}  ({key})")

    box(c1, f"banner {s1:.2f}", (255, 0, 0))
    box(c2, f"claim {s2:.2f}", (0, 255, 0))
    box(cx, f"X {sx:.2f}", (0, 0, 255))
    # 畫出活動鈕與左側清單比對區
    cv2.circle(vis, ACTIVITY_BTN, 35, (0, 255, 255), 4)
    x0, y0, x1, y1 = LIST_REGION
    cv2.rectangle(vis, (x0, y0), (x1, y1), (255, 255, 0), 4)

    p = os.path.join(out_dir, "_dryrun_annotated.jpg")
    cv2.imwrite(p, vis, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f"   標註圖已存：{p}")


def main():
    dry = "--dry-run" in sys.argv

    today = datetime.now().strftime("%Y%m%d")
    out_dir = os.path.join(BASE_DIR, today)
    os.makedirs(out_dir, exist_ok=True)

    templates = load_templates()
    print(f"連接 {HOST}:{PORT} ...")
    device = AdbDeviceTcp(HOST, PORT)
    device.connect(read_timeout_s=10)
    print("ADB 連接成功")

    try:
        if dry:
            dry_run(device, templates, out_dir)
            return
        claim_login_reward(device, templates)
        dismiss_popups(device, templates)        # 清掉其他推銷彈窗（例如商城彈窗）
        capture_activities(device, templates, out_dir)
        print(f"\n完成！截圖位置：{out_dir}")
    finally:
        device.close()
        try:
            os.remove(TMP_PNG)
        except OSError:
            pass


if __name__ == "__main__":
    main()
