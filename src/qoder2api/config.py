from typing import Any

from .database import get_db
from .env import admin_password


def load_config() -> dict[str, Any]:
    with get_db() as conn:
        res = conn.execute("SELECT value FROM settings WHERE key = 'auth_required'").fetchone()
        auth_required = (res[0] == "1") if res else False
        
        rows = conn.execute("SELECT api_key FROM allowed_keys").fetchall()
        allowed_keys = [r[0] for r in rows]
        
        res_tok = conn.execute("SELECT value FROM settings WHERE key = 'gateway_token'").fetchone()
        gateway_token = admin_password() or (res_tok[0] if res_tok else "admin")

    return {
        "auth_required": auth_required,
        "allowed_keys": allowed_keys,
        "gateway_token": gateway_token
    }


def save_config(config: dict[str, Any]) -> None:
    with get_db() as conn:
        auth_required_str = "1" if config.get("auth_required", False) else "0"
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_required', ?)",
            (auth_required_str,)
        )
        
        if "gateway_token" in config:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('gateway_token', ?)",
                (str(config["gateway_token"]),)
            )
            
        if "allowed_keys" in config:
            conn.execute("DELETE FROM allowed_keys")
            for key in config["allowed_keys"]:
                conn.execute("INSERT OR REPLACE INTO allowed_keys (api_key) VALUES (?)", (key,))
