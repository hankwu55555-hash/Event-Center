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

import os
import re
import sys
import json
import shutil
import asyncio
import logging
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeout,
)

# ─── 設定 ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scrape")

REPO_DIR = Path(__file__).parent
CF_RANKINGS_FILE = REPO_DIR / "CF" / "rankings.json"
DAFU_RANKINGS_FILE = REPO_DIR / "Dafu" / "rankings.json"
DEBUG_FILE = REPO_DIR / "st_debug.json"

BASE_URL = "https://app.sensortower-china.com"

# 逾時 / 等待參數（毫秒）
GOTO_TIMEOUT = 40000
API_WAIT_TIMEOUT = 25000   # 等待目標 API 回應出現的上限
SETTLE_MS = 4000           # API 出現後再多等一下，讓相關回應都到齊
MAX_RETRIES = 2            # 疑似網路失敗時的重試次數
TARGET_API = "category_history"   # 目標 API 在 URL 中的識別字串

# Cash Frenzy
CF_APP_APPLE = "1404165333"
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
# apple_category / android_category 格式： "<chart_category>&category=<sub>"
#   - 前段（&前）為榜單分類 id，用來在回應中精確比對
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


def category_id(category_param):
    """從 "game_casino&category=all" 取出榜單分類 id "game_casino"。"""
    return category_param.split("&", 1)[0]


# ─── JSON 工具（原子寫入 + 自動修復）─────────────────────────────────────────
def _repair_json(raw):
    """
    容忍常見損壞後盡力解析：
      - 結尾被截斷（缺收尾括號）
      - 物件/陣列結尾前的多餘逗號，或檔尾懸空的逗號
    成功回傳物件，全部失敗回 None。
    """
    if not raw:
        return None
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", raw)        # 去掉 } 或 ] 前的逗號
    end_stripped = re.sub(r",\s*$", "", no_trailing)         # 去掉檔尾懸空逗號
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
        except OSError as e:
            log.warning("讀取 %s 失敗：%s", src, e)
            continue
        parsed = _repair_json(raw)
        if parsed is not None:
            return parsed
        log.warning("無法解析 %s（已嘗試修復），改用下一個來源", src)
    return default


def save_json(path, data):
    """原子寫入：先寫 .tmp，驗證後 rename，並保留 .bak 備份。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    json.loads(content)  # 驗證資料可被正確讀回
    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if p.exists():
        shutil.copy2(p, str(p) + ".bak")
    os.replace(tmp, p)


# ─── 前往頁面並攔截所有 JSON API 回應 ────────────────────────────────────────
async def capture_api(page, url):
    """
    前往 url 並攔截所有 JSON 回應，明確等待目標 API（category_history）出現。
    回傳 (captured, had_error)：
      - captured: [{"url", "body"}, ...]
      - had_error: True 代表逾時/載入失敗，疑似網路失敗（值得重試）
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
        await page.goto(url, timeout=GOTO_TIMEOUT, wait_until="domcontentloaded")
        # 明確等待目標 API 出現（輪詢已攔截清單），取代不可靠的 networkidle
        waited = 0
        step = 500
        while waited < API_WAIT_TIMEOUT:
            if any(TARGET_API in c["url"] for c in captured):
                break
            await page.wait_for_timeout(step)
            waited += step
        else:
            had_error = True
            log.warning("    等待 %s 逾時", TARGET_API)
        # 目標出現後再多等一下，讓同批相關回應到齊
        await page.wait_for_timeout(SETTLE_MS)
    except PlaywrightTimeout:
        had_error = True
        log.warning("    頁面載入逾時：%s", url[-80:])
    finally:
        page.remove_listener("response", on_resp)

    for c in captured:
        log.info("    [API] %s", c["url"][-80:])

    return captured, had_error


# ─── 解析 category_history 回應 ──────────────────────────────────────────────
SKIP_KEYS = {
    "apps", "categories", "chart_types", "countries", "code",
    "server_upload_time", "payload_size_bytes", "events_ingested", "lines",
}


