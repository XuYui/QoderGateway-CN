from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .auth import SessionContext, bearer_headers
from .env import httpx_client_kwargs


MODEL_LIST_URL = "https://gateway.qoder.com.cn/algo/api/v2/model/list?Encode=1"
MODEL_CACHE_TTL = 600


@dataclass(frozen=True)
class ModelInfo:
    id: str
    key: str
    display_name: str
    source: str = "system"
    is_vl: bool = False
    is_reasoning: bool = True
    max_input_tokens: int = 180000


@dataclass(frozen=True)
class ModelCatalog:
    models: tuple[ModelInfo, ...]
    dynamic: bool

    def resolve(self, requested: str | None) -> ModelInfo | None:
        if not requested:
            return self.default()
        wanted = requested.strip()
        wanted_folded = wanted.casefold()
        for model in self.models:
            if wanted == model.id or wanted == model.key:
                return model
            if wanted_folded in {model.id.casefold(), model.key.casefold()}:
                return model
        return None

    def default(self) -> ModelInfo:
        for model in self.models:
            if model.key == "lite" or model.id.casefold() == "lite":
                return model
        return self.models[0]

    def payload(self) -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {"id": model.id, "object": "model", "created": 0, "owned_by": "qoder"}
                for model in self.models
            ],
        }


FALLBACK_CATALOG = ModelCatalog(
    models=(
        ModelInfo(id="lite", key="lite", display_name="Lite"),
    ),
    dynamic=False,
)

_cache: dict[str, tuple[float, ModelCatalog]] = {}
_retry_after: dict[str, float] = {}
_cache_lock = asyncio.Lock()


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _as_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def parse_model_catalog(payload: Any) -> ModelCatalog | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("data"), dict):
        payload = payload["data"]
    raw_models = payload.get("chat")
    if not isinstance(raw_models, list):
        return None

    models: list[ModelInfo] = []
    seen: set[str] = set()
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        if "enable" in raw and not _as_bool(raw.get("enable")):
            continue
        if "is_enabled" in raw and not _as_bool(raw.get("is_enabled")):
            continue
        key = str(raw.get("key") or "").strip()
        display_name = str(raw.get("display_name") or key).strip()
        if not key or not display_name or key in seen:
            continue
        seen.add(key)
        efforts = raw.get("efforts")
        is_reasoning = raw.get("is_reasoning")
        if is_reasoning is None:
            for field in ("reasoning", "supports_reasoning", "is_reasoning_model"):
                if field in raw:
                    is_reasoning = raw[field]
                    break
        if is_reasoning is None:
            is_reasoning = bool(efforts) if isinstance(efforts, (list, tuple)) else True
        models.append(
            ModelInfo(
                id=display_name,
                key=key,
                display_name=display_name,
                source=str(raw.get("source") or "system"),
                is_vl=_as_bool(raw.get("is_vl"), _as_bool(raw.get("is_vl_model"))),
                is_reasoning=_as_bool(is_reasoning, True),
                max_input_tokens=_as_int(raw.get("max_input_tokens"), 180000),
            )
        )
    return ModelCatalog(tuple(models), dynamic=True) if models else None


async def _fetch_model_catalog(sess: SessionContext) -> ModelCatalog:
    headers = bearer_headers(sess, MODEL_LIST_URL, "", "application/json")
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10), **httpx_client_kwargs()) as client:
        response = await client.get(MODEL_LIST_URL, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"model list HTTP {response.status_code} body={response.text[:200]}")
    catalog = parse_model_catalog(response.json())
    if catalog is None:
        raise RuntimeError("model list response has no enabled chat models")
    return catalog


async def get_model_catalog(sess: SessionContext) -> ModelCatalog:
    cache_key = sess.identity.uid or "default"
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < MODEL_CACHE_TTL:
        return cached[1]
    if now < _retry_after.get(cache_key, 0):
        return cached[1] if cached else FALLBACK_CATALOG

    async with _cache_lock:
        now = time.monotonic()
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < MODEL_CACHE_TTL:
            return cached[1]
        if now < _retry_after.get(cache_key, 0):
            return cached[1] if cached else FALLBACK_CATALOG
        try:
            catalog = await _fetch_model_catalog(sess)
        except Exception:
            _retry_after[cache_key] = time.monotonic() + 30
            return cached[1] if cached else FALLBACK_CATALOG
        _cache[cache_key] = (time.monotonic(), catalog)
        _retry_after.pop(cache_key, None)
        return catalog
