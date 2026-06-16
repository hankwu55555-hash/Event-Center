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
BACKFILL_DATES = ["20260611", "20260612"]

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
    json.loads(content)
    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if p.exists():
        shutil.copy2(p, str(p) + ".bak")
    os.replace(tmp, p)

# ─── API 攔截 ─────────────────────────────────────────────────────────────────
async def capture_api(page, url, wait_ms=10000):
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

# ─── 排名解析（遞迴掃描 graphData）──────────────────────────────────────────
def _find_rank_in_graphdata(gd):
    if not isinstance(gd, list):
        return None
    for entry in reversed(gd):
        if isinstance(entry, list) and len(entry) >= 2:
            v = entry[1]
            if isinstance(v, (int, float)) and 1 <= int(v) <= 5000:
                return int(v)
    return None

def _search_graphdata(obj, depth=0):
    if depth > 8:
        return None
    if isinstance(obj, dict):
        if "graphData" in obj:
            r = _find_rank_in_graphdata(obj["graphData"])
            if r:
                return r
        for v in obj.values():
            r = _search_graphdata(v, depth + 1)
            if r:
                return r
    if isinstance(obj, list):
        for item in obj[:50]:
            r = _search_graphdata(item, depth + 1)
            if r:
                return r
    return None

def extract_rank(captured, app_id):
    SKIP_KEYS = {"apps", "categories", "chart_types", "countries", "code",
                 "server_upload_time", "payload_size_bytes", "events_ingested"}
    for c in captured:
        body = c["body"]
        if not isinstance(body, dict):
            continue
        # 優先從 app_id key 找
        app_data = body.get(str(app_id))
        if app_data is None:
            for k in body:
                if k not in SKIP_KEYS and k != "lines":
                    app_data = body[k]
                    break
        if isinstance(app_data, dict):
            r = _search_graphdata(app_data)
            if r:
                return r
        # 嘗試 lines
        lines = body.get("lines")
        if isinstance(lines, list):
            r = _search_graphdata(lines)
            if r:
                return r
        # 全掃描保底
        r = _search_graphdata(body)
        if r:
            return r
    return None

# ─── 查詢單一排名 ─────────────────────────────────────────────────────────────
async def fetch_rank(context, os_type, prod, st_country, date_str):
    d = datetime.strptime(date_str, "%Y%m%d")
    date_api  = d.strftime("%Y-%m-%d")
    start_api = (d - timedelta(days=30)).strftime("%Y-%m-%d")
    if os_type == "ios":
        app_id = prod["apple_id"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=ios&start_date={start_api}&end_date={date_api}"
            f"&{prod['apple_param']}&edit=1&granularity=daily"
            f"&country={st_country}&category={prod['apple_category']}"
            f"&chart_type=free&breakdown_attribute=appId&device=iphone&selected_tab=0"
        )
    else:
        app_id = prod["android_saa"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=android&start_date={start_api}&end_date={date_api}"
            f"&saa={app_id}&edit=1&granularity=daily"
            f"&country={st_country}&category={prod['android_category']}"
            f"&chart_type=free&breakdown_attribute=appId&device=android&selected_tab=0"
        )
    page = await context.new_page()
    try:
        captured = await capture_api(page, url)
    finally:
        await page.close()
    return extract_rank(captured, app_id)

# ─── 主流程 ──────────────────────────────────────────────────────────────────
async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="zh-TW",
        )

        # 暖機：先載入首頁讓 Sensor Tower 建立 session
        print("🔥 暖機中...")
        warmup = await context.new_page()
        try:
            await warmup.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
            await warmup.wait_for_timeout(4000)
        except Exception:
            pass
        finally:
            await warmup.close()
        print("✅ 暖機完成\n")

        for prod in PRODUCTS:
            print(f"{'='*50}")
            print(f"補抓產品：{prod['name']}")
            print('='*50)
            rankings = load_json(prod["rankings_file"], {})

            for date_str in BACKFILL_DATES:
                print(f"\n  日期：{date_str}")
                rankings.setdefault(date_str, {})
                for local_key, st_country in COUNTRIES.items():
                    entry = rankings[date_str].setdefault(local_key, {})
                    apple   = await fetch_rank(context, "ios",     prod, st_country, date_str)
                    android = await fetch_rank(context, "android", prod, st_country, date_str)
                    a_str = f"#{apple}"   if apple   else "--"
                    g_str = f"#{android}" if android else "--"
                    print(f"    [{local_key}] Apple: {a_str:<6}  Android: {g_str}")
                    if apple   is not None and "apple"   not in entry: entry["apple"]   = apple
                    if android is not None and "android" not in entry: entry["android"] = android

            save_json(prod["rankings_file"], rankings)
            print(f"\n✅ {prod['name']} 補抓完成\n")

        await context.close()
        await browser.close()

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
