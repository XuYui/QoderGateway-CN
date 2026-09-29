# Architecture

QoderGate bridges OpenAI-compatible clients to Qoder sessions.

## Request Flow

```text
Client
  -> FastAPI /v1/chat/completions
  -> API key validation
  -> SQLite account router
  -> Qoder Bearer signing
  -> Qoder upstream API
  -> OpenAI-compatible response
```

## Backend Components

| Module | Responsibility |
| --- | --- |
| `app.py` | FastAPI routes, UI auth, request routing. |
| `accounts.py` | SQLite account CRUD and active session selection. |
| `auth.py` | PAT exchange, local auth import, quota query. |
| `bridge.py` | OpenAI-compatible stream and response conversion. |
| `signature.py` | Bearer signing implementation. |
| `database.py` | SQLite schema and connection helpers. |

## Frontend Components

The WebUI is built with Vite, React, Tailwind CSS, GSAP, and Markdown rendering.

It is compiled into:

```text
src/qoder2api/static
```

FastAPI serves the compiled `index.html` and static assets directly.
