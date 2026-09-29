# -*- coding: utf-8 -*-
"""qodergate-register：Qoder 独立注册机（无限循环，导出 JSON）。"""
from .core import (
    start_registration,
    stop_registration,
    get_registrar_status,
)

__all__ = ["start_registration", "stop_registration", "get_registrar_status"]
__version__ = "0.1.0"
