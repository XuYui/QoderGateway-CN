# API 参考

QoderGate 提供 OpenAI 兼容的 Chat Completions 接口。

## Base URL

```text
http://127.0.0.1:5050
```

## Chat Completions

```http
POST /v1/chat/completions
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `model` | string | 否 | 默认是 `lite`。 |
| `messages` | array | 是 | OpenAI 风格消息列表。 |
| `stream` | boolean | 否 | 为 `true` 时启用 SSE 流式输出。 |

### 非流式示例

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

### 流式示例

```bash
curl http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lite",
    "stream": true,
    "messages": [{ "role": "user", "content": "Stream a short answer" }]
  }'
```

## 错误码

| 状态码 | 含义 |
| --- | --- |
| `401` | 缺少或传入了错误的 API Key。 |
| `400` | 当前没有可用的 Qoder 账号。 |
| `502` | 所有可用账号请求上游都失败。 |
