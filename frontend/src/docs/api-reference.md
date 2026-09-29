# API Reference

QoderGate exposes an OpenAI-compatible chat completions endpoint.

## Base URL

```text
http://127.0.0.1:5050
```

## Chat Completions

```http
POST /v1/chat/completions
```

### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `model` | string | No | Defaults to `lite`. |
| `messages` | array | Yes | OpenAI-style message list. |
| `stream` | boolean | No | Enables SSE streaming when `true`. |

### Non-Streaming Example

```bash
curl http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer qg_live_xxx" \
  -d '{
    "model": "lite",
    "stream": false,
    "messages": [{ "role": "user", "content": "Explain QoderGate" }]
  }'
```

### Streaming Example

```bash
curl http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lite",
    "stream": true,
    "messages": [{ "role": "user", "content": "Stream a short answer" }]
  }'
```

## Error Responses

| Status | Meaning |
| --- | --- |
| `401` | Missing or invalid API key. |
| `400` | No active Qoder account available. |
| `502` | Upstream request failed across available accounts. |
