#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
往回補抓歷史排名資料（支援 CF + 大福）
用法：python backfill_rankings.py
"""

import json, asyncio, os, re, sys, shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

REPO_DIR = Path(__file__).parent
BASE_URL  = "https://app.sensortower-china.com"

COUNTRIES = {"TW": "TW", "US": "US", "JP": "JP", "UK": "GB"}

MAX_RETRIES = 3  # 疑似網路失敗時的重試次數（解決間歇性 -- 的主因）

# 要補抓的日期（可用命令列覆寫，例如：python backfill_rankings.py 20260613 20260614 20260615）
BACKFILL_DATES = ["20260618", "20260619", "20260620", "20260621"]
if len(sys.argv) > 1:
    BACKFILL_DATES = sys.argv[1:]

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
def _repair_json(raw):
    """容忍截斷/多餘逗號等常見損壞，盡力解析。失敗回 None。"""
    if not raw:
        return None
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", raw)
    end_stripped = re.sub(r",\s*$", "", no_trailing)
    suffixes = ["", "}", "}}", "]}", "\n}", "\n}}"]
    for base in (raw, no_trailing, end_stripped):
        for suffix in suffixes:
            try:
                return json.loads(base + suffix)
            except json.JSONDecodeError:
                continue
    return None

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
        except OSError:
            continue
        parsed = _repair_json(raw)
        if parsed is not None:
            return parsed
        print(f"  ⚠️ 無法解析 {src}（已嘗試修復），改用下一個來源")
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
    """
    沿用原本可正常運作的攔截邏輯（inline 讀 body + networkidle），
    僅多回傳 had_error 供上層判斷是否重試。
    had_error=True 代表 goto / networkidle 逾時，疑似網路失敗，值得重試。
    """
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
    had_error = False
    try:
        await page.goto(url, timeout=40000, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=25000)
        except PlaywrightTimeout:
            had_error = True
        await page.wait_for_timeout(wait_ms)
    except PlaywrightTimeout:
        had_error = True
    finally:
        page.remove_listener("response", on_resp)
    return captured, had_error

# ─── 排名解析（精確比對 category + 目標日期）────────────────────────────────
SKIP_KEYS = {"apps", "categories", "chart_types", "countries", "code",
             "server_upload_time", "payload_size_bytes", "events_ingested", "lines"}

def _category_id(category_param):
    """從 "game_casino&category=all" 取出榜單分類 id "game_casino"。"""
    return category_param.split("&", 1)[0]

def _ts_to_date(ts):
    if ts > 1e12:  # 毫秒
        ts = ts / 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()

def _pick_rank_for_date(gd, target_date):
    """
    從 graphData [[ts, rank, null], ...] 取出對應 target_date 的排名。
    找不到符合日期則回 None（±1 天時區誤差才退而求其次），
    避免目標日沒進榜時誤拿鄰近日期。
    """
    if not isinstance(gd, list):
        return None
    fallback = None
    for entry in gd:
        if not (isinstance(entry, list) and len(entry) >= 2):
            continue
        ts, v = entry[0], entry[1]
        if not isinstance(v, (int, float)):
            continue
        v = int(v)
        if not (1 <= v <= 5000):
            continue
        try:
            d = _ts_to_date(ts)
        except (OverflowError, OSError, ValueError):
            continue
        if d == target_date:
            return v
        if abs((d - target_date).days) <= 1:
            fallback = v
    return fallback

def extract_rank(captured, app_id, st_country, want_category, target_date):
    for c in captured:
        body = c["body"]
        if not isinstance(body, dict):
            continue

        app_data = body.get(str(app_id))
        if app_data is None:
            for k in body:
                if k not in SKIP_KEYS:
                    app_data = body[k]
                    break
        if not isinstance(app_data, dict):
            continue

        country_data = app_data.get(st_country)
        if not isinstance(country_data, dict):
            country_data = app_data

        # 優先精確比對 category id；找不到才退而遍歷全部
        if want_category in country_data and isinstance(country_data[want_category], dict):
            cat_items = [country_data[want_category]]
        else:
            cat_items = [v for v in country_data.values() if isinstance(v, dict)]

        for cat_val in cat_items:
            for chart_val in cat_val.values():
                if not isinstance(chart_val, dict):
                    continue
                r = _pick_rank_for_date(chart_val.get("graphData"), target_date)
                if r is not None:
                    return r
    return None

# ─── 查詢單一排名 ─────────────────────────────────────────────────────────────
async def fetch_rank(context, os_type, prod, st_country, date_str):
    d = datetime.strptime(date_str, "%Y%m%d")
    target_date = d.date()
    date_api  = d.strftime("%Y-%m-%d")
    start_api = (d - timedelta(days=30)).strftime("%Y-%m-%d")
    if os_type == "ios":
        app_id = prod["apple_id"]
        want_category = _category_id(prod["apple_category"])
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=ios&start_date={start_api}&end_date={date_api}"
            f"&{prod['apple_param']}&edit=1&granularity=daily"
            f"&country={st_country}&category={prod['apple_category']}"
            f"&chart_type=free&breakdown_attribute=appId&device=iphone&selected_tab=0"
        )
    else:
        app_id = prod["android_saa"]
        want_category = _category_id(prod["android_category"])
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=android&start_date={start_api}&end_date={date_api}"
            f"&saa={app_id}&edit=1&granularity=daily"
            f"&country={st_country}&category={prod['android_category']}"
            f"&chart_type=free&breakdown_attribute=appId&device=android&selected_tab=0"
        )
    for attempt in range(1, MAX_RETRIES + 1):
        page = await context.new_page()
        try:
            captured, had_error = await capture_api(page, url)
        finally:
            await page.close()

        rank = extract_rank(captured, app_id, st_country, want_category, target_date)
        if rank is not None:
            return rank

        st_caps = [c for c in captured if "sensortower-china.com" in c["url"]]
        # 有抓到 ST 回應但解析不到 → 視為「未進榜」，不重試
        if st_caps and not had_error:
            return None
        # 疑似網路失敗 → 重試
        if attempt < MAX_RETRIES:
            await asyncio.sleep(2)
    return None

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
