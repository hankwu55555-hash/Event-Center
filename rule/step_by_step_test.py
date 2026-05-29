#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐步診斷 - 找出具體問題"""

import sys
import time

print("=" * 70)
print("🔍 逐步診斷 ADB 連接問題")
print("=" * 70 + "\n")

# Step 1: 檢查 Python 版本
print("Step 1: 檢查 Python 版本")
print(f"   Python: {sys.version}")
print(f"   執行檔: {sys.executable}\n")
input("按 Enter 繼續... ")

# Step 2: 導入 adb_shell
print("\nStep 2: 導入 adb_shell 模組")
try:
    from adb_shell.adb_device import AdbDeviceTcp
    print("✅ 成功導入 adb_shell.adb_device.AdbDeviceTcp\n")
except ImportError as e:
    print(f"❌ 導入失敗: {e}\n")
    sys.exit(1)

input("按 Enter 繼續... ")

# Step 3: 建立 AdbDeviceTcp 物件
print("\nStep 3: 建立 AdbDeviceTcp 物件")
print("   建立物件: AdbDeviceTcp('127.0.0.1', 5555)")
try:
    device = AdbDeviceTcp("127.0.0.1", 5555)
    print(f"✅ 物件建立成功")
    print(f"   物件類型: {type(device)}\n")
except Exception as e:
    print(f"❌ 建立失敗: {e}\n")
    sys.exit(1)

input("按 Enter 繼續... ")

# Step 4: 嘗試連接 (加入超時)
print("\nStep 4: 嘗試連接 (加入 10 秒超時)")
print("   執行: device.connect()")
try:
    device.connect(rsa_keys=None, auth_callback=None)
    print("✅ 連接成功！\n")
except Exception as e:
    print(f"❌ 連接失敗: {e}\n")
    print(f"   錯誤類型: {type(e).__name__}\n")
    sys.exit(1)

input("按 Enter 繼續... ")

# Step 5: 執行簡單命令
print("\nStep 5: 執行簡單命令")
print("   執行: device.shell('getprop ro.build.version.release')")
try:
    result = device.shell("getprop ro.build.version.release")
    print(f"✅ 命令執行成功")
    print(f"   結果: {result}\n")
except Exception as e:
    print(f"❌ 命令失敗: {e}\n")
    sys.exit(1)

input("按 Enter 繼續... ")

# Step 6: 關閉連接
print("\nStep 6: 關閉連接")
try:
    device.close()
    print("✅ 連接已關閉\n")
except Exception as e:
    print(f"⚠️  關閉時出錯: {e}\n")

print("=" * 70)
print("✅ 診斷完成！")
print("=" * 70)
print("\n如果上面所有步驟都成功，說明 ADB 連接沒有問題。")
print("如果某個步驟失敗，錯誤訊息會顯示具體原因。")