def _ts_to_date(ts):
    """graphData 的 timestamp（毫秒或秒）轉成 UTC date。"""
    if ts > 1e12:  # 毫秒
        ts = ts / 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def _pick_rank_for_date(graph_data, target_date):
    """
    從 graphData 取出對應 target_date 的排名。
    graphData 形如 [[timestamp, rank, null], ...]。
    找不到符合日期的點則回傳 None（不硬拿最後一筆，避免拿到舊日期）。
    """
    fallback = None
    for point in graph_data:
        if not (isinstance(point, list) and len(point) >= 2):
            continue
        ts, rank = point[0], point[1]
        if not isinstance(rank, (int, float)):
            continue
        rank = int(rank)
        if not (1 <= rank <= 5000):
            continue
        try:
            pt_date = _ts_to_date(ts)
        except (OverflowError, OSError, ValueError):
            continue
        if pt_date == target_date:
            return rank
        # 容忍 ±1 天時區誤差，但僅作為退而求其次
        if abs((pt_date - target_date).days) <= 1:
            fallback = rank
    return fallback


def _parse_category_history(captured, app_id, st_country, want_category, target_date, allow_todays_rank=False):
    """
    category_history API 結構：
      { "<app_id>": { "<country>": { "<category_id>": { "<chart_type>": {
            "todays_rank": 75,
            "graphData": [[ts, rank, null], ...] } } } }, "lines": [...] }

    ⚠️ 不用 todays_rank：它永遠是即時排名，查歷史日期會回傳今天的值。
    ⚠️ 精確比對 want_category 與 target_date，避免抓錯榜單或錯日期。
    """
    todays_fallback = None
    for c in captured:
        body = c["body"]
        if not isinstance(body, dict) or "category_history" not in c["url"]:
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
        cat_items = []
        if want_category in country_data and isinstance(country_data[want_category], dict):
            cat_items = [country_data[want_category]]
        else:
            cat_items = [v for v in country_data.values() if isinstance(v, dict)]

        for cat_val in cat_items:
            for chart_val in cat_val.values():
                if not isinstance(chart_val, dict):
                    continue
                gd = chart_val.get("graphData")
                if isinstance(gd, list) and gd:
                    rank = _pick_rank_for_date(gd, target_date)
                    if rank is not None:
                        return rank
                # 抓「今天」時 graphData 常還沒今天的點 → 改用即時的 todays_rank
                # （等同 end_date=今天 的值；歷史日期不可用，故由 allow_todays_rank 控制）
                if allow_todays_rank and todays_fallback is None:
                    tr = chart_val.get("todays_rank")
                    if isinstance(tr, (int, float)) and 1 <= int(tr) <= 5000:
                        todays_fallback = int(tr)
    return todays_fallback


def _make_debug_entries(st_caps, app_id):
    entries = []
    for c in st_caps:
        body = c["body"]
        entry = {"url": c["url"][-90:]}
        if isinstance(body, dict):
            entry["body_keys"] = list(body.keys())
            if "category_history" in c["url"]:
                app_data = body.get(str(app_id))
                if app_data is None:
                    for k in body:
                        if k not in SKIP_KEYS:
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


# ─── 組 URL ──────────────────────────────────────────────────────────────────
def _build_url(os_type, st_country, target_date, prod_cfg):
    """回傳 (url, app_id, want_category)。"""
    end_api = target_date.strftime("%Y-%m-%d")
    # 放寬查詢區間（原本只查前 1 天），讓 graphData 多幾個點，提高命中目標日的機率
    start_api = (target_date - timedelta(days=7)).strftime("%Y-%m-%d")

    if os_type == "ios":
        if prod_cfg["apple_sia"]:
            id_param = f"sia={prod_cfg['apple_sia']}"
            app_id = prod_cfg["apple_sia"]
        else:
            id_param = f"app_id={prod_cfg['apple_id']}"
            app_id = prod_cfg["apple_id"]
        category = prod_cfg["apple_category"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=ios&start_date={start_api}&end_date={end_api}"
            f"&{id_param}&granularity=daily"
            f"&country={st_country}&category={category}"
            f"&chart_type=free&breakdown_attribute=appId"
            f"&device=iphone&selected_tab=0"
        )
    else:
        app_id = prod_cfg["android_saa"]
        category = prod_cfg["android_category"]
        url = (
            f"{BASE_URL}/app-analysis/category-rankings"
            f"?os=android&start_date={start_api}&end_date={end_api}"
            f"&saa={app_id}&granularity=daily"
            f"&country={st_country}&category={category}"
            f"&chart_type=free&breakdown_attribute=appId"
            f"&device=android&selected_tab=0"
        )
    return url, app_id, category_id(category)


