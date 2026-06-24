#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
擷取目前模擬器畫面（原始解析度）一張，存到 basic/_capture.png
用途：當畫面上出現「白色 X」彈窗時執行，之後交給程式裁切成 X 參考圖。
"""
import time
from adb_shell.adb_device import AdbDeviceTcp

OUT = r"C:\Users\hankwu\Desktop\Event_Center\CF\basic\_capture.png"

print("連接 127.0.0.1:5555 ...")
d = AdbDeviceTcp("127.0.0.1", 5555)
d.connect()
d.shell("screencap -p /sdcard/_cap.png")
time.sleep(0.5)
d.pull("/sdcard/_cap.png", OUT)
d.shell("rm /sdcard/_cap.png")
d.close()
print(f"已儲存原始截圖：{OUT}")
