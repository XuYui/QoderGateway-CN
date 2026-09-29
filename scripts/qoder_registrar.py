#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qoder 半自动注册机（DrissionPage + YYDS Mail）

流程：
  register —— 注册新账号（姓名/邮箱/密码自动填写，人机验证人工滑动，
              验证码邮件自动收取并填入 OTP）
  device   —— 登录已注册账号 + Device 授权（人工过验证码），拉取 dt-/drt- 凭据

用法：
  python qoder_registrar.py register [--headless]
  python qoder_registrar.py device --email xxx@getaura.today --password 'pwd' [--headless]

依赖：uv add DrissionPage httpx
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import shutil
import string
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yyds_mail_parser import extract_verification_codes, normalize_message  # noqa: E402
from qoder_button_parser import pick_button  # noqa: E402

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
YYDS_API = "https://maliapi.215.im/v1"
YYDS_KEY = os.getenv("YYDS_API_KEY", "").strip()
REGISTER_URL = "https://qoder.com/users/sign-up"
LOGIN_URL = "https://qoder.com/users/sign-in"
SUCCESS_URL_MARK = "/download"          # 注册成功跳转特征
DEVICE_CLIENT_ID = "e883ade2-e6e3-4d6d-adf7-f92ceff5fdcb"
DEVICE_VERIFIER_CHARS = string.ascii_letters + string.digits + "-._~"

OUT_CREDENTIALS = Path(__file__).resolve().parent / "qoder_credentials.json"
LAST_PROFILE = Path(__file__).resolve().parent / ".last_profile"

log = print


# ---------------------------------------------------------------------------
# 随机数据生成
# ---------------------------------------------------------------------------
def random_name() -> str:
    """随机英文姓名。"""
    consonants = "bcdfghjklmnpqrstvwxyz"
    vowels = "aeiou"

    def syllable() -> str:
        return random.choice(consonants) + random.choice(vowels) + random.choice(consonants)

    first = (syllable() + syllable()).capitalize()
    last = (syllable() + syllable()).capitalize()
    return first, last


def random_password(length: int = 12) -> str:
    """12 位：大写 + 小写 + 数字 + 符号。"""
    if length < 4:
        raise ValueError("password too short")
    lower = random.choice(string.ascii_lowercase)
    upper = random.choice(string.ascii_uppercase)
    digit = random.choice(string.digits)
    symbol = random.choice("!@#$%^&*()-_=+")
    rest = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*()-_=+", k=length - 4))
    pool = list(lower + upper + digit + symbol + rest)
    random.shuffle(pool)
    return "".join(pool)


