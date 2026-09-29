# Operations

Operational notes for running QoderGate locally.

## SQLite Storage

QoderGate stores runtime data in:

```text
~/.qoder/qoder2api.db
```

The database contains accounts, allowed API keys, and settings.

## Backup

Stop the server and copy the database file:

```powershell
Copy-Item "$env:USERPROFILE\.qoder\qoder2api.db" "$env:USERPROFILE\Desktop\qoder2api.db.backup"
```

## Reset the Gateway Token

The gateway token lives in the `settings` table under `gateway_token`.

If you lock yourself out, update the value directly in SQLite or remove the database to reinitialize defaults.

## Troubleshooting

### 401 Unauthorized

- WebUI route: check `X-Gateway-Token`.
- API route: check `Authorization: Bearer <key>`.

### No Active Session

Import an account or add a PAT from the Dashboard.

### Account Quota Exceeded

Disable the exhausted account or import another account and let rotation continue.

### Local Auth Import Failed

Make sure Qoder CLI has been logged in on this machine and the local auth files exist.
