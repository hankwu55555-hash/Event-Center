#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""將 CF 資料夾內所有日期子資料夾的圖片轉成 JPG quality=10"""

from PIL import Image
import os

BASE_DIR = r"C:\Users\hankwu\Desktop\Event_Center\CF"
QUALITY = 10

total = 0
for folder_name in sorted(os.listdir(BASE_DIR)):
    folder = os.path.join(BASE_DIR, folder_name)
    # 只處理日期格式的資料夾（8位數字）
    if not os.path.isdir(folder) or not folder_name.isdigit() or len(folder_name) != 8:
        continue
    files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not files:
        continue
    count = 0
    for f in files:
        path = os.path.join(folder, f)
        jpg_path = os.path.splitext(path)[0] + ".jpg"
        try:
            img = Image.open(path).convert("RGB")
            img.save(jpg_path, "JPEG", quality=QUALITY)
            # 若原檔是 PNG 則刪除
            if path.lower().endswith(".png"):
                os.remove(path)
            count += 1
        except Exception as e:
            print(f"  ⚠️  {f} 失敗：{e}")
    print(f"✅ {folder_name}：處理 {count} 張")
    total += count

print(f"\n全部完成！共處理 {total} 張")
