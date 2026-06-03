import re

with open('generate_gallery.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 用正則找到 PRODUCTS 區塊並替換
pattern = r'# \(.*?\nPRODUCTS = \[.*?\]'
replacement = '''# (顯示名稱, 來源資料夾, 圖片URL前綴, 排名JSON路徑, 自動偵測頁籤名稱)
GDRIVE = Path("C:/Users/hankwu/GoogleDrive/Event_Center")

PRODUCTS = [
    ("Cash Frenzy", GDRIVE / "CF",   "",      CF_DIR / "rankings.json",           True),
    ("\u5927\u798f\u5a1b\u6a02\u57ce",   GDRIVE / "Dafu", "dafu/", GDRIVE / "Dafu" / "rankings.json", False),
]'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('generate_gallery.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
