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
DEBUG_FILE    = CF_DIR / "st_debug.json"   # 存 API URL，方便排查

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

    return captured

# ─── Apple App Store 排名 ─────────────────────────────────────────────────────
async def get_apple_rank(page, st_country, debug):
    url = f"{BASE_URL}/overview/{APP_APPLE}?country={st_country}"
    print(f"  [Apple/{st_country}] 抓取中...")
    captured = await capture_api(page, url, wait_ms=4000)
    debug[f"apple_{st_country}"] = [c["url"] for c in captured]

    for c in captured:
        r = find_rank(c["body"])
        if r:
            print(f"    → #{r}  (API: ...{c['url'][-50:]})")
            return r

    # fallback: DOM 全文搜尋
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
    debug[f"android_{st_country}"] = [c["url"] for c in captured]

    for c in captured:
        r = find_rank(c["body"])
        if r:
            print(f"    → #{r}  (API: ...{c['url'][-50:]})")
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
