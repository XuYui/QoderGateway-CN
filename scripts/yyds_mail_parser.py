#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YYDS Mail 邮件解析器（含 Qoder 邮件特化）

输入（两种皆可）：
  1. YYDS Mail API 的消息 JSON —— GET /v1/messages/{id} 的 data，或
     GET /v1/messages/next 的 data.message
  2. 原始邮件源码（RFC 822）—— GET /v1/sources/{id} 的 data.data

用法：
  python yyds_mail_parser.py <message.json>            # 解析消息 JSON 文件
  python yyds_mail_parser.py --raw <source.txt>        # 解析原始邮件源码
  python yyds_mail_parser.py --json '<json字符串>'     # 直接传 JSON
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

if sys.platform == "win32":  # Windows 控制台默认 GBK，强制 UTF-8 输出
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 通用：邮件头解析
# ---------------------------------------------------------------------------

def _parse_address_list(raw: str | None) -> list[dict[str, str]]:
    """'Name <a@b.c>, d@e.f' -> [{"name": "...", "address": "..."}]"""
    out: list[dict[str, str]] = []
    for name, addr in getaddresses([raw or ""]):
        if addr:
            out.append({"name": name.strip(), "address": addr.strip()})
    return out


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return value


def parse_raw_source(raw: str | bytes) -> dict[str, Any]:
    """解析 RFC 822 原始邮件，输出统一结构。"""
    data = raw.encode("utf-8", errors="replace") if isinstance(raw, str) else raw
    msg = BytesParser(policy=policy.default).parsebytes(data)

    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict[str, Any]] = []

    def walk(part: Any) -> None:
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        if ctype.startswith("multipart/"):
            for sub in part.iter_parts():
                walk(sub)
            return
        if ctype == "text/plain" and "attachment" not in disp:
            try:
                text_parts.append(part.get_content())
            except Exception:
                pass
        elif ctype == "text/html" and "attachment" not in disp:
            try:
                html_parts.append(part.get_content())
            except Exception:
                pass
        else:
            payload = part.get_payload(decode=True) or b""
            attachments.append({
                "filename": part.get_filename() or "",
                "contentType": ctype,
                "size": len(payload),
            })

    walk(msg)

    headers = {k.lower(): v for k, v in msg.items()}
    return {
        "id": headers.get("message-id", "").strip("<>"),
        "from": _parse_address_list(headers.get("from")),
        "to": _parse_address_list(headers.get("to")),
        "cc": _parse_address_list(headers.get("cc")),
        "subject": headers.get("subject", ""),
        "text": "\n".join(text_parts),
        "html": "\n".join(html_parts),
        "date": _parse_date(headers.get("date")),
        "seen": None,
        "hasAttachments": bool(attachments),
        "size": len(data),
        "attachments": attachments,
        "rawHeaders": headers,
    }


def _norm_addresses(value: Any) -> list[dict[str, str]]:
    """YYDS Mail 的 from 是单个对象、to 是数组，统一成 list。"""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def normalize_message(msg: dict[str, Any]) -> dict[str, Any]:
    """把 YYDS Mail 消息 JSON 归一化成统一结构（字段名对齐 parse_raw_source）。"""
    html_raw = msg.get("html")
    if isinstance(html_raw, list):
        html_str = "\n".join(str(x) for x in html_raw)
    else:
        html_str = html_raw or ""
    return {
        "id": msg.get("id", ""),
        "from": _norm_addresses(msg.get("from")),
        "to": _norm_addresses(msg.get("to")),
        "cc": msg.get("cc") or [],
        "subject": msg.get("subject", ""),
        "text": msg.get("text") or "",
        "html": html_str,
        "date": msg.get("createdAt") or msg.get("date"),
        "seen": msg.get("seen"),
        "hasAttachments": bool(msg.get("hasAttachments")),
        "size": msg.get("size", 0),
        "attachments": msg.get("attachments") or [],
        "verificationCode": msg.get("verificationCode"),
        "raw": msg,
    }


# ---------------------------------------------------------------------------
# 验证码提取
# ---------------------------------------------------------------------------

_CODE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("6digit", re.compile(r"(?<!\d)(\d{6})(?!\d)")),
    ("4to8digit", re.compile(r"(?<!\d)(\d{4,8})(?!\d)")),
]

