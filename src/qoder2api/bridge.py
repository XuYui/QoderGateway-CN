import copy
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from . import encoding
from .auth import SessionContext, bearer_headers
from .env import httpx_client_kwargs


QODER_CHAT_URL = "https://gateway.qoder.com.cn/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1"
QODER_CHAT_URL_NEW = QODER_CHAT_URL


def now_ms() -> int:
    return int(time.time() * 1000)


def blank_response_meta() -> dict[str, Any]:
    return {
        "id": "",
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "completion_tokens_details": {"reasoning_tokens": 0},
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }


def template_base() -> dict[str, Any]:
    return {
        "request_id": str(uuid.uuid4()),
        "request_set_id": str(uuid.uuid4()),
        "chat_record_id": str(uuid.uuid4()),
        "stream": True,
        "chat_task": "FREE_INPUT",
        "chat_context": {
            "chatPrompt": "",
            "extra": {"context": [], "modelConfig": {"is_reasoning": False, "key": "lite"}, "originalContent": {"type": "text", "text": "hi"}},
            "features": [],
            "imageUrls": None,
            "text": {"type": "text", "text": "hi"},
        },
        "image_urls": None,
        "is_reply": True,
        "is_retry": False,
        "session_id": str(uuid.uuid4()),
        "code_language": "",
        "source": 1,
        "version": "3",
        "chat_prompt": "",
        "parameters": {"max_tokens": 32768},
        "aliyun_user_type": "personal_standard",
        "session_type": "qodercli",
        "agent_id": "agent_common",
        "task_id": "common",
        "model_config": {
            "key": "lite",
            "display_name": "Lite",
            "model": "",
            "format": "openai",
            "is_vl": False,
            "is_reasoning": False,
            "api_key": "",
            "url": "",
            "source": "system",
            "max_input_tokens": 180000,
        },
        "messages": [
            {
                "role": "system",
                "content": "You are Qoder, an interactive CLI tool that helps users with software engineering tasks.",
                "response_meta": blank_response_meta(),
                "reasoning_content_signature": "",
            }
        ],
        "tools": [],
        "business": {"product": "cli", "version": "0.1.43", "type": "agent", "id": str(uuid.uuid4()), "name": "hi", "begin_at": now_ms(), "stage": "start"},
    }


def normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [normalize_content_part(item) for item in content]
        return "\n\n".join(part for part in parts if part.strip())
    return normalize_content_part(content)


def normalize_content_part(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if isinstance(item.get("text"), str):
            return item["text"]
        if item.get("type") in {"image_url", "input_image"} and isinstance(item.get("image_url"), dict):
            url = item["image_url"].get("url")
            if isinstance(url, str):
                return f"[image] {url}"
        if isinstance(item.get("content"), (dict, list)):
            return normalize_content(item["content"])
        return json.dumps(item, ensure_ascii=False)
    return json.dumps(item, ensure_ascii=False)


def normalize_message_text(message: dict[str, Any]) -> str:
    text = normalize_content(message.get("content"))
    return text if text.strip() else normalize_content(message.get("contents"))


def extract_latest_user_prompt(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user":
            text = normalize_message_text(message)
            if text.strip():
                return text
    return ""


def build_user_message(text: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": "",
        "contents": [{"type": "text", "text": text}],
        "response_meta": blank_response_meta(),
        "reasoning_content_signature": "",
    }


def build_structured_message(role: str, text: str) -> dict[str, Any]:
    return {"role": role, "content": text or "", "response_meta": blank_response_meta(), "reasoning_content_signature": ""}


def normalize_tool_arguments(arguments: Any) -> str:
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))


def normalize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]] | None:
    if not isinstance(raw_tool_calls, list):
        return None
    normalized = []
    for raw in raw_tool_calls:
        function = raw.get("function", {}) if isinstance(raw, dict) else {}
        name = function.get("name", "")
        arguments = normalize_tool_arguments(function.get("arguments"))
        if not name and not arguments:
            continue
        normalized.append({"id": raw.get("id", ""), "type": raw.get("type", "function"), "function": {"name": name, "arguments": arguments}})
    return normalized or None


