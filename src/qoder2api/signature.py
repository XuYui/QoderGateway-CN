import hashlib
from datetime import datetime, timezone
from email.utils import format_datetime


APPCODE = "cosy"
SECRET = "d2FyLCB3YXIgbmV2ZXIgY2hhbmdlcw=="
SEP = "&"


def current_date() -> str:
    return format_datetime(datetime.now(timezone.utc), usegmt=True)


def sign(date: str) -> str:
    return hashlib.md5(f"{APPCODE}{SEP}{SECRET}{SEP}{date}".encode()).hexdigest()
