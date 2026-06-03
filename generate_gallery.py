#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CF Screenshot Gallery Generator"""
import re, json
from pathlib import Path
from datetime import datetime
from PIL import Image

WEBSITE_DIR   = Path(__file__).parent
EVENT_CENTER  = WEBSITE_DIR.parent
ONEDRIVE      = Path("C:/Users/hankwu/OneDrive - International Games System/Event_Center")
OUTPUT_HTML   = WEBSITE_DIR / "gallery.html"
CACHE_FILE    = WEBSITE_DIR / "tab_names_cache.json"

# (顯示名稱, 來源資料夾, 圖片URL前綴, 排名JSON路徑, 自動偵測頁籤名稱)
PRODUCTS = [
    ("Cash Frenzy", ONEDRIVE / "CF",   "CF/",   EVENT_CENTER / "CF"   / "rankings.json", True),
    ("大福娛樂城",   ONEDRIVE / "Dafu", "Dafu/", EVENT_CENTER / "Dafu" / "rankings.json", False),
]

SIDEBAR_X = 200
SIDEBAR_HEADER = 80
LIGHT_THRESHOLD = 180

ZONE_NAMES_MAP = {
    3: {1: "促銷", 2: "活動", 3: "公告"},
    4: {1: "促銷", 2: "特別", 3: "活動", 4: "公告"},
}
DEFAULT_ZONE_NAMES = ZONE_NAMES_MAP[3]

def detect_active_zone(img_path, n_tabs=3):
    try:
        img = Image.open(img_path).convert("RGB")
        _, h = img.size
        zone_divisor = n_tabs + 1
        zone_h = (h - SIDEBAR_HEADER) // zone_divisor
        best_zone, best_count = 1, 0
        for z in range(n_tabs):
            y0 = SIDEBAR_HEADER + z * zone_h
            y1 = y0 + zone_h
            region = img.crop((0, y0, SIDEBAR_X, y1))
            count = sum(1 for p in region.getdata()
                        if p[0] >= LIGHT_THRESHOLD and p[1] >= LIGHT_THRESHOLD and p[2] >= LIGHT_THRESHOLD)
            if count > best_count:
                best_count = count
                best_zone = z + 1
        return best_zone
    except Exception as e:
        print(f"  [warn] {img_path.name}: {e}")
        return 0

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_bytes().decode("utf-8").replace("\x00","").strip())
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def load_rankings(path=None):
    p = Path(path) if path else RANKINGS_FILE
    if p.exists():
        try:
            return json.loads(p.read_bytes().decode("utf-8").replace("\x00","").strip())
        except Exception:
            return {}
    return {}

def get_tab_label(date_str, tab_key, first_img, cache, n_tabs=3, prod_key="p0", auto_detect=True):
    key = f"{prod_key}/{date_str}/{tab_key}"
    if key in cache:
        return cache[key]
    if not auto_detect:
        label = f"頁籤{tab_key.replace('tab','')}"
        cache[key] = label
        return label
    print(f"  偵測：{key} ...")
    zone = detect_active_zone(first_img, n_tabs=n_tabs)
    zone_names = ZONE_NAMES_MAP.get(n_tabs, DEFAULT_ZONE_NAMES)
    label = zone_names.get(zone, f"頁籤{tab_key.replace('tab','')}")
    cache[key] = label
    print(f"    Zone {zone} → {label}")
    return label

def scan_folders(base_dir=None):
    if base_dir is None:
        base_dir = WEBSITE_DIR
    data = {}
    if not base_dir.exists():
        return data
    for item in sorted(base_dir.iterdir(), reverse=True):
        if item.is_dir() and re.match(r'^\d{8}$', item.name):
            tabs = {}
            for img in sorted(item.iterdir(),
                              key=lambda x: int(re.search(r'_(\d+)\.', x.name).group(1))
                              if re.search(r'_(\d+)\.', x.name) else 0):
                if img.suffix.lower() in ['.png','.jpg','.jpeg','.gif','.webp']:
                    m = re.match(r'^(tab\d+)_\d+\..+$', img.name, re.I)
                    if m:
                        tabs.setdefault(m.group(1).lower(), []).append(img)
            if tabs:
                data[item.name] = tabs
    return data


