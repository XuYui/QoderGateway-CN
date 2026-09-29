# Authentication

QoderGate has two authentication layers: one for the management console and one for external API clients.

## Management Console Token

The WebUI uses the gateway token you enter on login. Frontend requests send it as:

```http
X-Gateway-Token: admin
```

This protects routes such as:

- `/ui/status`
- `/ui/accounts`
- `/ui/config`
- `/ui/logs`

## External API Keys

The OpenAI-compatible API can optionally require Bearer keys.

When enabled, clients must send:

```http
Authorization: Bearer <allowed-api-key>
```

## Which Token Should I Use?

| Use case | Header | Scope |
| --- | --- | --- |
| WebUI management | `X-Gateway-Token` | `/ui/*` routes |
| OpenAI-compatible calls | `Authorization` | `/v1/chat/completions` |

## Recommended Setup

- Keep the management token private.
- Enable API key auth before exposing the gateway to other machines.
- Rotate API keys if they are shared in logs or scripts.
