#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qoder 全流程启动器：register → device（pull 凭据）→ 退出浏览器 → 自毁临时 profile

一次跑完：
  1. 创建全新临时 profile，打开注册页（你滑一次滑块，脚本自动收码填 OTP）
  2. 注册成功 → 退出浏览器（profile 保留，登录 cookie 在里面）
  3. 复用同一 profile 打开 Device 授权页（已登录，脚本自动点"继 续"）
  4. poll 拿到 dt-/drt- 凭据 → 保存 qoder_credentials.json → 退出浏览器 → 自毁 profile

用法：
  python qoder_launcher.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qoder_registrar import QoderRegistrar, OUT_CREDENTIALS  # noqa: E402


def main() -> int:
    log = print

    # ---------- 1) register：全新临时 profile ----------
    reg = QoderRegistrar(cleanup_profile=False)  # 注册完保留 profile（cookie 在里面）
    try:
        acct = reg.register()
    finally:
        reg.close()  # 退出浏览器（保留 profile 供下一步）
    profile = reg.profile_dir
    log(f"[launcher] register done, profile kept: {profile}")

    # ---------- 2) device：复用同一 profile，完成后自毁 ----------
    dev = QoderRegistrar(profile_dir=profile, cleanup_profile=True)
    try:
        cred = dev.device(acct["email"], acct["password"])
    finally:
        dev.close()  # 退出浏览器 + 自毁 profile

    # ---------- 3) 汇总 ----------
    log("=" * 60)
    log("[launcher] ALL DONE")
    summary = {
        "email": cred["email"],
        "password": cred["password"],
        "device": cred["device"],
        "credentials_file": str(OUT_CREDENTIALS),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