_CODE_KEYWORDS_CN = ["验证码", "校验码", "确认码", "动态码", "激活码"]
_CODE_KEYWORDS_EN = [
    "verification code", "verification-code", "verify code", "confirm code",
    "security code", "one-time code", "one time code", "otp", "code is",
    "code:", "your code",
]


def _strip_html(body: str) -> str:
    """极简 HTML -> 文本（够用即可）。"""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"'))
    return text


def extract_verification_codes(
    text: str | None,
    html: str | None = None,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    """
    从正文/主题中提取验证码。
    返回 [{code, source(text|html|subject), context}]，关键词上下文行优先。
    """
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(code: str, source: str, context: str) -> None:
        if code not in seen:
            seen.add(code)
            candidates.append({"code": code, "source": source, "context": context[:160]})

    def scan(blob: str, source: str) -> None:
        plain = _strip_html(blob) if source == "html" else blob
        if not plain:
            return
        lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]

        # 1) 带关键词的行优先（如 "Your verification code is 384729."）
        for line in lines:
            low = line.lower()
            has_kw = any(k in low for k in _CODE_KEYWORDS_EN) or any(k in line for k in _CODE_KEYWORDS_CN)
            if not has_kw:
                continue
            for _, pat in _CODE_PATTERNS:
                m = pat.search(line)
                if m:
                    add(m.group(1), source, line)
                    break

        # 2) 无关键词时：整段扫常见模式
        if not candidates:
            for _, pat in _CODE_PATTERNS:
                for m in pat.finditer(plain):
                    add(m.group(1), source, plain[max(0, m.start() - 40):m.end() + 40])

    if text:
        scan(text, "text")
    if html:
        scan(html, "html")
    if subject:
        scan(subject, "subject")
    return candidates


# ---------------------------------------------------------------------------
# Qoder 特化
# ---------------------------------------------------------------------------

_QODER_SENDERS = ("qoder", "noreply@qoder", "@qoder.com", "@qoder.sh")


def is_qoder_message(msg: dict[str, Any]) -> bool:
    """判断是否来自 Qoder 的邮件（发件人域名 + 主题关键词）。"""
    sender = "".join(a.get("address", "") for a in _norm_addresses(msg.get("from")))
    subject = msg.get("subject") or ""
    return any(d in sender.lower() for d in _QODER_SENDERS) or "qoder" in subject.lower()


def parse_qoder(msg: dict[str, Any]) -> dict[str, Any]:
    """
    解析 Qoder 邮件，返回：
    {
      "isQoder": bool,
      "kind": "verification" | "notification" | "unknown",
      "verificationCode": str | None,
      "codes": [...],
      "summary": {...}
    }
    """
    norm = normalize_message(msg)
    result: dict[str, Any] = {
        "isQoder": is_qoder_message(norm),
        "kind": "unknown",
        "verificationCode": None,
        "codes": [],
        "summary": {
            "from": norm["from"],
            "to": norm["to"],
            "subject": norm["subject"],
            "date": norm["date"],
        },
    }
    if not result["isQoder"]:
        return result

    server_code = norm.get("verificationCode")
    codes = extract_verification_codes(norm["text"], norm["html"], norm["subject"])

    if server_code:
        result["verificationCode"] = str(server_code)
    elif codes:
        result["verificationCode"] = codes[0]["code"]
    result["codes"] = codes

    subject_low = (norm["subject"] or "").lower()
    body = (norm["text"] or "") + _strip_html(norm["html"] or "")
    if (
        result["verificationCode"]
        or any(k in subject_low for k in ("code", "verify", "验证", "otp"))
        or any(k in body for k in ("verification code", "验证码", "verify"))
    ):
        result["kind"] = "verification"
    else:
        result["kind"] = "notification"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    if argv[0] == "--raw":
        with open(argv[1], "r", encoding="utf-8", errors="replace") as f:
            parsed = parse_raw_source(f.read())
    elif argv[0] == "--json":
        parsed = parse_qoder(json.loads(argv[1]))
    else:
        with open(argv[0], "r", encoding="utf-8") as f:
            raw_msg = json.load(f)
        # 兼容 data.message / data / 裸 message 三种包装
        if isinstance(raw_msg, dict) and isinstance(raw_msg.get("data"), dict) and "message" in raw_msg["data"]:
            raw_msg = raw_msg["data"]["message"]
        elif isinstance(raw_msg, dict) and "message" in raw_msg:
            raw_msg = raw_msg["message"]
        parsed = parse_qoder(raw_msg)

    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
