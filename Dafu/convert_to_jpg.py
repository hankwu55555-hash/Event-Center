#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
將指定資料夾內的 PNG 截圖批次轉成 JPG quality 10，並刪除原始 PNG
"""

import os
from PIL import Image

BASE_DIR = r"C:\Users\hankwu\Desktop\Event_Center\Dafu"
FOLDERS = ["20260529", "20260601", "20260602"]
QUALITY = 10

total = 0
for folder in FOLDERS:
    folder_path = os.path.join(BASE_DIR, folder)
    if not os.path.exists(folder_path):
        print(f"找不到資料夾：{folder}，略過")
        continue
    files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]
    print(f"{folder}：共 {len(files)} 張 PNG")
    for filename in files:
        png_path = os.path.join(folder_path, filename)
        jpg_path = os.path.join(folder_path, filename[:-4] + '.jpg')
        img = Image.open(png_path).convert('RGB')
        img.save(jpg_path, 'JPEG', quality=QUALITY)
        os.remove(png_path)
        total += 1

print(f"\n完成！共轉換 {total} 張，quality={QUALITY}")
