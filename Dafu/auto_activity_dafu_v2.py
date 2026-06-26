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
  python auto_activity_dafu_v2.py             # 正式執行：啟動App -> 領登入獎勵 -> 關彈窗 -> 活動截圖
  python auto_activity_dafu_v2.py --no-launch # 略過「啟動App」（大福已開好、在大廳時用）
  python auto_activity_dafu_v2.py --dry-run   # 只截圖+標註偵測結果，不點任何東西
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

# 切換到下一個活動：用「向上滾動」前進一個活動（比點清單可靠，不會因自動捲動幅度不固定
# 而跳號）。截圖去重後，連續幾次滾動都沒有新活動 => 到末尾。
#
# ★不同版面的「可捲動區」不一樣，所以用雙軌、先試安全的那個：
#   方式1 = 左側清單區 (x=450)：永遠沒有購買鈕，最安全；寬版面（如機台「通行證」）靠它捲。
#   方式2 = 右側卡片外深色縫隙 (x=2690)：窄版面堆疊清單（如促銷）靠它捲；在卡片外無按鈕。
#   每一步先滑左側清單，沒換到活動才滑右側縫隙 —— 這樣寬版面就不會去碰右側可能有的按鈕。
#   再加「可控長拖曳」(600ms)，夠長會捲動、夠果斷不會被判成點擊。
SELECT_TAB_X = 315                 # 頁籤點擊用的 X
LIST_SCROLL_X = 450                # 方式1：左側清單區（無購買鈕，最安全）
GAP_SCROLL_X = 2690                # 方式2：卡片右側外深色縫隙（X 鈕在 ~2806，不會誤觸）
SCROLL_FROM_Y = 760
SCROLL_TO_Y = 500                  # 上滑約 260px ≈ 前進一個活動（寧可小一點也不跳號）
SCROLL_MS = 600                    # 可控拖曳（夠長 => 會捲動；夠果斷 => 取消任何誤觸點擊）
SCROLL_WAIT = 1.2                  # 滾動後等待動畫定下來再截圖
STALE_SCROLLS = 4                  # 連續幾次滾動都沒有新活動 => 視為到末尾
MAX_ITEMS_PER_TAB = 60             # 安全上限

# 存檔大小控制：把每張截圖壓到約 100KB（±20），避免容量太大
JPEG_TARGET_KB = 100
JPEG_TOL_KB = 20

# 用「內容卡片頂端的大標題」當活動身分（每個活動標題不同、辨識度高，且幾乎不動畫）。
# 比用左側小標籤可靠：左側標籤太小、又被高亮底色蓋過，名稱相近的活動會被誤判成同一個
# （例如『隨機郵票大放送』vs『大福郵票』、『特惠折扣』vs『同花順促銷』）。
TITLE_REGION = (650, 120, 2250, 360)   # 卡片頂端大標題的範圍
TITLE_DUP_TOL = 15.0               # 標題平均像素差 < 此值 => 同一活動（實測：同一個~1、不同~43+）

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


def grab(device, retries=5):
    """
    截一張裝置畫面，回傳 BGR numpy array。
    screencap 偶爾會在 GL 畫面還沒 render 好時抓到「全黑空幀」，這裡會偵測並重抓，
    避免存到整張黑圖、也避免黑圖污染去重。
    """
    img = None
    for _ in range(retries):
        device.shell("screencap -p /sdcard/_cap.png")
        device.pull("/sdcard/_cap.png", TMP_PNG)
        img = cv2.imread(TMP_PNG)
        if img is not None and float(img.mean()) > 3.0:   # 非全黑/非空幀
            return img
        time.sleep(0.4)                                   # 等畫面 render 好再重抓
    return img


def imwrite_unicode(path, img, quality=85):
    """cv2.imwrite 在 Windows 不支援非 ASCII 路徑，改用 imencode + tofile。"""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        buf.tofile(path)
    return ok


def imwrite_target_size(path, img, target_kb=JPEG_TARGET_KB, tol_kb=JPEG_TOL_KB):
    """
    二分搜尋 JPEG 品質，把存檔大小鎖在 target_kb ± tol_kb（預設 100±20 KB）。
    固定品質的檔案大小會隨畫面內容浮動，這裡改成鎖大小，較穩定。
    """
    lo, hi = 2, 95
    best_buf, best_gap = None, None
    for _ in range(8):
        q = (lo + hi) // 2
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
        if not ok:
            break
        kb = len(buf) / 1024
        gap = abs(kb - target_kb)
        if best_gap is None or gap < best_gap:   # 記住最接近目標的一版
            best_buf, best_gap = buf, gap
        if kb < target_kb - tol_kb:
            lo = q + 1
        elif kb > target_kb + tol_kb:
            hi = q - 1
        else:
            best_buf = buf
            break
        if lo > hi:
            break
    if best_buf is not None:
        best_buf.tofile(path)
    return best_buf is not None


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


# 各種彈窗的關閉 X 都落在右上角這個窄帶（實測 X 中心 x≈2560~2595、y≈130~165）。
# 收窄到這塊可排除先前在 x≈2300~2450 的誤判，門檻才能放寬到 0.55 以接住「樣式相近、
# 但底色不同導致分數偏低」的 X（例如奇幻樂園彈窗的 X 只有 0.61）。
# y 從 90 起算，避開上方 y≈55 的「活動」鈕；x 到 2780，避開 x≈2790 的選單鈕。
CLOSE_X_REGION = (2520, 90, 2780, 240)
CLOSE_X_THRESHOLD = 0.55