def parse_tool_calls_text(text: str | None) -> list[dict[str, Any]] | None:
    if not text:
        return None
    trimmed = text.strip()
    if not trimmed.startswith("Tool calls:"):
        return None
    payload = trimmed[len("Tool calls:") :].strip()
    if payload.startswith("```") and payload.endswith("```"):
        newline = payload.find("\n")
        if newline >= 0:
            payload = payload[newline + 1 : -3].strip()
    if not payload.startswith("["):
        return None
    try:
        return normalize_tool_calls(json.loads(payload))
    except json.JSONDecodeError:
        return None


def render_tool_result(message: dict[str, Any], text: str) -> str:
    label = "Tool result"
    if message.get("name"):
        label += f" ({message['name']})"
    if message.get("tool_call_id"):
        label += f" [{message['tool_call_id']}]"
    return f"{label}:\n{text}" if text.strip() else label


def convert_incoming_message(message: dict[str, Any], tools_enabled: bool) -> dict[str, Any] | None:
    role = message.get("role", "user")
    if role == "developer":
        role = "system"
    text = normalize_message_text(message)
    if not tools_enabled and message.get("tool_calls"):
        calls = json.dumps(message["tool_calls"], ensure_ascii=False)
        text = f"{text}\n\nTool calls:\n{calls}" if text.strip() else f"Tool calls:\n{calls}"
    if role == "tool":
        if tools_enabled:
            out = build_structured_message("tool", text)
            if message.get("name"):
                out["name"] = message["name"]
            if message.get("tool_call_id"):
                out["tool_call_id"] = message["tool_call_id"]
            return out
        role = "user"
        text = render_tool_result(message, text)
    if not text.strip() and not (tools_enabled and role == "assistant" and message.get("tool_calls")):
        return None
    if role == "user":
        return build_user_message(text)
    out = build_structured_message(role, text)
    if tools_enabled and role == "assistant":
        tool_calls = normalize_tool_calls(message.get("tool_calls")) or parse_tool_calls_text(text)
        if tool_calls:
            out["tool_calls"] = tool_calls
            if parse_tool_calls_text(text):
                out["content"] = ""
    return out


def build_qoder_messages(template_messages: list[dict[str, Any]], incoming: list[dict[str, Any]], prompt: str, tools_enabled: bool) -> list[dict[str, Any]]:
    rebuilt = []
    if not any(message.get("role") in {"system", "developer"} for message in incoming or []):
        rebuilt.extend(copy.deepcopy(message) for message in template_messages if message.get("role") == "system")
    for message in incoming or []:
        converted = convert_incoming_message(message, tools_enabled)
        if converted:
            rebuilt.append(converted)
    if not rebuilt and prompt.strip():
        rebuilt.append(build_user_message(prompt))
    return rebuilt


def build_qoder_body(req: dict[str, Any], sess: SessionContext) -> tuple[dict[str, Any], str, bool]:
    """Build the Qoder CN agent-chat request body from an OpenAI request."""
    model = req.get("model") or "lite"
    messages = req.get("messages") if isinstance(req.get("messages"), list) else []
    tools_enabled = bool(req.get("tools"))
    prompt = extract_latest_user_prompt(messages)
    rid = str(uuid.uuid4())
    body = template_base()
    body["request_id"] = rid
    body["request_set_id"] = str(uuid.uuid4())
    body["chat_record_id"] = rid
    body["session_id"] = str(uuid.uuid4())
    body["aliyun_user_type"] = sess.identity.user_type
    body["business"]["id"] = str(uuid.uuid4())
    body["business"]["begin_at"] = now_ms()
    body["business"]["name"] = prompt[:30] if prompt else "hi"
    body["chat_context"]["text"]["text"] = prompt
    body["chat_context"]["extra"]["originalContent"]["text"] = prompt
    body["model_config"]["key"] = model
    body["model_config"]["is_reasoning"] = True
    body["chat_context"]["extra"]["modelConfig"]["key"] = model
    body["chat_context"]["extra"]["modelConfig"]["is_reasoning"] = True
    body["messages"] = build_qoder_messages(body["messages"], messages, prompt, tools_enabled)
    if tools_enabled:
        body["tools"] = copy.deepcopy(req["tools"])
    if "tool_choice" in req:
        body["tool_choice"] = copy.deepcopy(req["tool_choice"])
    if "parallel_tool_calls" in req:
        body["parallel_tool_calls"] = req["parallel_tool_calls"]
    return body, model, tools_enabled