def fmt_date(s):
    try:
        return datetime.strptime(s, "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        return s

_CSS = """
:root{--bg:#0d0020;--sf:#1e0045;--sf2:#2a0060;--ac:#a855f7;--ac2:#7c3aed;--ac3:#c084fc;--glow:rgba(168,85,247,.4);--tx:#f0e6ff;--tx2:#c4a8e8;--bd:#3d1a6e;--r:10px;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--tx);font-family:'Segoe UI','Microsoft JhengHei',sans-serif;min-height:100vh;}
header{background:linear-gradient(135deg,#1a0040,#2d006a);border-bottom:2px solid var(--ac);padding:14px 28px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 20px rgba(168,85,247,.3);}
.logo-area{display:flex;align-items:center;gap:10px;}
.logo{display:flex;align-items:center;gap:12px;text-decoration:none;}
.logo img{width:44px;height:44px;border-radius:10px;box-shadow:0 0 12px rgba(168,85,247,.5);}
.logo span{font-size:1.4rem;font-weight:bold;color:#fde047;letter-spacing:2px;text-shadow:0 0 16px rgba(253,224,71,.6);}
.prod-toggle{position:relative;}
.prod-toggle-btn{background:rgba(168,85,247,.25);border:1px solid var(--bd);color:var(--tx2);width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:1rem;display:flex;align-items:center;justify-content:center;transition:all .2s;padding:0;}
.prod-toggle-btn:hover{background:var(--ac2);border-color:var(--ac);color:#fff;}
.prod-popup{display:none;position:absolute;left:0;top:calc(100% + 8px);background:var(--sf2);border:2px solid var(--ac);border-radius:var(--r);padding:8px;min-width:160px;box-shadow:0 8px 40px rgba(168,85,247,.5);z-index:999;}
.prod-popup.open{display:block;}
.prod-opt{padding:9px 16px;border-radius:8px;cursor:pointer;color:var(--tx);font-size:.9rem;font-weight:600;transition:all .15s;white-space:nowrap;}
.prod-opt:hover{background:var(--ac2);color:#fff;}
.prod-opt.on{background:linear-gradient(135deg,#f59e0b,#fde047);color:#1a0a00;}
.header-right{display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
.cal-wrap{position:relative;}
.country-sel{display:flex;align-items:center;}
.csel-wrap{position:relative;}
.csel-popup{display:none;position:absolute;left:0;top:calc(100% + 10px);background:var(--sf2);border:2px solid var(--ac);border-radius:var(--r);padding:8px;min-width:140px;box-shadow:0 8px 40px rgba(168,85,247,.5);z-index:999;}
.csel-popup.open{display:block;}
.csel-opt{padding:9px 16px;border-radius:8px;cursor:pointer;color:var(--tx);font-size:.9rem;font-weight:600;transition:all .15s;white-space:nowrap;}
.csel-opt:hover{background:var(--ac2);color:#fff;}
.csel-opt.on{background:linear-gradient(135deg,#f59e0b,#fde047);color:#1a0a00;}
.header-center{display:flex;align-items:center;gap:10px;flex:1;justify-content:center;flex-wrap:wrap;}
.rank-label{font-size:.8rem;color:var(--tx2);white-space:nowrap;letter-spacing:1px;}
.rank-badge{display:flex;align-items:center;gap:7px;background:var(--sf);border:1px solid var(--bd);border-radius:20px;padding:0 15px;height:40px;box-sizing:border-box;transition:all .25s;}
.rank-badge .s-icon{width:20px;height:20px;flex-shrink:0;}
.rank-badge .s-name{font-size:.72rem;color:var(--tx2);}
.rank-badge .r-num{font-size:1.1rem;font-weight:bold;color:var(--tx2);min-width:28px;text-align:right;}
.rank-badge.live .r-num{color:#fde047;text-shadow:0 0 8px rgba(253,224,71,.6);}
.cal-btn{background:linear-gradient(135deg,#f59e0b,#fde047);color:#1a0a00;border:none;padding:0 20px;border-radius:20px;cursor:pointer;font-size:.9rem;font-weight:bold;display:flex;align-items:center;justify-content:center;gap:8px;box-shadow:0 0 14px rgba(245,158,11,.5);transition:all .2s;white-space:nowrap;height:40px;box-sizing:border-box;}
.cal-btn:hover{box-shadow:0 0 22px rgba(245,158,11,.8);transform:scale(1.04);}
.cal-popup{display:none;position:absolute;right:0;top:calc(100% + 10px);background:var(--sf2);border:2px solid var(--ac);border-radius:var(--r);padding:18px;min-width:290px;box-shadow:0 8px 40px rgba(168,85,247,.5);z-index:999;}
.cal-popup.open{display:block;}
.cal-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
.cal-nav button{background:var(--sf);border:1px solid var(--bd);color:var(--tx);width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:1.2rem;line-height:1;transition:all .2s;}
.cal-nav button:hover{background:var(--ac2);border-color:var(--ac);color:#fff;}
.cal-nav span{font-weight:bold;color:var(--ac3);font-size:1rem;}
.cal-dow{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;margin-bottom:6px;}
.cal-dow span{font-size:.72rem;color:var(--tx2);padding:2px 0;}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;}
.cal-cell{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:8px;font-size:.85rem;cursor:default;color:rgba(255,255,255,.2);transition:all .2s;}
.cal-cell.has-data{background:rgba(168,85,247,.25);color:var(--tx);cursor:pointer;border:1px solid var(--bd);font-weight:600;}
.cal-cell.has-data:hover{background:var(--ac2);border-color:var(--ac);color:#fff;box-shadow:0 0 8px var(--glow);}
.cal-cell.selected{background:linear-gradient(135deg,#f59e0b,#fde047)!important;color:#1a0a00!important;border-color:#fde047!important;font-weight:bold;box-shadow:0 0 12px rgba(245,158,11,.6);}
.ats{display:flex;gap:8px;flex-wrap:wrap;padding:18px 28px 0;justify-content:center;}
.at{background:var(--sf);color:var(--tx2);border:1px solid var(--bd);padding:6px 18px;border-radius:20px;cursor:pointer;font-size:.9rem;transition:all .2s;}
.at:hover{background:#78350f;color:#fff;border-color:#fde047;}
.at.on{background:linear-gradient(135deg,#f59e0b,#fde047);color:#1a0a00;border-color:#fde047;font-weight:bold;box-shadow:0 0 14px rgba(245,158,11,.5);}
.dp{display:none;}.dp.on{display:block;}
.viewer{display:flex;align-items:center;justify-content:center;padding:20px 28px;gap:16px;min-height:60vh;}
.arrow{background:linear-gradient(135deg,#92400e,#78350f);border:2px solid #fde047;color:#fff176;width:52px;height:52px;border-radius:50%;font-size:1.4rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;flex-shrink:0;box-shadow:0 2px 12px rgba(0,0,0,.4);}
.arrow:hover{background:linear-gradient(135deg,#f59e0b,#fde047);border-color:#fde047;box-shadow:0 0 20px rgba(245,158,11,.5);transform:scale(1.1);}
.arrow.hidden{opacity:0;pointer-events:none;}
.main-img-wrap{flex:1;max-width:860px;display:flex;flex-direction:column;align-items:center;gap:14px;}
.main-img-wrap img{width:100%;max-height:62vh;object-fit:contain;border-radius:var(--r);border:2px solid var(--bd);box-shadow:0 4px 40px rgba(168,85,247,.25);background:var(--sf);}
.counter{font-size:.88rem;color:#1a0a00;font-weight:bold;background:linear-gradient(135deg,#f59e0b,#fde047);border:1px solid #fde047;padding:4px 16px;border-radius:20px;box-shadow:0 0 10px rgba(245,158,11,.4);}
.thumbs{display:flex;gap:8px;padding:0 28px 24px;justify-content:center;overflow-x:auto;scrollbar-width:thin;scrollbar-color:var(--bd) transparent;}
.thumbs::-webkit-scrollbar{height:4px;}.thumbs::-webkit-scrollbar-thumb{background:var(--bd);border-radius:2px;}
.loading-overlay{display:none;position:fixed;inset:0;background:rgba(13,0,32,.82);z-index:9999;flex-direction:column;align-items:center;justify-content:center;gap:18px;}
.loading-overlay.show{display:flex;}
.spinner{width:56px;height:56px;border:4px solid rgba(168,85,247,.2);border-top:4px solid #a855f7;border-radius:50%;animation:spin .75s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}
.loading-text{color:#c084fc;font-size:.95rem;letter-spacing:3px;font-weight:600;}
.thumb{width:100px;height:56px;flex-shrink:0;border-radius:6px;overflow:hidden;cursor:pointer;border:2px solid transparent;transition:all .2s;opacity:.6;}
.thumb:hover{opacity:1;border-color:var(--ac2);}.thumb.on{opacity:1;border-color:var(--ac);box-shadow:0 0 10px var(--glow);}
.thumb img{width:100%;height:100%;object-fit:cover;display:block;}
"""

_JS_TMPL = """
const ALL_DATA     = %ALL_DATA%;
const ALL_RANKINGS = %ALL_RANKINGS%;
let curProdKey  = '%FIRST_KEY%';
let IMGS        = ALL_DATA[curProdKey].imgs;
let AVAIL_DATES = ALL_DATA[curProdKey].dates;
let curCountry  = 'TW';
let curDate='', curTab='', curIdx=0, calYear=0, calMonth=0;

function togglePpopup(){document.getElementById('prod-popup').classList.toggle('open');}
function toggleCsel(){document.getElementById('cselPopup').classList.toggle('open');}

function selectProduct(pk){
  if(pk===curProdKey){document.getElementById('prod-popup').classList.remove('open');return;}
  curProdKey=pk; IMGS=ALL_DATA[pk].imgs; AVAIL_DATES=ALL_DATA[pk].dates;
  document.querySelectorAll('.prod-opt').forEach(o=>o.classList.remove('on'));
  const opt=document.querySelector('.prod-opt[data-pk="'+pk+'"]');
  if(opt) opt.classList.add('on');
  document.getElementById('prod-popup').classList.remove('open');
  document.querySelectorAll('.dp').forEach(p=>{p.classList.remove('on');p.style.display='none';});
  document.querySelectorAll('.dp[data-prod="'+pk+'"]').forEach(p=>{p.style.display='';});
  const nd=AVAIL_DATES[0]||''; curDate=nd;
  if(nd){
    document.getElementById('calBtnTxt').textContent=fmtDateBtn(nd);
    const panel=document.getElementById('dp-'+pk+'-'+nd);
    if(panel){panel.classList.add('on');panel.style.display='';}
    switchAct(nd,Object.keys(IMGS[nd])[0]);
  }
  updateRankings(); renderCal();
}

function selectCountry(c){
  curCountry=c;
  const L={'TW':'台灣','US':'美國','JP':'日本','UK':'英國'};
  document.getElementById('cselBtnTxt').textContent=L[c]||c;
  document.querySelectorAll('.csel-opt').forEach(o=>o.classList.remove('on'));
  const opt=document.querySelector('.csel-opt[data-c="'+c+'"]');
  if(opt) opt.classList.add('on');
  document.getElementById('cselPopup').classList.remove('open');
  updateRankings();
}

function updateRankings(){
  const prodR=(ALL_RANKINGS[curProdKey]||{});
  const r=prodR[curDate]&&prodR[curDate][curCountry];
  const ae=document.getElementById('rankApple'), ge=document.getElementById('rankAndroid');
  const an=document.getElementById('rApple'), gn=document.getElementById('rAndroid');
  if(r&&r.apple){an.textContent='#'+r.apple; ae.classList.add('live');}
  else{an.textContent='--'; ae.classList.remove('live');}
  if(r&&r.android){gn.textContent='#'+r.android; ge.classList.add('live');}
  else{gn.textContent='--'; ge.classList.remove('live');}
}

function fmtDateBtn(s){return s.slice(0,4)+'/'+s.slice(4,6)+'/'+s.slice(6,8);}

function toggleCal(){
  const p=document.getElementById('calPopup');
  if(p.classList.contains('open')){p.classList.remove('open');}
  else{const d=curDate||AVAIL_DATES[0];if(!d)return;calYear=parseInt(d.slice(0,4));calMonth=parseInt(d.slice(4,6))-1;renderCal();p.classList.add('open');}
}
function changeMonth(dir){
  calMonth+=dir;
  if(calMonth<0){calMonth=11;calYear--;} if(calMonth>11){calMonth=0;calYear++;}
  renderCal();
}
function renderCal(){
  if(!AVAIL_DATES.length) return;
  const months=['一1月','一2月','一3月','一4月','一5月','一6月','一7月','一8月','一9月','10月','11月','12月'];
  document.getElementById('calMonthLabel').textContent=calYear+' 年 '+months[calMonth];
  const grid=document.getElementById('calGrid');
  const first=new Date(calYear,calMonth,1).getDay();
  const days=new Date(calYear,calMonth+1,0).getDate();
  let html='';
  for(let i=0;i<first;i++) html+='<div class="cal-cell"></div>';
  for(let d=1;d<=days;d++){
    const mm=String(calMonth+1).padStart(2,'0'), dd=String(d).padStart(2,'0');
    const key=`${calYear}${mm}${dd}`;
    const hasData=AVAIL_DATES.includes(key), isSel=key===curDate;
    let cls='cal-cell'; if(hasData) cls+=' has-data'; if(isSel) cls+=' selected';
    const click=hasData?`onclick="selectDate('${key}')"`:'';
    html+=`<div class="${cls}" ${click}>${d}</div>`;
  }
  grid.innerHTML=html;
}

function selectDate(d){
  curDate=d;
  document.getElementById('calBtnTxt').textContent=fmtDateBtn(d);
  document.getElementById('calPopup').classList.remove('open');
  document.querySelectorAll('.dp[data-prod="'+curProdKey+'"]').forEach(p=>p.classList.remove('on'));
  const panel=document.getElementById('dp-'+curProdKey+'-'+d);
  if(panel) panel.classList.add('on');
  switchAct(d,Object.keys(IMGS[d])[0]);
  updateRankings();
}

const loadedTabs=new Set();
function preloadAndRender(d,k){
  const key=d+'/'+k, imgs=IMGS[d]&&IMGS[d][k]||[];
  if(!imgs.length||loadedTabs.has(key)){renderViewer();return;}
  const ov=document.getElementById('loadingOverlay'); ov.classList.add('show');
  let done=0;
  imgs.forEach(src=>{
    const img=new Image();
    img.onload=img.onerror=()=>{done++;if(done>=imgs.length){loadedTabs.add(key);ov.classList.remove('show');renderViewer();}};
    img.src=src;
  });
}
function switchAct(d,k){
  document.querySelectorAll('.at').forEach(b=>b.classList.remove('on'));
  const btn=document.getElementById('at-'+curProdKey+'-'+d+'-'+k);
  if(btn) btn.classList.add('on');
  curTab=k; curIdx=0; preloadAndRender(d,k);
}
function renderViewer(){
  const imgs=(IMGS[curDate]&&IMGS[curDate][curTab])||[], total=imgs.length;
  if(!total) return;
  document.getElementById('mainImg').src=imgs[curIdx];
  document.getElementById('counter').textContent=(curIdx+1)+' / '+total;
  document.getElementById('btnPrev').classList.toggle('hidden',curIdx===0);
  document.getElementById('btnNext').classList.toggle('hidden',curIdx===total-1);
  const strip=document.getElementById('thumbs');
  strip.innerHTML=imgs.map((src,i)=>`<div class="thumb ${i===curIdx?'on':''}" onclick="goTo(${i})"><img src="${src}" loading="lazy"/></div>`).join('');
  setTimeout(()=>{const a=strip.querySelector('.thumb.on');if(a) a.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});},50);
}
function navigate(dir){const imgs=(IMGS[curDate]&&IMGS[curDate][curTab])||[];curIdx=Math.max(0,Math.min(imgs.length-1,curIdx+dir));renderViewer();}
function goTo(i){curIdx=i;renderViewer();}
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')navigate(-1);if(e.key==='ArrowRight')navigate(1);});
document.addEventListener('click',e=>{
  const cw=document.getElementById('calWrap');  if(cw&&!cw.contains(e.target)) document.getElementById('calPopup').classList.remove('open');
  const sw=document.getElementById('cselWrap'); if(sw&&!sw.contains(e.target)) document.getElementById('cselPopup').classList.remove('open');
  const pw=document.getElementById('prod-toggle');if(pw&&!pw.contains(e.target)) document.getElementById('prod-popup').classList.remove('open');
});
(function(){
  const fd=AVAIL_DATES[0];
  if(!fd) return;
  const ft=Object.keys(IMGS[fd])[0];
  curDate=fd; curTab=ft;
  calYear=parseInt(fd.slice(0,4)); calMonth=parseInt(fd.slice(4,6))-1;
  document.getElementById('calBtnTxt').textContent=fmtDateBtn(fd);
  const panel=document.getElementById('dp-'+curProdKey+'-'+fd);
  if(panel){panel.classList.add('on');panel.style.display='';}
  preloadAndRender(fd,ft); updateRankings();
})();
"""

def generate_html(products_list, all_rankings=None):
    if not products_list:
        return None
    if all_rankings is None:
        all_rankings = {}

    first_prod_key = products_list[0][1]

    all_data_js = {}
    for prod_name, prod_key, data, labels, img_prefix, _ in products_list:
        prod_dates = list(data.keys())
        prod_imgs = {}
        for d, tabs in data.items():
            prod_imgs[d] = {}
            for k, imgs in tabs.items():
                prod_imgs[d][k] = [img_prefix + d + '/' + p.name for p in imgs]
        all_data_js[prod_key] = {
            "name": prod_name, "dates": prod_dates,
            "imgs": prod_imgs,
            "labels": {key: val for key, val in labels.items()},
        }

    all_panels = ""
    for pi, (prod_name, prod_key, data, labels, img_prefix, _) in enumerate(products_list):
        for di, (d, tabs) in enumerate(data.items()):
            sk = sorted(tabs.keys())
            tabs_html = "".join(
                '<button class="at ' + ('on' if j == 0 else '') + '" '
                'onclick="switchAct(\'' + d + '\',\'' + k + '\')" '
                'id="at-' + prod_key + '-' + d + '-' + k + '">'
                + labels.get(d + '/' + k, k) + '</button>'
                for j, k in enumerate(sk)
            )
            style = ' style="display:none"' if pi > 0 else ""
            visible = " on" if (pi == 0 and di == 0) else ""
            all_panels += (
                '<div class="dp' + visible + '" data-prod="' + prod_key + '" '
                'id="dp-' + prod_key + '-' + d + '"' + style + '>'
                '<div class="ats" id="ats-' + prod_key + '-' + d + '">' + tabs_html + '</div>'
                '</div>'
            )

    prod_opts = "".join(
        '<div class="prod-opt ' + ('on' if i == 0 else '') + '" '
        'data-pk="' + pk + '" '
        'onclick="selectProduct(\'' + pk + '\')">' + pn + '</div>'
        for i, (pn, pk, _, _, _, _) in enumerate(products_list)
    )
    first_prod_display = products_list[0][0]

    apple_svg = '<svg class="s-icon" viewBox="0 0 24 24" width="30" height="30" fill="#a0c4ff"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>'
    android_svg = '<svg class="s-icon" viewBox="0 0 24 24" width="16" height="16"><path fill="#4285F4" d="M3.18 1.06a1.5 1.5 0 00-.88 1.44v19c0 .65.37 1.2.88 1.44L13.6 12z"/><path fill="#FBBC05" d="M20.82 10.7l-3.1-1.78-3.32 3.08 3.32 3.08 3.1-1.78a1.5 1.5 0 000-2.6z"/><path fill="#EA4335" d="M3.18 1.06L13.6 12l4.12-3.08L5.08.4a1.5 1.5 0 00-1.9.66z"/><path fill="#34A853" d="M3.18 22.94L13.6 12l4.12 3.08L5.08 23.6a1.5 1.5 0 01-1.9-.66z"/></svg>'

    js = (_JS_TMPL
          .replace('%ALL_DATA%',     json.dumps(all_data_js,  ensure_ascii=False))
          .replace('%ALL_RANKINGS%', json.dumps(all_rankings, ensure_ascii=False))
          .replace('%FIRST_KEY%',    first_prod_key))

    TW = '台灣'; US = '美國'; JP = '日本'; UK = '英國'
    ZT = '類別排名'; GD = '選擇日期'

    parts = [
        '<!DOCTYPE html>\n<html lang="zh-TW">\n<head>\n<meta charset="UTF-8">\n',
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">\n',
        '<title>CF Gallery</title>\n<style>', _CSS, '</style>\n</head>\n<body>\n',
        '<header>\n',
        '  <div class="logo-area">\n',
        '    <div class="logo"><img src="CF/basic/icon.png" alt="CF"/><span>Cash Frenzy</span></div>\n',
        '    <div class="prod-toggle" id="prod-toggle">\n',
        '      <button class="prod-toggle-btn" onclick="togglePpopup()">&#9660;</button>\n',
        '      <div class="prod-popup" id="prod-popup">', prod_opts, '</div>\n',
        '    </div>\n',
        '  </div>\n',
        '  <div class="header-center" id="rankSection">\n',
        '    <span class="rank-label">' + ZT + '</span>\n',
        '    <div class="rank-badge" id="rankApple">', apple_svg,
        '<span class="s-name">App Store</span><span class="r-num" id="rApple">--</span></div>\n',
        '    <div class="rank-badge" id="rankAndroid">', android_svg,
        '<span class="s-name">Google Play</span><span class="r-num" id="rAndroid">--</span></div>\n',
        '  </div>\n',
        '  <div class="header-right">\n',
        '    <div class="country-sel"><div class="csel-wrap" id="cselWrap">\n',
        '      <button class="cal-btn" onclick="toggleCsel()"><span id="cselBtnTxt">' + TW + '</span> &#9660;</button>\n',
        '      <div class="csel-popup" id="cselPopup">\n',
        '        <div class="csel-opt on" data-c="TW" onclick="selectCountry(\'TW\')">' + TW + '</div>\n',
        '        <div class="csel-opt" data-c="US" onclick="selectCountry(\'US\')">' + US + '</div>\n',
        '        <div class="csel-opt" data-c="JP" onclick="selectCountry(\'JP\')">' + JP + '</div>\n',
        '        <div class="csel-opt" data-c="UK" onclick="selectCountry(\'UK\')">' + UK + '</div>\n',
        '      </div>\n    </div></div>\n',
        '    <div class="cal-wrap" id="calWrap">\n',
        '      <button class="cal-btn" id="calBtn" onclick="toggleCal()"><span id="calBtnTxt">' + GD + '</span> &#9660;</button>\n',
        '      <div class="cal-popup" id="calPopup">\n',
        '        <div class="cal-nav"><button onclick="changeMonth(-1)">&#8249;</button>',
        '<span id="calMonthLabel"></span><button onclick="changeMonth(1)">&#8250;</button></div>\n',
        '        <div class="cal-dow"><span>日</span><span>一</span><span>二</span><span>三</span>',
        '<span>四</span><span>五</span><span>六</span></div>\n',
        '        <div class="cal-grid" id="calGrid"></div>\n',
        '      </div>\n    </div>\n  </div>\n</header>\n',
        '<div id="panels">', all_panels, '</div>\n',
        '<div class="loading-overlay" id="loadingOverlay"><div class="spinner"></div>',
        '<span class="loading-text">資源下載中</span></div>\n',
        '<div class="viewer">\n',
        '  <button class="arrow" id="btnPrev" onclick="navigate(-1)">&#8249;</button>\n',
        '  <div class="main-img-wrap"><img id="mainImg" src="" alt=""/>',
        '<div class="counter" id="counter">1 / 1</div></div>\n',
        '  <button class="arrow" id="btnNext" onclick="navigate(1)">&#8250;</button>\n',
        '</div>\n',
        '<div class="thumbs" id="thumbs"></div>\n',
        '<script>', js, '</script>\n</body>\n</html>',
    ]
    return "".join(parts)


def main():
    import subprocess, shutil
    cache    = load_cache()
    all_rankings = {}
    products_list = []

    for pi, (prod_name, src_dir, img_prefix, rankings_path, auto_detect) in enumerate(PRODUCTS):
        prod_key = "p" + str(pi)
        print("[CF Gallery] Scanning " + prod_name + ": " + str(src_dir))
        data = scan_folders(base_dir=src_dir)
        print("  Found " + str(len(data)) + " date folders")

        # OneDrive → CF git 資料夾（讓 GitHub Pages 可以讀到圖片）
        if img_prefix:
            dest_base = WEBSITE_DIR / img_prefix.rstrip("/")
        else:
            dest_base = WEBSITE_DIR
        dest_base.mkdir(parents=True, exist_ok=True)
        for date_str, tabs in data.items():
            for tab_key, imgs in tabs.items():
                for img_path in imgs:
                    dest_date_dir = dest_base / date_str
                    dest_date_dir.mkdir(exist_ok=True)
                    dest = dest_date_dir / img_path.name
                    if not dest.exists():
                        shutil.copy2(img_path, dest)
        # 同步 basic/ 資料夾（icon、素材等）
        src_basic = src_dir / "basic"
        if src_basic.exists():
            dest_basic = dest_base / "basic"
            dest_basic.mkdir(exist_ok=True)
            for f in src_basic.iterdir():
                if f.is_file():
                    shutil.copy2(f, dest_basic / f.name)

        labels = {}
        for date_str, tabs in data.items():
            n_tabs = len(tabs)
            for tab_key, imgs in tabs.items():
                labels[date_str + "/" + tab_key] = get_tab_label(
                    date_str, tab_key, imgs[0], cache, n_tabs=n_tabs,
                    prod_key=prod_key, auto_detect=auto_detect
                )

        all_rankings[prod_key] = load_rankings(rankings_path)
        products_list.append((prod_name, prod_key, data, labels, img_prefix, rankings_path))

    save_cache(cache)

    html = generate_html(products_list, all_rankings)
    if html:
        OUTPUT_HTML.write_text(html, encoding="utf-8")
        INDEX_HTML = WEBSITE_DIR / "index.html"
        INDEX_HTML.write_text(html, encoding="utf-8")
        total = sum(len(imgs) for _, _, data, _, _p, _r in products_list
                    for tabs in data.values() for imgs in tabs.values())
        print("[CF Gallery] Generated (" + str(total) + " images, " + str(len(products_list)) + " products)")

        git = shutil.which("git")
        if git:
            try:
                lock = WEBSITE_DIR / '.git' / 'index.lock'
                if lock.exists(): lock.unlink()
                run = lambda cmd: subprocess.run(cmd, cwd=WEBSITE_DIR, capture_output=True, text=True)
                run([git, "add", "index.html"])
                run([git, "add", "."])
                status = run([git, "status", "--porcelain"])
                if status.stdout.strip():
                    import datetime
                    run([git, "commit", "-m", "update: gallery " + str(datetime.date.today())])
                    push = run([git, "push", "origin", "main"])
                    if push.returncode == 0:
                        print("[CF Gallery] Pushed to GitHub Pages!")
                    else:
                        print("[CF Gallery] Push failed: " + push.stderr.strip())
                else:
                    print("[CF Gallery] No changes to push.")
            except Exception as e:
                print("[CF Gallery] Git error: " + str(e))
        else:
            print("[CF Gallery] git not found.")
    else:
        print("[CF Gallery] No data found.")


if __name__ == "__main__":
    main()