# ─── 單一日期排名抓取（Apple / Android 共用）────────────────────────────────
async def fetch_rank(page, os_type, st_country, target_date, debug, debug_key, prod_cfg):
    url, app_id, want_category = _build_url(os_type, st_country, target_date, prod_cfg)
    allow_today = target_date == date.today()

    for attempt in range(1, MAX_RETRIES + 1):
        captured, had_error = await capture_api(page, url)
        st_caps = [c for c in captured if "sensortower-china.com" in c["url"]]
        debug[debug_key] = _make_debug_entries(st_caps, app_id)

        rank = _parse_category_history(captured, app_id, st_country, want_category, target_date, allow_today)
        if rank is not None:
            return rank

        # 有抓到 ST 回應但解析不到 → 視為「未進榜」，不重試
        if st_caps and not had_error:
            return None

        # 疑似網路失敗 → 重試
        if attempt < MAX_RETRIES:
            log.warning("    第 %d 次未取得資料（疑似網路失敗），重試...", attempt)
            await page.wait_for_timeout(2000)

    return None


async def get_rank(page, os_type, st_country, debug, target_date, prod_cfg):
    label = target_date.strftime("%Y%m%d")
    tag = "Apple" if os_type == "ios" else "Android"
    log.info("  [%s/%s/%s/%s] 抓取中...", tag, prod_cfg["name"], st_country, label)
    debug_key = f"{'apple' if os_type == 'ios' else 'android'}_{st_country}_{label}"
    r = await fetch_rank(page, os_type, st_country, target_date, debug, debug_key, prod_cfg)
    log.info("    → %s", f"#{r}" if r else "未找到排名")
    return r


# ─── 處理單一日期（今天/昨天共用）────────────────────────────────────────────
async def process_date(page, rankings, target_date, debug, prod):
    date_key = target_date.strftime("%Y%m%d")
    log.info("📅 %s", date_key)
    rankings.setdefault(date_key, {})
    for local_key, st_country in COUNTRIES.items():
        entry = rankings[date_key].setdefault(local_key, {})
        for os_type, field in (("ios", "apple"), ("android", "android")):
            if field in entry:
                log.info("  [%s/%s] 已有資料 #%s，跳過", field, local_key, entry[field])
                continue
            r = await get_rank(page, os_type, st_country, debug, target_date, prod)
            if r is not None:
                entry[field] = r


# ─── 主流程 ──────────────────────────────────────────────────────────────────
async def main():
    today = date.today()
    yesterday = today - timedelta(days=1)
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
        # 暖機
        warmup = await context.new_page()
        try:
            await warmup.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
            await warmup.wait_for_timeout(3000)
        except PlaywrightTimeout:
            log.warning("暖機逾時，繼續執行")
        except Exception as e:  # noqa: BLE001
            log.warning("暖機失敗：%s", e)
        finally:
            await warmup.close()

        page = await context.new_page()

        for prod in PRODUCTS:
            rankings = load_json(prod["rankings_file"], {})
            log.info("%s", "=" * 50)
            log.info("🎮 %s", prod["name"])
            log.info("%s", "=" * 50)

            await process_date(page, rankings, today, debug, prod)
            await process_date(page, rankings, yesterday, debug, prod)

            save_json(prod["rankings_file"], rankings)
            log.info("%s rankings.json updated", prod["name"])

        await context.close()
        await browser.close()

    save_json(DEBUG_FILE, debug)

    gallery = REPO_DIR / "generate_gallery.py"
    if gallery.exists():
        r = subprocess.run(
            [sys.executable, str(gallery)],
            capture_output=True, text=True, cwd=str(REPO_DIR),
        )
        if r.stdout.strip():
            log.info(r.stdout.strip())
        if r.returncode != 0:
            log.error("generate_gallery.py 失敗：%s", r.stderr[:300])
    else:
        log.warning("找不到 generate_gallery.py，略過")


if __name__ == "__main__":
    asyncio.run(main())