@dataclass
class BridgeDelta:
    role: str = ""
    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None

    @property
    def is_empty(self) -> bool:
        return not self.role and not self.content and not self.tool_calls


def extract_delta(data_line: str) -> BridgeDelta:
    try:
        obj = json.loads(data_line)
        if not isinstance(obj, dict):
            return BridgeDelta()
        # 新版：标准 OpenAI chunk（choices 直接在顶层）
        if "choices" in obj:
            for choice in obj.get("choices", []):
                delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
                role = delta.get("role") or ""
                content = delta.get("content") or ""
                tool_calls = delta.get("tool_calls") if isinstance(delta.get("tool_calls"), list) else None
                if role or content or tool_calls:
                    return BridgeDelta(role, content, tool_calls)
            return BridgeDelta()
        # 老版：wrapper 内嵌 body 字符串
        inner = obj.get("body") or ""
        if not inner:
            return BridgeDelta()
        inner_json = json.loads(inner)
        for choice in inner_json.get("choices", []):
            delta = choice.get("delta", {})
            role = delta.get("role") or ""
            content = delta.get("content") or ""
            tool_calls = delta.get("tool_calls") if isinstance(delta.get("tool_calls"), list) else None
            if role or content or tool_calls:
                return BridgeDelta(role, content, tool_calls)
    except (TypeError, json.JSONDecodeError):
        return BridgeDelta()
    return BridgeDelta()


