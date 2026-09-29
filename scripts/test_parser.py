#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yyds_mail_parser 自测：用真实的 Qoder 验证码邮件样本验证解析结果。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from yyds_mail_parser import parse_qoder, parse_raw_source  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent / "testdata"
EXPECTED = "000000"


def test_yyds_json() -> None:
    msg = json.loads((HERE / "qoder_message.json").read_text(encoding="utf-8"))
    r = parse_qoder(msg)
    assert r["isQoder"], r
    assert r["kind"] == "verification", r
    assert r["verificationCode"] == EXPECTED, r
    assert r["summary"]["from"][0]["address"] == "no-reply@qoder.com", r


def test_raw_eml() -> None:
    raw = (HERE / "qoder_message.eml").read_text(encoding="utf-8", newline="")
    parsed = parse_raw_source(raw)
    assert parsed["subject"] == "Verify your Email with Qoder", parsed["subject"]
    assert parsed["from"][0]["address"] == "no-reply@qoder.com", parsed["from"]
    r = parse_qoder(parsed)
    assert r["isQoder"] and r["kind"] == "verification", r
    assert r["verificationCode"] == EXPECTED, r


if __name__ == "__main__":
    test_yyds_json()
    test_raw_eml()
    print("ALL TESTS PASSED (verificationCode =", EXPECTED + ")")
