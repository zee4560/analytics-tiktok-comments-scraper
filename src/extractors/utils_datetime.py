from datetime import datetime, timezone

def to_iso8601(epoch_seconds: int) -> str:
    """
    Convert unix epoch seconds to ISO-8601 UTC string.
    Accepts ints or strings convertible to int.
    """
    try:
        ts = int(epoch_seconds)
    except Exception:
        ts = 0
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")