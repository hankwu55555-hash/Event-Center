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

CF_DIR        = Path(__file__).parent
RANKINGS_FILE = CF_DIR / "rankings.json"
DEBUG_FILE    = CF_DIR / "st_debug.json"

BASE_URL        = "https://app.sensortower-china.com"
APP_APPLE       = "1404165333"
APP_ANDROID_SAA = "slots.pcg.casino.games.free.android"

COUNTRIES = {
    "TW": "TW",
    "US": "US",
    "JP": "JP",
    "UK": "GB",
}

# ─── JSON 工具 ────────────────────────────────────────────────────────────────
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


# ─── Apple App Store 類別排名 ────────────────────────────────────────────────
async def get_apple_rank(page, st_country, debug):
    """
    改用 app-analysis/category-rankings (iOS 版)，
    這與 Android 相同的頁面，會觸發 category_ranking_summary API。
    """
    today     = date.today().strftime("%Y-%m-%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = (
        f"{BASE_URL}/app-analysis/category-rankings"
        f"?os=ios&start_date={yesterday}&end_date={today}"
        f"&app_id={APP_APPLE}&granularity=daily"
        f"&country={st_country}&category=game_casino&category=all"
        f"&chart_type=free&breakdown_attribute=appId"
        f"&device=iphone&selected_tab=0"
    )
    print(f"  [Apple/{st_country}] 抓取中...")
    captured = await capture_api(page, url, wait_ms=6000)

    # 儲存 sensortower API 回應
    st_caps = [c for c in captured if "sensortower-china.com" in c["url"]]
    debug[f"apple_{st_country}"] = _make_debug_entries(st_caps, APP_APPLE)

    # 從 category_history 回應中解析排名
    r = _parse_category_history(captured, APP_APPLE, debug_label=f"apple_{st_country}")
    if r is not None:
        print(f"    → #{r}")
        return r

    print(f"    → 未找到排名")
    return None

# ─── Google Play 類別排名 ─────────────────────────────────────────────────────
async def get_android_rank(page, st_country, debug):
    today     = date.today().strftime("%Y-%m-%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = (
        f"{BASE_URL}/app-analysis/category-rankings"
        f"?os=android&start_date={yesterday}&end_date={today}"
        f"&saa={APP_ANDROID_SAA}&granularity=daily"
        f"&country={st_country}&category=game_casino&category=all"
        f"&chart_type=free&breakdown_attribute=appId"
        f"&device=android&selected_tab=0"
    )
    print(f"  [Android/{st_country}] 抓取中...")
    captured = await capture_api(page, url, wait_ms=6000)

    st_caps = [c for c in captured if "sensortower-china.com" in c["url"]]
    debug[f"android_{st_country}"] = _make_debug_entries(st_caps, APP_ANDROID_SAA)

    r = _parse_category_history(captured, APP_ANDROID_SAA, debug_label=f"android_{st_country}")
    if r is not None:
        print(f"    → #{r}")
        return r

    print(f"    → 未找到排名")
    return None


def _parse_category_history(captured, app_id, debug_label=""):
    """
    category_history API 回應結構：
      { "<app_id>": [ {date, rank, ...}, ... ], "lines": [...] }
    取最新一筆（最後一個 date）的 rank 值。
    """
    history_caps = [c for c in captured if "category_history" in c["url"]]
    for c in history_caps:
        body = c["body"]
        if not isinstance(body, dict):
            continue
        # app_id 作為 key
        app_data = body.get(app_id) or body.get(str(app_id))
        if app_data is None:
            # 嘗試找唯一的非 "lines" key
            keys = [k for k in body if k != "lines"]
            if len(keys) == 1:
                app_data = body[keys[0]]

        if app_data is None:
            continue

        # app_data 可能是 list of dicts: [{date, rank}, ...]
        if isinstance(app_data, list) and app_data:
            # 取最後一筆（最新日期）
            for entry in reversed(app_data):
                if isinstance(entry, dict):
                    for key in ("rank", "category_rank", "ranking", "position"):
                        if key in entry:
                            v = entry[key]
                            if isinstance(v, (int, float)) and 1 <= int(v) <= 5000:
                                return int(v)
        # 也嘗試 generic find_rank
        r = find_rank(app_data)
        if r:
            return r

    return None

# ─── 主流程 ──────────────────────────────────────────────────────────────────
async def main():
    today_key = date.today().strftime("%Y%m%d")
    rankings  = load_json(RANKINGS_FILE, {})
    if today_key not in rankings:
        rankings[today_key] = {}

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

        for local_key, st_country in COUNTRIES.items():
            print(f"\n── {local_key} ({st_country}) ──────────────────")
            entry = rankings[today_key].setdefault(local_key, {})

            apple   = await get_apple_rank(page, st_country, debug)
            android = await get_android_rank(page, st_country, debug)

            if apple   is not None: entry["apple"]   = apple
            if android is not None: entry["android"] = android

        await browser.close()

    save_json(RANKINGS_FILE, rankings)
    save_json(DEBUG_FILE, debug)

    print(f"\n✅ rankings.json 更新完成（{today_key}）")
    print(json.dumps(rankings.get(today_key, {}), ensure_ascii=False, indent=2))

    # 自動重新產生 gallery + git push
    import subprocess
    r = subprocess.run(
        [sys.executable, str(CF_DIR / "generate_gallery.py")],
        capture_output=True, text=True, cwd=str(CF_DIR)
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print("[錯誤]", r.stderr[:300])

if __name__ == "__main__":
    asyncio.run(main())