# ---------------------------------------------------------------------------
# YYDS Mail 集成
# ---------------------------------------------------------------------------
def yyds_create_mailbox(prefix: str = "qoder") -> str:
    """创建临时邮箱，返回 address。"""
    local = prefix + uuid.uuid4().hex[:8]
    r = httpx.post(
        f"{YYDS_API}/accounts",
        headers={"X-API-Key": YYDS_KEY, "Content-Type": "application/json"},
        json={"localPart": local},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()["data"]
    log(f"[mail] created {data['address']} (expires {data['expiresAt']})")
    return data["address"]


def _extract_code(msg: dict) -> str | None:
    """从 YYDS 消息里提取验证码（优先服务端 verificationCode）。"""
    server = msg.get("verificationCode")
    if server:
        return str(server)
    norm = normalize_message(msg)
    codes = extract_verification_codes(norm["text"], norm["html"], norm["subject"])
    return codes[0]["code"] if codes else None


def yyds_wait_code(address: str, timeout: float = 120.0) -> str:
    """长轮询收件箱直到拿到验证码，返回 (code)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(
                f"{YYDS_API}/messages/next",
                params={"address": address, "wait": 30},
                headers={"X-API-Key": YYDS_KEY},
                timeout=45,
            )
            if r.status_code == 200:
                msg = r.json()["data"]["message"]
                code = _extract_code(msg)
                log(f"[mail] got message from {msg.get('from', {}).get('address')}: {msg.get('subject')}")
                if code:
                    log(f"[mail] verification code = {code}")
                    return code
                log("[mail] no code found in message, keep polling...")
            elif r.status_code == 204:
                log("[mail] no message yet...")
            else:
                log(f"[mail] unexpected status {r.status_code}: {r.text[:200]}")
        except httpx.HTTPError as e:
            log(f"[mail] poll error: {e}")
        time.sleep(1)
    raise TimeoutError(f"no verification code within {timeout}s for {address}")


# ---------------------------------------------------------------------------
# Device flow 参数（来自 qodercli 逆向：docs/qoder-protocol-research.md §4）
# ---------------------------------------------------------------------------
def device_flow_params(machine_id: str | None = None) -> dict:
    """生成 PKCE verifier/challenge/nonce 与授权 URL、轮询 URL。"""
    length = random.randint(43, 128)
    verifier = "".join(random.choices(DEVICE_VERIFIER_CHARS, k=length))
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    nonce = str(uuid.uuid4())
    mid = machine_id or str(uuid.uuid4())
    auth_url = (
        f"https://qoder.com/device/selectAccounts?challenge={challenge}"
        f"&challenge_method=S256&nonce={nonce}&machine_id={mid}&client_id={DEVICE_CLIENT_ID}"
    )
    poll_url = (
        f"https://openapi.qoder.sh/api/v1/deviceToken/poll"
        f"?nonce={nonce}&verifier={verifier}&challenge_method=S256"
    )
    return {"verifier": verifier, "nonce": nonce, "auth_url": auth_url, "poll_url": poll_url}


def poll_device_token(poll_url: str, timeout: float = 300.0) -> dict:
    """轮询 /deviceToken/poll，404 = 未授权，200 = 凭据。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = httpx.get(poll_url, headers={"Accept": "application/json"}, timeout=20)
        if r.status_code == 404:
            log("[device] waiting for user authorization...")
        elif r.status_code == 200:
            data = r.json()
            log("[device] credential received")
            return data
        else:
            log(f"[device] unexpected status {r.status_code}: {r.text[:200]}")
        time.sleep(1)
    raise TimeoutError("device authorization timeout")


# ---------------------------------------------------------------------------
# DrissionPage 封装
# ---------------------------------------------------------------------------
class QoderRegistrar:
    def __init__(self, headless: bool = False, profile_dir: str | None = None,
                 cleanup_profile: bool = False) -> None:
        from DrissionPage import ChromiumPage, ChromiumOptions

        co = ChromiumOptions()
        if headless:
            co.headless()
        if profile_dir:
            self.profile_dir = profile_dir
            self._own_profile = False
        else:
            # 全新注册/无 profile 时：创建唯一临时 profile 目录（登录 cookie 存这里）
            self.profile_dir = tempfile.mkdtemp(prefix="qoder_profile_")
            self._own_profile = True
            log(f"[browser] new temp profile: {self.profile_dir}")
        self._cleanup_profile = cleanup_profile
        co.set_user_data_path(self.profile_dir)
        self.page = ChromiumPage(co)

    def close(self) -> None:
        try:
            self.page.quit()
        except Exception:
            pass
        # 标记自毁时删除 profile 目录（device 完成后清理临时 profile）
        if self._cleanup_profile:
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
                log(f"[browser] profile destroyed: {self.profile_dir}")
            except Exception as e:
                log(f"[browser] failed to destroy profile: {e}")

    # ---- 页面工具 ----
    @staticmethod
    def _html_fp(page) -> str:
        """页面 DOM 指纹（html 的 md5），用于检测点击后页面是否变化。"""
        html = page.html or ""
        return hashlib.md5(html.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _wait_ele(page, selector: str, timeout: float = 60.0, index: int | None = None):
        """等待元素出现并返回。"""
        kwargs: dict = {"timeout": timeout}
        if index is not None:
            kwargs["index"] = index
        return page.wait.ele_displayed(selector, **kwargs)

    def _click_submit(self, timeout: float = 10.0) -> None:
        """点击包含'继 续'文本的 submit 按钮（找不到则点第一个 submit）。"""
        btn = self._find_submit_button(timeout)
        if btn is not None:
            btn.click()
            return
        self.page.ele('css:button[type="submit"]').click()

    def _find_submit_button(self, timeout: float = 10.0):
        """扫描可点击元素，用 qoder_button_parser 的规则选出认证按钮（'继 续'）。"""
        pairs: list[tuple] = []  # (element, feature)
        for sel in ('css:button', 'css:a[href]', 'css:[role="button"]'):
            try:
                els = self.page.eles(sel, timeout=timeout)
            except Exception:
                continue
            for el in els:
                try:
                    feat = {
                        "tag": el.tag,
                        "text": (el.text or "").strip()[:80],
                        "id": el.attr("id") or "",
                        "class": el.attr("class") or "",
                        "type": el.attr("type") or "",
                        "aria-label": el.attr("aria-label") or "",
                        "displayed": bool(el.states.is_displayed),
                    }
                    pairs.append((el, feat))
                except Exception:
                    continue
        if not pairs:
            return None
        picked = pick_button([f for _, f in pairs])
        if not picked:
            return None
        for el, feat in pairs:
            if feat is picked["feature"]:
                return el
        return None

    # ---- 流程 1：注册 ----
    def register(self) -> dict:
        page = self.page
        # 0) 先申请临时邮箱（提前拿到地址）
        address = yyds_create_mailbox()
        first, last = random_name()
        password = random_password()
        log(f"[reg] name={first} {last}  mail={address}  pwd={password}")

        # 1) 打开注册页并等待加载
        log("[reg] opening sign-up page...")
        page.get(REGISTER_URL)
        page.wait.load_start()
        time.sleep(1)
        self._wait_ele(page, "#basic_firstName", timeout=60)
        log("[reg] page loaded")

        # 2) 填姓名 + 邮箱
        page.ele("#basic_firstName").input(first)
        page.ele("#basic_lastName").input(last)
        page.ele("#basic_email").input(address)
        log("[reg] name & email filled")

        # 3) 勾选第一个 checkbox（同意条款）
        cb = page.ele("css:.ant-checkbox-input")
        cb.parent().click()
        log("[reg] checkbox checked")

        # 4) 点击"继 续"
        self._click_submit()
        log("[reg] submitted email step")

        # 5) 填密码（直接等待密码框出现，不额外 sleep）
        page.wait.ele_displayed("#basic_password", timeout=60)
        page.ele("#basic_password").input(password)
        self._click_submit()
        log("[reg] submitted password step")

        # 6) 人机验证：等用户手动完成（页面进入 OTP 步骤）
        log("=" * 60)
        log("[reg] >>> 请在浏览器中完成人机验证（滑动滑块）<<<")
        log("=" * 60)
        # 轮询等待 OTP 输入框出现（人工完成验证码后页面自动跳转）
        try:
            self._wait_ele(page, 'css:input[aria-label^="OTP Input"]', timeout=300)
            log("[reg] OTP input appeared")
        except Exception:
            # 某些情况页面直接跳转，检查 URL
            if SUCCESS_URL_MARK not in page.url:
                raise
            log("[reg] page jumped directly to download")

        # 7) 反复检查收件箱提取验证码（邮件一般 10s 内到达）
        code = yyds_wait_code(address, timeout=120)

        # 8) 填入 OTP
        otp_inputs = page.eles('css:input[aria-label^="OTP Input"]')
        if otp_inputs:
            for i, ch in enumerate(code[: len(otp_inputs)]):
                otp_inputs[i].input(ch)
            log(f"[reg] OTP filled: {code}")
        else:
            log("[reg] no OTP inputs found, trying paste into first otp...")
            page.ele('css:input[aria-label^="OTP Input"]').input(code)

        # 9) 等待跳转到下载页 = 注册成功
        deadline = time.time() + 30
        while time.time() < deadline:
            if SUCCESS_URL_MARK in page.url:
                log(f"[reg] SUCCESS -> {page.url}")
                break
            time.sleep(1)
        else:
            log(f"[reg] warning: still at {page.url}, check manually")

        result = {"email": address, "password": password, "name": f"{first} {last}"}
        # 记录 profile 路径：注册产生的登录 cookie 在里面，device 流程复用
        LAST_PROFILE.write_text(self.profile_dir, encoding="utf-8")
        log(f"[reg] profile saved -> {LAST_PROFILE} ({self.profile_dir})")
        log(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # ---- 流程 2：Device 授权（带 cookie 直接点"继 续"，最后 pull） ----
    def device(self, email: str, password: str) -> dict:
        page = self.page

        # 1) 先拿登录/授权 URL（复用 qodercli 逆向的 device flow 参数）
        flow = device_flow_params()
        log(f"[dev] auth URL:\n  {flow['auth_url']}")

        # 2) 跳转过去执行 device（带登录 cookie 会直接显示认证页）
        page.get(flow["auth_url"])
        page.wait.load_start()
        time.sleep(1)

        # 3) 轮询定位"继 续"按钮并点击（点击后 2 秒无 DOM/URL 变化 => 点击失败重试）
        deadline = time.time() + 300
        clicked = False
        while time.time() < deadline:
            try:
                btn = self._find_submit_button(timeout=3)
                if btn is not None:
                    before_url = page.url
                    before_fp = self._html_fp(page)
                    log(f"[dev] found button '{btn.text.strip()}', clicking...")
                    btn.click()
                    # 点击后 2 秒内检测 DOM/URL 变化，无变化视为点击失败
                    changed = False
                    for _ in range(4):  # 4 x 0.5s = 2s
                        time.sleep(0.5)
                        if page.url != before_url or self._html_fp(page) != before_fp:
                            changed = True
                            break
                    if changed:
                        clicked = True
                        log("[dev] click took effect (page changed)")
                        break
                    log("[dev] click did not change page, retrying...")
            except Exception:
                pass
            try:
                # 仅当登录表单可见才提示（隐藏模板元素不算）
                login_el = page.ele("#basic_email", timeout=1)
                if login_el.states.is_displayed:
                    log("[dev] 检测到可见登录表单：浏览器未登录，请在页面中手动完成登录后等待脚本点击'继 续'...")
            except Exception:
                pass
            time.sleep(1)

        if not clicked:
            raise TimeoutError("认证页未出现可点击的'继 续'按钮（可能未登录或页面结构变化）")

        log("=" * 60)
        log("[dev] >>> 已点击'继 续'，等待服务端完成认证并 pull <<<")
        log("=" * 60)

        # 4) 最后 pull：轮询 poll 端点拿凭据
        cred = poll_device_token(flow["poll_url"], timeout=300)
        result = {
            "email": email,
            "password": password,
            "device": {
                "token": cred.get("token"),
                "refresh_token": cred.get("refresh_token"),
                "user_id": cred.get("user_id"),
                "expires_at": cred.get("expires_at"),
                "refresh_token_expires_at": cred.get("refresh_token_expires_at"),
            },
        }
        OUT_CREDENTIALS.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[dev] credentials saved -> {OUT_CREDENTIALS}")
        return result

    # ---- 流程 3：扫描认证页按钮特征（供人工确认'继 续'按钮） ----
    def scan_auth_buttons(self) -> None:
        page = self.page
        flow = device_flow_params()
        log(f"[scan] auth URL:\n  {flow['auth_url']}")
        page.get(flow["auth_url"])
        page.wait.load_start()
        time.sleep(1)

        results: list[dict] = []
        for sel in ('css:button', 'css:a[href]', 'css:[role="button"]'):
            try:
                els = page.eles(sel, timeout=5)
            except Exception:
                continue
            for el in els:
                try:
                    rect = None
                    try:
                        loc = el.rect.location
                        size = el.rect.size
                        rect = {"x": loc.x, "y": loc.y, "w": size.width, "h": size.height}
                    except Exception:
                        pass
                    results.append({
                        "tag": el.tag,
                        "text": (el.text or "").strip()[:80],
                        "id": el.attr("id") or "",
                        "class": el.attr("class") or "",
                        "type": el.attr("type") or "",
                        "aria-label": el.attr("aria-label") or "",
                        "displayed": bool(el.states.is_displayed),
                        "rect": rect,
                    })
                except Exception:
                    continue

        dump = {"url": page.url, "count": len(results), "buttons": results}
        out = Path(__file__).resolve().parent / "buttons_dump.json"
        out.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(dump, ensure_ascii=False, indent=2))
        log(f"[scan] {len(results)} elements dumped -> {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Qoder 半自动注册机")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reg = sub.add_parser("register", help="注册新账号（新临时 profile，注册完保留供 device 复用）")
    p_reg.add_argument("--headless", action="store_true")
    p_reg.add_argument("--profile", help="指定 profile 目录（默认新建临时目录）")

    p_dev = sub.add_parser("device", help="Device 授权拉取凭据（默认复用上次注册的 profile，成功后自毁）")
    p_dev.add_argument("--email", required=True)
    p_dev.add_argument("--password", required=True)
    p_dev.add_argument("--headless", action="store_true")
    p_dev.add_argument("--profile", help="指定 profile 目录（默认读取 .last_profile）")
    p_dev.add_argument("--keep-profile", action="store_true", help="device 完成后保留 profile（默认自毁）")

    p_scan = sub.add_parser("scan", help="扫描认证页所有按钮特征（人工确认'继 续'按钮）")
    p_scan.add_argument("--profile", help="指定 profile（默认读取 .last_profile）")
    p_scan.add_argument("--headless", action="store_true")

    args = parser.parse_args()

    # 解析 profile 与自毁策略
    profile_dir = args.profile
    cleanup = False
    if args.cmd in ("device", "scan"):
        if not profile_dir and LAST_PROFILE.exists():
            profile_dir = LAST_PROFILE.read_text(encoding="utf-8").strip()
            log(f"[dev] using last profile: {profile_dir}")
        cleanup = (args.cmd == "device") and not args.keep_profile  # device 完成后自毁

    app = QoderRegistrar(headless=args.headless, profile_dir=profile_dir, cleanup_profile=cleanup)
    try:
        if args.cmd == "register":
            app.register()
        elif args.cmd == "scan":
            app.scan_auth_buttons()
        else:
            app.device(args.email, args.password)
    except KeyboardInterrupt:
        log("\ninterrupted by user")
        return 130
    except Exception as e:
        log(f"\n[error] {type(e).__name__}: {e}")
        return 1
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
