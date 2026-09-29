# Quickstart

Start QoderGateway, manage Qoder accounts, and complete your first OpenAI-compatible API request.

## Quickstart Flow

Follow these steps:

- Start QoderGateway.
- Manage Qoder accounts and request routing.
- Complete your first API call.

## Install and Start

Clone the repository and install dependencies:

```bash
git clone https://github.com/bzym2/QoderGateway.git
cd QoderGateway
uv sync
```

Then start the server:

```powershell
uv run qoder2api
```

The WebUI is served at:

```text
http://127.0.0.1:5050/
```

## Login and Change the Default Password

The default administrator password is:

```text
admin
```

You can use `admin` for the first login.

Change it immediately before using the gateway seriously. Copy the environment template:

```bash
mv .env.example .env
```

Then set a strong administrator password in `.env`:

```env
QODER_ADMIN_PASSWORD=your-strong-password
```

This password protects all management routes under `/ui/*` with the `X-Gateway-Token` header.

## Manage Qoder Accounts

Use one of these options:

- Click **Auto Import** to import the current local Qoder auth session.
- Paste a Qoder Personal Access Token into **Add PAT**.

Imported accounts are stored in SQLite and deduplicated by `uid`.

## First API Call

Once an account is active, send a chat completion request:

```bash
curl http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lite",
    "messages": [{ "role": "user", "content": "Say hello" }],
    "stream": false
  }'
```

If API key auth is enabled, also pass:

```bash
-H "Authorization: Bearer <your-api-key>"
```

## Verify Routing

Open **Service Logs**. Every request logs the account used for routing, for example:

```text
Request routing via account: Alice (019ec5c6-4bb0-7c1c-bf93-5209e1367f2b)
```

## Next Steps

- Read **Authentication** before exposing the gateway to another machine.
- Read **Account Pool** to understand rotation and quota behavior.
- Read **API Reference** if you want to connect an OpenAI SDK client.
