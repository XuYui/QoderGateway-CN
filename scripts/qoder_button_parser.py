#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qoder 认证页按钮识别 parser

输入：元素特征列表（与 scripts/buttons_dump.json 同构，字段：
      tag / text / id / class / type / aria-label / displayed / rect）
输出：选中的认证按钮（"继 续"按钮）特征 + 评分与理由。

规则依据（来自 2026-08-06 对 https://qoder.com/device/selectAccounts 的实测扫描，
见 scripts/buttons_dump.json）：
  认证按钮 = <button> 文本"继 续"，class 含 ant-btn-primary，type=button
  其余均为导航 <a>（QoderWork/价格/下载/前往中国站等），需排除。

用法：
  python qoder_button_parser.py <features.json>        # 解析特征文件
  python qoder_button_parser.py --self-test            # 用内置样本自测
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# 候选按钮文本关键词（按优先级）
_TEXT_KEYWORDS: tuple[tuple[int, str], ...] = (
    (100, "继续"),      # "继 续" 归一化后
    (90, "同意"),
    (90, "授权"),
    (80, "authorize"),
)

# 特征加分
_TAG_BUTTON = 10
_CLASS_PRIMARY = 30       # ant-btn-primary
_TYPE_SUBMIT = 20
_DISPLAYED = 0            # 不显示不额外加分，但隐藏直接否决
_HIDDEN_PENALTY = -1000


def normalize_text(text: Any) -> str:
    """归一化按钮文本：去空白/全角空格。"""
    return (text or "").replace("\u00a0", " ").replace(" ", "").replace("\n", "").replace("\r", "").strip()


def score_button(feat: dict[str, Any]) -> int:
    """对单个元素特征打分，分越高越像认证按钮。"""
    score = 0
    tag = (feat.get("tag") or "").lower()
    text = normalize_text(feat.get("text"))
    cls = feat.get("class") or ""
    type_ = feat.get("type") or ""

    # 隐藏元素否决
    if feat.get("displayed") is False:
        score += _HIDDEN_PENALTY

    # 标签
    if tag == "button":
        score += _TAG_BUTTON
    # 文本关键词
    for pts, kw in _TEXT_KEYWORDS:
        if kw in text:
            score += pts
            break
    # class 特征
    if "ant-btn-primary" in cls:
        score += _CLASS_PRIMARY
    # type
    if type_ == "submit":
        score += _TYPE_SUBMIT
    return score


def pick_button(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    从特征列表里选出认证按钮。
    返回 {feature, score}；找不到（最高分过低）返回 None。
    """
    if not features:
        return None
    best = max(features, key=score_button)
    best_score = score_button(best)
    if best_score < _TAG_BUTTON + 40:  # 至少是 button + 明确文本/primary
        return None
    return {"feature": best, "score": best_score}


def parse_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    features = data.get("buttons", data if isinstance(data, list) else [])
    picked = pick_button(features)
    return {
        "source": str(path),
        "total": len(features),
        "picked": picked["feature"] if picked else None,
        "score": picked["score"] if picked else 0,
    }


def self_test() -> bool:
    """用 buttons_dump.json 的真实特征自测。"""
    here = Path(__file__).resolve().parent
    dump = here / "buttons_dump.json"
    if not dump.exists():
        print("[self-test] buttons_dump.json not found, skipping")
        return True
    result = parse_file(dump)
    picked = result["picked"]
    ok = bool(picked) and normalize_text(picked.get("text")) == "继续"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("[self-test]", "PASS" if ok else "FAIL", "- picked:", picked.get("text") if picked else None)
    return ok


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--self-test":
        return 0 if self_test() else 1
    print(json.dumps(parse_file(argv[0]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
