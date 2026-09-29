# Account Pool

The account pool lets QoderGate route requests through multiple Qoder accounts and recover when one account fails.

## Import Methods

### Auto Import

Reads the current local Qoder auth session from your machine and imports it into SQLite.

### Add PAT

Exchanges a Qoder Personal Access Token for a usable session and stores it in the account pool.

## Deduplication

Accounts are deduplicated by `uid`. Re-importing the same user updates session data instead of creating duplicates.

## Enable and Disable

Disabled accounts stay in SQLite but are skipped during routing.

## Active Account

The active account is the first account used for a request. If it fails, QoderGate rotates to another enabled account.

## Quota Fields

| Field | Meaning |
| --- | --- |
| `quota` | Current quota value reported by Qoder. |
| `is_quota_exceeded` | Whether the account is over quota. |
| `plan` | Account plan identifier. |
| `user_tag` | Display label from Qoder. |
| `next_reset_at` | When quota is expected to reset. |
