# 架构

QoderGate 把 OpenAI 兼容客户端请求桥接到 Qoder 会话。

## 请求流程

```text
Client
  -> FastAPI /v1/chat/completions
  -> API Key 校验
  -> SQLite 账号路由器
  -> Qoder Bearer 签名
  -> Qoder 上游 API
  -> OpenAI 兼容响应
```

## 后端模块

| 模块 | 职责 |
| --- | --- |
| `app.py` | FastAPI 路由、UI 鉴权、请求路由。 |
| `accounts.py` | SQLite 账号 CRUD 和活跃会话选择。 |
| `auth.py` | PAT 交换、本地 auth 导入、额度查询。 |
| `bridge.py` | OpenAI 兼容流式和非流式响应转换。 |
| `signature.py` | Bearer 签名实现。 |
| `database.py` | SQLite schema 和连接帮助函数。 |

## 前端模块

WebUI 使用 Vite、React、Tailwind CSS、GSAP 和 Markdown 渲染构建。

构建产物会输出到：

```text
src/qoder2api/static
```

FastAPI 会直接服务编译后的 `index.html`、`console.html`、`docs.html` 和静态资源。