def find_close_x(screen, templates):
    """在右上角找關閉鈕（兩種樣式擇一）。收窄區域 + 高門檻避免誤判。"""
    best_score = -1.0
    for key in ("close_x_dark", "close_x_purple"):
        center, score = find(screen, templates[key], region=CLOSE_X_REGION,
                             threshold=CLOSE_X_THRESHOLD, scales=SCALES_WIDE)
        best_score = max(best_score, score)
        if center:
            return center, score, key
    return None, best_score, None


def tap(device, x, y, wait=1.0):
    device.shell(f"input tap {int(x)} {int(y)}")
    time.sleep(wait)


def swipe(device, x1, y1, x2, y2, ms=600, wait=1.0):
    device.shell(f"input swipe {x1} {y1} {x2} {y2} {ms}")
    time.sleep(wait)


def activity_signature(screen):
    """以內容卡片頂端的大標題當活動身分（位置固定、辨識度高、幾乎不動畫）。"""
    x0, y0, x1, y1 = TITLE_REGION
    g = cv2.cvtColor(screen[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (200, 40)).astype(np.int16)


def is_duplicate(sig, seen, tol=TITLE_DUP_TOL):
    """sig 是否與已看過的任一活動相同。"""
    return any(float(np.abs(sig - s).mean()) < tol for s in seen)




# ───────────────────────── 流程 ─────────────────────────
def dismiss_popups(device, templates, max_rounds=16, patience=3, settle=1.3):
    """
    持續關閉右上角彈窗。
    冷啟動時彈窗會「陸續、延遲」跳出來，所以找不到 X 時不立刻收手，而是等一下再看，
    連續 patience 次都沒有 X 才結束（接住晚跳出來的彈窗）。
    每次關完會驗證畫面真的有變，避免對著誤判的 X 一直點。
    """
    closed = 0
    empty = 0
    prev_full = None
    for _ in range(max_rounds):
        img = grab(device)
        center, score, key = find_close_x(img, templates)
        if center:
            cur = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (120, 60)).astype(np.int16)
            if prev_full is not None and np.abs(cur - prev_full).mean() < 3.0:
                print("   關閉後畫面未變化，停止（避免誤點）")
                break
            print(f"   關閉彈窗 X@{center} ({key} score={score:.2f})")
            tap(device, *center, wait=1.5)
            closed += 1
            empty = 0
            prev_full = cur
        else:
            empty += 1
            if empty >= patience:
                break
            time.sleep(settle)   # 等可能晚跳出來的彈窗
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
    dismiss_popups(device, templates)
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

        seen = []          # 此頁籤已截過的活動指紋
        saved = 0

        def consider():
            """截目前畫面、去重、存檔；回傳是否為新活動。"""
            nonlocal saved
            img = grab(device)
            sig = activity_signature(img)
            if is_duplicate(sig, seen):
                return False
            seen.append(sig)
            saved += 1
            fname = f"tab{ti + 1}_{saved:02d}.jpg"   # ASCII 檔名
            imwrite_target_size(os.path.join(out_dir, fname), img)
            print(f"   截圖 {saved}：{fname}（{tab['name']}）")
            return True

        def scroll(x):
            swipe(device, x, SCROLL_FROM_Y, x, SCROLL_TO_Y, ms=SCROLL_MS, wait=SCROLL_WAIT)

        # 先截目前這個活動
        consider()
        stale = 0
        # 前進：先試左側清單捲動（安全），沒換到再試右側縫隙捲動；兩者都沒新活動才累積 stale
        while stale < STALE_SCROLLS and saved < MAX_ITEMS_PER_TAB:
            scroll(LIST_SCROLL_X)
            if consider():
                stale = 0
                continue
            scroll(GAP_SCROLL_X)
            stale = 0 if consider() else stale + 1

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
    # 畫出活動鈕、關閉鈕偵測區、兩條捲動軌跡
    cv2.circle(vis, ACTIVITY_BTN, 35, (0, 255, 255), 4)
    cv2.rectangle(vis, CLOSE_X_REGION[:2], CLOSE_X_REGION[2:], (0, 0, 255), 3)
    cv2.arrowedLine(vis, (LIST_SCROLL_X, SCROLL_FROM_Y), (LIST_SCROLL_X, SCROLL_TO_Y), (255, 255, 0), 4)
    cv2.arrowedLine(vis, (GAP_SCROLL_X, SCROLL_FROM_Y), (GAP_SCROLL_X, SCROLL_TO_Y), (255, 255, 0), 4)

    p = os.path.join(out_dir, "_dryrun_annotated.jpg")
    cv2.imwrite(p, vis, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f"   標註圖已存：{p}")


def launch_app(device, templates, max_wait=80):
    """
    強制重啟大福並等待載入完成。
    以「偵測到登入獎勵橫幅」為載入完成的訊號；偵測不到則最多等 max_wait 秒。
    """
    print("\n【啟動 App】強制重啟大福...")
    device.shell(f"am force-stop {PACKAGE_NAME}")
    time.sleep(2)
    device.shell(f"monkey -p {PACKAGE_NAME} -c android.intent.category.LAUNCHER 1")
    print(f"   等待載入（最多 {max_wait} 秒）...")
    time.sleep(15)                       # 首屏載入至少要十幾秒
    waited = 15
    while waited < max_wait:
        img = grab(device)
        c, s = find(img, templates["login_banner"],
                    region=(600, 120, 2400, 760), threshold=0.55)
        if c:
            print(f"   偵測到登入獎勵 (score={s:.2f})，載入完成")
            return
        time.sleep(5)
        waited += 5
    print("   等待逾時，仍繼續（可能今天已領過登入獎勵）")


def main():
    dry = "--dry-run" in sys.argv
    no_launch = "--no-launch" in sys.argv   # 略過啟動 App（大福已開好時用）

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
        if not no_launch:
            launch_app(device, templates)
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
