#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
往回補抓歷史排名資料（支援 CF + 大福）
用法：python backfill_rankings.py
"""

import json, asyncio, os, sys, shutil
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

REPO_DIR = Path(__file__).parent
BASE_URL  = "https://app.sensortower-china.com"

COUNTRIES = {"TW": "TW", "US": "US", "JP": "JP", "UK": "GB"}

# 要補抓的日期
BACKFILL_DATES = ["20260601", "20260602", "20260603", "20260604"]

# 各產品設定
PRODUCTS = [
    {
        "name": "Cash Frenzy",
        "rankings_file": REPO_DIR / "CF" / "rankings.json",
        "apple_param": "app_id=1404165333",
        "apple_id":    "1404165333",
        "apple_category": "game_casino&category=all",
        "android_saa": "slots.pcg.casino.games.free.android",
        "android_category": "game_casino&category=all",
    },
    {
        "name": "Dafu",
        "rankings_file": REPO_DIR / "Dafu" / "rankings.json",
        "apple_param": "sia=1356980152",
        "apple_id":    "1356980152",
        "apple_category": "7006&category=0",
        "android_saa": "com.grandegames.slots.dafu.casino",
        "android_category": "game_casino&category=all",
    },
]

# ─── JSON 工具（原子寫入 + 自動修復）─────────────────────────────────────────
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
            for suffix in ["", "}", "}}", "\n}", "\n}}"]:
                try:
                    return json.loads(raw + suffix)
                except Exception:
                    pass
        except Exception:
            pass
    return default

def save_json(path, data):
    p = Path(path)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    json.loads(content)  # 驗證
    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if p.exists():
        shutil.copy2(p, str(p) + ".bak")
    os.replace(tmp, p)

# ─── API 攔截 ─────────────────────────────────────────────────────────────────
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
    return captured

def extract_rank_from_graphdata(captured, app_id, st_country, date_str):
    """取 graphData 最後一筆（對應 end_date = target_date），與 scrape_rankings.py 邏輯一致"""
    SKIP_KEYS = {"apps", "categories", "chart_types", "countries", "code",
                 "server_upload_time", "payload_size_bytes", "events_ingested"}
    for c in captured:
        body = c["body"]
        if not isinstance(body, dict):
            continue
        app_data = body.get(str(app_id))
        if app_data is None:
            for k in body:
                if k not in SKIP_KEYS and k != "lines":
                    app_data = body[k]
                    break
        if not isinstance(app_data, dict):
            continue
        country_data = app_data.get(st_country, app_data)
        if not isinstance(country_data, dict):
            continue
        for cat_val in country_data.values():
            if not isinstance(cat_val, dict):
                continue
            for chart_val in cat_val.values():
                if not isinstance(chart_val, dict):
                    continue
                gd = chart_val.get("graphData")
                if isinstance(gd, list) and gd:
                    # 從尾端找第一個有效排名（跳過 null 值）
                    for entry in reversed(gd):
                        if isinstance(entry, list) and len(entry) >= 2:
                            v = entry[1]
                            if isinstance(v, (int, float)) and 1 <= int(v) <= 5000:
                                return int(v)
    return None

async def fetch_rank(context, os_type, prod, st_country, date_str):
    d = datetime.strptime(date_str, "%Y%m%d")
    date_api  = d.strftime("%Y-%m-%d")
    start_api = (d - timedelta(days=30)).strftime("%Y-%m-%d")
    if os_type == "ios":
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=ios&start_date={start_api}&end_date={date_api}"
            f"&{prod['apple_param']}&granularity=daily"
            f"&country={st_country}&category={prod['apple_category']}"
            f"&chart_type=free&breakdown_attribute=appId&device=iphone&selected_tab=0"
        )
        app_id = prod["apple_id"]
    else:
        app_id = prod["android_saa"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=android&start_date={start_api}&end_date={date_api}"
            f"&saa={app_id}&granularity=daily"
            f"&country={st_country}&category={prod['android_category']}"
            f"&chart_type=free&breakdown_attribute=appId&device=android&selected_tab=0"
        )
    # 每次開新頁面避免狀態污染
    page = await context.new_page()
    try:
        captured = await capture_api(page, url, wait_ms=10000)
    finally:
        await page.close()
    return extract_rank_from_graphdata(captured, app_id, st_country, date_str)

# Chrome profile 路徑（借用登入 session）
CHROME_PROFILE = r"C:\Users\hankwu\AppData\Local\Google\Chrome\User Data"

async def main():
    async with async_playwright() as pw:
        # 使用現有 Chrome profile，借用 Sensor Tower 登入 session
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 900},
            locale="zh-TW",
        )
        for prod in PRODUCTS:
            print(f"\n{'='*50}")
            print(f"補抓產品：{prod['name']}")
            print('='*50)
            rankings = load_json(prod["rankings_file"], {})

            for date_str in BACKFILL_DATES:
                print(f"\n  日期：{date_str}")
                if date_str not in rankings:
                    rankings[date_str] = {}
                for local_key, st_country in COUNTRIES.items():
                    entry = rankings[date_str].setdefault(local_key, {})
                    apple   = await fetch_rank(context, "ios",     prod, st_country, date_str)
                    android = await fetch_rank(context, "android", prod, st_country, date_str)
                    print(f"    [{local_key}] Apple: {'#'+str(apple) if apple else '--'}  Android: {'#'+str(android) if android else '--'}")
                    if apple   is not None: entry["apple"]   = apple
                    if android is not None: entry["android"] = android

            save_json(prod["rankings_file"], rankings)
            print(f"\n✅ {prod['name']} 補抓完成")

        await context.close()

    # 重新產生 gallery + push
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
