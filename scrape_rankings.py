#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sensor Tower 排名自動爬蟲（無需登入）

安裝依賴（只需一次）：
  pip install playwright --break-system-packages
  playwright install chromium

執行：
  python scrape_rankings.py
"""

import json, asyncio, re, sys
from datetime import date, timedelta
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

REPO_DIR           = Path(__file__).parent
CF_RANKINGS_FILE   = REPO_DIR / "CF"   / "rankings.json"
DAFU_RANKINGS_FILE = REPO_DIR / "Dafu" / "rankings.json"
DEBUG_FILE         = REPO_DIR / "st_debug.json"

BASE_URL = "https://app.sensortower-china.com"

# Cash Frenzy
CF_APP_APPLE       = "1404165333"
CF_APP_ANDROID_SAA = "slots.pcg.casino.games.free.android"

# 大福娛樂城
DAFU_APP_APPLE_SIA = "1356980152"
DAFU_APP_ANDROID_SAA = "com.grandegames.slots.dafu.casino"

COUNTRIES = {
    "TW": "TW",
    "US": "US",
    "JP": "JP",
    "UK": "GB",
}

# 各產品設定
PRODUCTS = [
    {
        "name": "Cash Frenzy",
        "rankings_file": CF_RANKINGS_FILE,
        "apple_id": CF_APP_APPLE,
        "apple_sia": None,
        "apple_category": "game_casino&category=all",
        "android_saa": CF_APP_ANDROID_SAA,
        "android_category": "game_casino&category=all",
    },
    {
        "name": "大福娛樂城",
        "rankings_file": DAFU_RANKINGS_FILE,
        "apple_id": None,
        "apple_sia": DAFU_APP_APPLE_SIA,
        "apple_category": "7006&category=0",
        "android_saa": DAFU_APP_ANDROID_SAA,
        "android_category": "game_casino&category=all",
    },
]

# ─── JSON 工具（原子寫入 + 自動修復）─────────────────────────────────────────
import os

def load_json(path, default=None):
    if default is None:
        default = {}
    p = Path(path)
    for src in [p, Path(str(p) + ".bak")]:
        if not src.exists():
            continue
        try:
            raw = src.read_bytes().decode("utf-8", errors="ignore")
            raw = raw.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()
            # 嘗試補上缺失的結尾括號
            for suffix in ["", "}", "}}",  "\n}", "\n}}"]:
                try:
                    return json.loads(raw + suffix)
                except Exception:
                    pass
        except Exception:
            pass
    return default

def save_json(path, data):
    """原子寫入：先寫 .tmp，驗證後 rename，並保留 .bak 備份"""
    p = Path(path)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    # 驗證資料可以被正確讀回
    json.loads(content)
    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    # 備份舊檔
    if p.exists():
        import shutil
        shutil.copy2(p, str(p) + ".bak")
    os.replace(tmp, p)

# ─── 排名搜尋（只從明確命名的 rank 欄位取值，避免誤抓 downloads/rating）────
RANK_KEYS = {
    "category_ranking", "category_rank", "rank", "ranking",
    "current_rank", "free_rank", "position", "chart_rank",
    "store_rank", "free_ranking", "paid_rank",
}

def find_rank(obj, depth=0, _in_rank_key=False):
    """
    _in_rank_key=True 時才允許回傳整數，確保只取 rank 欄位的值，
    不誤抓 downloads_rounded(700)、rating(5) 等無關整數。
    """
    if depth > 8:
        return None
    if _in_rank_key and isinstance(obj, (int, float)):
        v = int(obj)
        if 1 <= v <= 5000:
            return v
    if isinstance(obj, dict):
        # 優先找命名的排名欄位
        for key in RANK_KEYS:
            if key in obj:
                v = find_rank(obj[key], depth + 1, _in_rank_key=True)
                if v:
                    return v
        # 再遞迴其他欄位（但不標記為 rank key）
        for v in obj.values():
            r = find_rank(v, depth + 1, _in_rank_key=False)
            if r:
                return r
    if isinstance(obj, list):
        for item in obj[:30]:
            r = find_rank(item, depth + 1, _in_rank_key=_in_rank_key)
            if r:
                return r
    return None

# ─── 前往頁面並攔截所有 JSON API 回應 ────────────────────────────────────────
async def capture_api(page, url, wait_ms=6000):
    captured = []

    async def on_resp(resp):
        ct = resp.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            body = await resp.json()
            captured.append({"url": resp.url, "body": body})
        except Exception:
            pass

    page.on("response", on_resp)
    try:
        await page.goto(url, timeout=40000, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=25000)
        await page.wait_for_timeout(wait_ms)
    except PlaywrightTimeout:
        pass
    finally:
        page.remove_listener("response", on_resp)

    for c in captured:
        print(f"    [API] {c['url'][-80:]}")

    return captured

def _make_debug_entries(st_caps, app_id):
    entries = []
    for c in st_caps:
        body = c["body"]
        entry = {"url": c["url"][-90:]}
        if isinstance(body, dict):
            entry["body_keys"] = list(body.keys())
            if "category_history" in c["url"]:
                # 找 app_id key（str 或直接第一個非 lines key）
                app_data = body.get(str(app_id))
                if app_data is None:
                    for k in body:
                        if k != "lines":
                            app_data = body[k]
                            break
                if isinstance(app_data, list):
                    entry["history_sample"] = app_data[:3]
                elif isinstance(app_data, dict):
                    entry["history_sample"] = app_data
        else:
            entry["body_type"] = type(body).__name__
            entry["body_sample"] = str(body)[:200]
        entries.append(entry)
    return entries


# ─── 單一日期排名抓取（Apple / Android 共用）────────────────────────────────
async def fetch_rank(page, os_type, st_country, target_date, debug, debug_key, prod_cfg=None):
    """
    target_date: date 物件
    os_type: "ios" | "android"
    prod_cfg: PRODUCTS dict，None 時預設 CF
    """
    if prod_cfg is None:
        prod_cfg = PRODUCTS[0]

    end_api  = target_date.strftime("%Y-%m-%d")
    prev_api = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")

    if os_type == "ios":
        if prod_cfg["apple_sia"]:
            id_param = f"sia={prod_cfg['apple_sia']}"
            app_id   = prod_cfg["apple_sia"]
        else:
            id_param = f"app_id={prod_cfg['apple_id']}"
            app_id   = prod_cfg["apple_id"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=ios&start_date={prev_api}&end_date={end_api}"
            f"&{id_param}&granularity=daily"
            f"&country={st_country}&category={prod_cfg['apple_category']}"
            f"&chart_type=free&breakdown_attribute=appId"
            f"&device=iphone&selected_tab=0"
        )
    else:
        app_id = prod_cfg["android_saa"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=android&start_date={prev_api}&end_date={end_api}"
            f"&saa={app_id}&granularity=daily"
            f"&country={st_country}&category={prod_cfg['android_category']}"
            f"&chart_type=free&breakdown_attribute=appId"
            f"&device=android&selected_tab=0"
        )

    captured = await capture_api(page, url, wait_ms=6000)
    st_caps = [c for c in captured if "sensortower-china.com" in c["url"]]
    debug[debug_key] = _make_debug_entries(st_caps, app_id)

    r = _parse_category_history(captured, app_id, st_country)
    return r


# ─── Apple App Store 類別排名 ────────────────────────────────────────────────
async def get_apple_rank(page, st_country, debug, target_date=None, prod_cfg=None):
    if target_date is None:
        target_date = date.today()
    prod_name = (prod_cfg or PRODUCTS[0])["name"]
    label = target_date.strftime("%Y%m%d")
    print(f"  [Apple/{prod_name}/{st_country}/{label}] 抓取中...")
    r = await fetch_rank(page, "ios", st_country, target_date, debug, f"apple_{st_country}_{label}", prod_cfg)
    print(f"    → {'#'+str(r) if r else '未找到排名'}")
    return r


# ─── Google Play 類別排名 ─────────────────────────────────────────────────────
async def get_android_rank(page, st_country, debug, target_date=None, prod_cfg=None):
    if target_date is None:
        target_date = date.today()
    prod_name = (prod_cfg or PRODUCTS[0])["name"]
    label = target_date.strftime("%Y%m%d")
    print(f"  [Android/{prod_name}/{st_country}/{label}] 抓取中...")
    r = await fetch_rank(page, "android", st_country, target_date, debug, f"android_{st_country}_{label}", prod_cfg)
    print(f"    → {'#'+str(r) if r else '未找到排名'}")
    return r


def _parse_category_history(captured, app_id, st_country):
    """
    category_history API 真實回應結構：
      {
        "<app_id>": {
          "<country>": {
            "<category_id>": {
              "<chart_type>": {
                "todays_rank": 75,
                "graphData": [[timestamp, rank, null], ...]
              }
            }
          }
        },
        "lines": [...]
      }
    """
    history_caps = [c for c in captured if "category_history" in c["url"]]
    for c in history_caps:
        body = c["body"]
        if not isinstance(body, dict):
            continue

        # 找 app_id key（string）
        app_data = body.get(str(app_id))
        if app_data is None:
            # fallback：第一個非 "lines" key
            for k in body:
                if k != "lines":
                    app_data = body[k]
                    break

        if not isinstance(app_data, dict):
            continue

        # 導航到 country 層
        country_data = app_data.get(st_country)
        if not isinstance(country_data, dict):
            country_data = app_data

        # 遍歷 category_id → chart_type → 取 graphData 最後一筆
        # ⚠️ 不用 todays_rank：它永遠是即時排名，查歷史日期時會回傳今天的值
        for cat_val in country_data.values():
            if not isinstance(cat_val, dict):
                continue
            for chart_val in cat_val.values():
                if not isinstance(chart_val, dict):
                    continue
                gd = chart_val.get("graphData")
                if isinstance(gd, list) and gd:
                    # 最後一筆對應 end_date（即目標日期）
                    last = gd[-1]
                    if isinstance(last, list) and len(last) >= 2:
                        v = last[1]
                        if isinstance(v, (int, float)) and 1 <= int(v) <= 5000:
                            return int(v)

    return None

# ─── 主流程 ──────────────────────────────────────────────────────────────────
async def main():
    today     = date.today()
    today_key = today.strftime("%Y%m%d")
    yesterday     = today - timedelta(days=1)
    yesterday_key = yesterday.strftime("%Y%m%d")
    debug = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-TW",
        )
        page = await context.new_page()

        for prod in PRODUCTS:
            rankings = load_json(prod["rankings_file"], {})
            print(f"\n{'='*50}")
            print(f"🎮 {prod['name']}")
            print('='*50)

            # ── 今天 ──────────────────────────────────────────────────────────
            print(f"\n📅 今天 {today_key}")
            if today_key not in rankings:
                rankings[today_key] = {}
            for local_key, st_country in COUNTRIES.items():
                entry = rankings[today_key].setdefault(local_key, {})
                apple   = await get_apple_rank(page, st_country, debug, today, prod)
                android = await get_android_rank(page, st_country, debug, today, prod)
                if apple   is not None: entry["apple"]   = apple
                if android is not None: entry["android"] = android

            if yesterday_key not in rankings:
                rankings[yesterday_key] = {}
            for local_key, st_country in COUNTRIES.items():
                entry = rankings[yesterday_key].setdefault(local_key, {})
                apple   = await get_apple_rank(page, st_country, debug, yesterday, prod)
                android = await get_android_rank(page, st_country, debug, yesterday, prod)
                if apple   is not None: entry["apple"]   = apple
                if android is not None: entry["android"] = android

            save_json(prod["rankings_file"], rankings)
            print(f"\n {prod['name']} rankings.json updated")

        await browser.close()

    save_json(DEBUG_FILE, debug)

    import subprocess
    r = subprocess.run(
        [sys.executable, str(REPO_DIR / "generate_gallery.py")],
        capture_output=True, text=True, cwd=str(REPO_DIR)
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print("[Error]", r.stderr[:300])

if __name__ == "__main__":
    asyncio.run(main())
