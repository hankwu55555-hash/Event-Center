#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
往回補抓歷史排名資料
用法：python backfill_rankings.py
"""

import json, asyncio
from datetime import date, timedelta, datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

CF_DIR        = Path(__file__).parent
RANKINGS_FILE = CF_DIR / "rankings.json"

BASE_URL        = "https://app.sensortower-china.com"
APP_APPLE       = "1404165333"
APP_ANDROID_SAA = "slots.pcg.casino.games.free.android"

COUNTRIES = {
    "TW": "TW",
    "US": "US",
    "JP": "JP",
    "UK": "GB",
}

# 要補抓的日期（YYYYMMDD）
BACKFILL_DATES = ["20260526", "20260527"]

def load_json(path, default=None):
    if default is None:
        default = {}
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_bytes().decode("utf-8").replace("\x00", "").strip())
        except Exception:
            pass
    return default

def save_json(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

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

def extract_rank_from_graphdata(captured, app_id, st_country, target_date_str):
    """
    target_date_str: "20260526"
    graphData 格式：[[unix_timestamp, rank, null], ...]
    找到對應日期的 rank。
    """
    # 把 target_date_str 轉成 unix timestamp（UTC 00:00）
    dt = datetime.strptime(target_date_str, "%Y%m%d")
    target_ts = int(dt.timestamp())
    # 允許前後 12 小時誤差（時區差）
    ts_min = target_ts - 43200
    ts_max = target_ts + 86400 + 43200

    history_caps = [c for c in captured if "category_history" in c["url"]]
    for c in history_caps:
        body = c["body"]
        if not isinstance(body, dict):
            continue

        app_data = body.get(str(app_id))
        if app_data is None:
            for k in body:
                if k != "lines":
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
                if not isinstance(gd, list):
                    continue
                # 找最接近 target_date 的資料點
                best_rank = None
                best_diff = float("inf")
                for entry in gd:
                    if isinstance(entry, list) and len(entry) >= 2:
                        ts = entry[0]
                        rank = entry[1]
                        if isinstance(rank, (int, float)) and 1 <= int(rank) <= 5000:
                            diff = abs(ts - target_ts)
                            if diff < best_diff:
                                best_diff = diff
                                best_rank = int(rank)
                # 48 小時內的資料才接受
                if best_rank and best_diff <= 48 * 3600:
                    return best_rank
    return None

async def fetch_rank_for_date(page, os_type, app_id_param, st_country, date_str):
    """date_str: YYYYMMDD"""
    d = datetime.strptime(date_str, "%Y%m%d")
    date_api = d.strftime("%Y-%m-%d")
    prev_api = (d - timedelta(days=1)).strftime("%Y-%m-%d")

    if os_type == "ios":
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=ios&start_date={prev_api}&end_date={date_api}"
            f"&app_id={APP_APPLE}&granularity=daily"
            f"&country={st_country}&category=game_casino&category=all"
            f"&chart_type=free&breakdown_attribute=appId"
            f"&device=iphone&selected_tab=0"
        )
        app_id = APP_APPLE
    else:
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=android&start_date={prev_api}&end_date={date_api}"
            f"&saa={APP_ANDROID_SAA}&granularity=daily"
            f"&country={st_country}&category=game_casino&category=all"
            f"&chart_type=free&breakdown_attribute=appId"
            f"&device=android&selected_tab=0"
        )
        app_id = APP_ANDROID_SAA

    captured = await capture_api(page, url, wait_ms=6000)
    rank = extract_rank_from_graphdata(captured, app_id, st_country, date_str)
    return rank

async def main():
    rankings = load_json(RANKINGS_FILE, {})

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

        for date_str in BACKFILL_DATES:
            print(f"\n{'='*40}")
            print(f"補抓日期：{date_str}")
            print('='*40)

            if date_str not in rankings:
                rankings[date_str] = {}

            for local_key, st_country in COUNTRIES.items():
                entry = rankings[date_str].setdefault(local_key, {})

                print(f"\n  [{local_key}] Apple...")
                apple = await fetch_rank_for_date(page, "ios", APP_APPLE, st_country, date_str)
                print(f"    → {'#'+str(apple) if apple else '未找到'}")

                print(f"  [{local_key}] Android...")
                android = await fetch_rank_for_date(page, "android", APP_ANDROID_SAA, st_country, date_str)
                print(f"    → {'#'+str(android) if android else '未找到'}")

                if apple   is not None: entry["apple"]   = apple
                if android is not None: entry["android"] = android

        await browser.close()

    save_json(RANKINGS_FILE, rankings)
    print(f"\n✅ rankings.json 補抓完成")
    print(json.dumps({d: rankings[d] for d in BACKFILL_DATES if d in rankings},
                     ensure_ascii=False, indent=2))

    # 重新產生 gallery + push
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, str(CF_DIR / "generate_gallery.py")],
        capture_output=True, text=True, cwd=str(CF_DIR)
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print("[錯誤]", r.stderr[:300])

if __name__ == "__main__":
    asyncio.run(main())