def make_chunk(chunk_id: str, created: int, model: str, delta: dict[str, Any] | None = None, finish_reason: str | None = None) -> dict[str, Any]:
    return {"id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish_reason}]}


class ToolCallAccumulator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def append(self, delta_calls: list[dict[str, Any]]) -> None:
        for delta in delta_calls:
            index = delta.get("index") if isinstance(delta.get("index"), int) else len(self.calls)
            while len(self.calls) <= index:
                self.calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            existing = self.calls[index]
            if isinstance(delta.get("id"), str):
                existing["id"] = delta["id"]
            if isinstance(delta.get("type"), str):
                existing["type"] = delta["type"]
            function = delta.get("function") or {}
            if isinstance(function.get("name"), str):
                existing["function"]["name"] = function["name"]
            if isinstance(function.get("arguments"), str):
                existing["function"]["arguments"] += function["arguments"]

    def snapshot(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.calls)


async def qoder_stream_lines(sess: SessionContext, body: dict[str, Any], model: str) -> AsyncIterator[str]:
    """POST the Qoder CN COSY-signed agent-chat request and yield SSE lines."""
    body_text = encoding.encode(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    headers = bearer_headers(
        sess,
        QODER_CHAT_URL_NEW,
        body_text,
        "text/event-stream",
        {"x-model-key": model, "x-model-source": body["model_config"].get("source", "system")},
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15), **httpx_client_kwargs()) as client:
        async with client.stream("POST", QODER_CHAT_URL_NEW, content=body_text, headers=headers) as response:
            if response.status_code != 200:
                text = await response.aread()
                raise RuntimeError(f"HTTP {response.status_code} {text.decode(errors='replace')}")
            async for line in response.aiter_lines():
                if line:
                    yield line


async def stream_openai_response(req: dict[str, Any], sess: SessionContext) -> AsyncIterator[str]:
    body, model, tools_enabled = build_qoder_body(req, sess)
    chunk_id = "chatcmpl-" + uuid.uuid4().hex[:24]
    created = int(time.time())
    tool_calls = ToolCallAccumulator()
    emitted = False
    pending = ""
    streaming_text = False
    pending_role = "assistant"

    def event(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"

    async for line in qoder_stream_lines(sess, body, model):
        if not line.startswith("data:"):
            continue
        delta = extract_delta(line[5:].strip())
        if delta.is_empty:
            continue
        if delta.role:
            pending_role = delta.role
        if delta.tool_calls:
            pending = "" if tools_enabled and pending.lstrip().startswith("Tool calls:") else pending
            indexed = []
            for index, call in enumerate(delta.tool_calls):
                item = copy.deepcopy(call)
                item.setdefault("index", index)
                indexed.append(item)
            tool_calls.append(indexed)
            out_delta = {"tool_calls": indexed}
            if not emitted:
                out_delta["role"] = pending_role
            emitted = True
            yield event(make_chunk(chunk_id, created, model, out_delta))
            continue
        if not delta.content:
            continue
        if not tools_enabled or streaming_text:
            out_delta = {"content": delta.content}
            if not emitted:
                out_delta["role"] = pending_role
            emitted = True
            streaming_text = True
            yield event(make_chunk(chunk_id, created, model, out_delta))
            continue
        pending += delta.content
        candidate = pending.lstrip()
        if "Tool calls:".startswith(candidate) or candidate.startswith("Tool calls:"):
            continue
        streaming_text = True
        out_delta = {"content": pending}
        if not emitted:
            out_delta["role"] = pending_role
        emitted = True
        pending = ""
        yield event(make_chunk(chunk_id, created, model, out_delta))

    parsed_calls = parse_tool_calls_text(pending) if tools_enabled else None
    if parsed_calls:
        indexed = []
        for index, call in enumerate(parsed_calls):
            item = copy.deepcopy(call)
            item.setdefault("index", index)
            indexed.append(item)
        tool_calls.append(indexed)
        yield event(make_chunk(chunk_id, created, model, {"tool_calls": indexed, "role": pending_role} if not emitted else {"tool_calls": indexed}))
    elif pending:
        yield event(make_chunk(chunk_id, created, model, {"content": pending, "role": pending_role} if not emitted else {"content": pending}))

    finish_reason = "tool_calls" if tool_calls.calls else "stop"
    yield event(make_chunk(chunk_id, created, model, {}, finish_reason))
    yield "data: [DONE]\n\n"


async def complete_openai_response(req: dict[str, Any], sess: SessionContext) -> dict[str, Any]:
    body, model, tools_enabled = build_qoder_body(req, sess)
    completion_id = "chatcmpl-" + uuid.uuid4().hex[:24]
    created = int(time.time())
    full = []
    tool_calls = ToolCallAccumulator()
    async for line in qoder_stream_lines(sess, body, model):
        if not line.startswith("data:"):
            continue
        delta = extract_delta(line[5:].strip())
        if delta.content:
            full.append(delta.content)
        if delta.tool_calls:
            tool_calls.append(delta.tool_calls)
    content = "".join(full)
    fallback_tool_calls = None if tool_calls.calls or not tools_enabled else parse_tool_calls_text(content)
    message: dict[str, Any] = {"role": "assistant"}
    if fallback_tool_calls:
        message["content"] = None
        message["tool_calls"] = fallback_tool_calls
    elif not content and tool_calls.calls:
        message["content"] = None
    else:
        message["content"] = content
    if tool_calls.calls:
        message["tool_calls"] = tool_calls.snapshot()
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls.calls or fallback_tool_calls else "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
