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
DEBUG_FILE    = CF_DIR / "st_debug.json"   # 存完整 API 回應，方便排查

BASE_URL         = "https://app.sensortower-china.com"
APP_APPLE        = "1404165333"
APP_ANDROID_SAA  = "slots.pcg.casino.games.free.android"

# 國家對應（本地 key → Sensor Tower code）
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
            return json.loads(p.read_bytes().decode("utf-8").replace("\x00","").strip())
        except Exception:
            pass
    return default

def save_json(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

# ─── 從巢狀 JSON 中搜尋排名數字 ──────────────────────────────────────────────
def find_rank(obj, depth=0):
    if depth > 8:
        return None
    if isinstance(obj, (int, float)):
        v = int(obj)
        if 1 <= v <= 3000:
            return v
    if isinstance(obj, dict):
        for key in ("category_ranking", "category_rank", "rank",
                    "ranking", "current_rank", "free_rank", "position"):
            if key in obj:
                v = find_rank(obj[key], depth + 1)
                if v:
                    return v
        for v in obj.values():
            r = find_rank(v, depth + 1)
            if r:
                return r
    if isinstance(obj, list):
        for item in obj[:30]:
            r = find_rank(item, depth + 1)
            if r:
                return r
    return None

def find_rank_in_apple_response(body):
    """
    Apple API (api/ios/apps/<id>?country=XX) 結構解析：
    嘗試多種可能的欄位路徑來找出類別排名。
    """
    if not isinstance(body, dict):
        return None
    # 常見路徑：
    # body["category_rankings"]["free"]["rank"]
    # body["ranking"]["free"]
    # body["rankings"][0]["rank"]
    # body["rank"]
    # body["store_ranking"]
    candidates = []
    for key in ("category_rankings", "rankings", "category_rank", "store_ranking",
                "free_rank", "rank", "ranking", "current_rankings"):
        if key in body:
            val = body[key]
            # 如果是 dict，再往下一層
            if isinstance(val, dict):
                for subkey in ("free", "rank", "category_rank", "ranking", "casino"):
                    if subkey in val:
                        sv = val[subkey]
                        if isinstance(sv, (int, float)) and 1 <= int(sv) <= 3000:
                            candidates.append(int(sv))
                        elif isinstance(sv, dict):
                            for sk2 in ("rank", "ranking", "category_rank"):
                                if sk2 in sv and isinstance(sv[sk2], (int, float)):
                                    candidates.append(int(sv[sk2]))
            elif isinstance(val, list) and val:
                item = val[0]
                if isinstance(item, dict):
                    for sk in ("rank", "ranking", "category_rank", "free_rank"):
                        if sk in item and isinstance(item[sk], (int, float)):
                            candidates.append(int(item[sk]))
            elif isinstance(val, (int, float)) and 1 <= int(val) <= 3000:
                candidates.append(int(val))
    return candidates[0] if candidates else None

def find_rank_in_android_summary(body):
    """
    Android app_category_ranking_summary API 結構解析：
    通常格式: { "slots.pcg...": { "topselling_free": { "TW": {"rank": X}, ... } } }
    或: [ {"rank": X, "country": "TW", ...} ]
    """
    if isinstance(body, dict):
        # 找 app_id key
        for app_key, app_val in body.items():
            if "slots" in app_key or "casino" in app_key or "pcg" in app_key:
                r = find_rank(app_val)
                if r:
                    return r
        # 直接找 rank
        r = find_rank(body)
        return r
    if isinstance(body, list):
        for item in body[:20]:
            r = find_rank(item)
            if r:
                return r
    return None

def rank_from_text(text):
    for pat in [
        r'"category_rank(?:ing)?"\s*:\s*(\d+)',
        r'"free_rank"\s*:\s*(\d+)',
        r'"rank"\s*:\s*(\d+)',
        r'#\s*(\d+)\s+(?:in|In)\s+(?:Casino|Free|Games)',
    ]:
        m = re.search(pat, text)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 3000:
                return v
    return None

# ─── 前往頁面 + 攔截所有 JSON API 回應 ───────────────────────────────────────
async def capture_api(page, url, wait_ms=5000):
    captured = []

    async def on_resp(resp):
        if "json" not in resp.headers.get("content-type", ""):
            return
        try:
            body = await resp.json()
            captured.append({"url": resp.url, "body": body})
        except Exception:
            pass

    page.on("response", on_resp)
    try:
        await page.goto(url, timeout=35000, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=20000)
        await page.wait_for_timeout(wait_ms)
    except PlaywrightTimeout:
        pass
    finally:
        page.remove_listener("response", on_resp)

    # 印出所有 API URL（debug 用）
    for c in captured:
        print(f"    [API] {c['url'][-80:]}")

    return captured

# ─── Apple App Store 排名 ─────────────────────────────────────────────────────
async def get_apple_rank(page, st_country, debug):
    url = f"{BASE_URL}/overview/{APP_APPLE}?country={st_country}"
    print(f"  [Apple/{st_country}] 抓取中...")
    captured = await capture_api(page, url, wait_ms=4000)

    # 儲存 sensortower 的回應供分析
    debug[f"apple_{st_country}"] = [
        {"url": c["url"], "body_sample": str(c["body"])[:3000]}
        for c in captured
        if "sensortower" in c["url"].lower()
    ]

    # 只處理 sensortower 自己的 API（排除第三方 analytics）
    st_responses = [c for c in captured if "sensortower-china.com/api" in c["url"]]
    if not st_responses:
        st_responses = captured  # fallback

    for c in st_responses:
        # 先用 Apple 專用解析
        r = find_rank_in_apple_response(c["body"])
        if r:
            print(f"    → #{r}  (apple-parser, API: ...{c['url'][-50:]})")
            return r
        # 再用通用解析
        r = find_rank(c["body"])
        if r:
            print(f"    → #{r}  (generic, API: ...{c['url'][-50:]})")
            return r

    try:
        content = await page.content()
        r = rank_from_text(content)
        if r:
            print(f"    → #{r}  (DOM)")
            return r
    except Exception:
        pass

    print(f"    → 未找到排名")
    return None

# ─── Google Play 排名 ─────────────────────────────────────────────────────────
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
    captured = await capture_api(page, url, wait_ms=5000)

    # 儲存 sensortower API 回應
    debug[f"android_{st_country}"] = [
        {"url": c["url"], "body_sample": str(c["body"])[:3000]}
        for c in captured
        if "sensortower" in c["url"].lower() or c["url"].startswith("/api/")
    ]

    # 優先處理 category_ranking_summary 端點
    ranking_responses = [c for c in captured
                         if "category_ranking_summary" in c["url"]
                         or "category_ranking" in c["url"]]
    if not ranking_responses:
        # fallback：排除明確無關的端點
        skip = {"internal_entities", "amplitude", "bugsnag", "osano", "sr-client"}
        ranking_responses = [c for c in captured
                             if not any(s in c["url"] for s in skip)]

    for c in ranking_responses:
        r = find_rank_in_android_summary(c["body"])
        if r:
            print(f"    → #{r}  (android-parser, API: ...{c['url'][-60:]})")
            return r
        r = find_rank(c["body"])
        if r:
            print(f"    → #{r}  (generic, API: ...{c['url'][-60:]})")
            return r

    try:
        content = await page.content()
        r = rank_from_text(content)
        if r:
            print(f"    → #{r}  (DOM)")
            return r
    except Exception:
        pass

    print(f"    → 未找到排名")
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

    print(f"\n📋 st_debug.json 已儲存，可用來分析 API 回應結構")

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
