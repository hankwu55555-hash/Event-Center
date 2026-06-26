#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只測『活動中心逐頁籤截圖』這一段；圖存到 _test_activity（不碰當日資料夾）。"""
import os
from adb_shell.adb_device import AdbDeviceTcp
import auto_activity_dafu_v2 as A

OUT = os.path.join(A.BASE_DIR, "_test_activity")
os.makedirs(OUT, exist_ok=True)

templates = A.load_templates()
d = AdbDeviceTcp(A.HOST, A.PORT)
d.connect(read_timeout_s=10)
print("連線成功，輸出資料夾：", OUT)
try:
    A.dismiss_popups(d, templates)          # 先關掉商城等彈窗，露出『活動』鈕
    A.capture_activities(d, templates, OUT)
finally:
    d.close()
    try:
        os.remove(A.TMP_PNG)
    except OSError:
        pass
