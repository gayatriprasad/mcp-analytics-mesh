import json
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

LOG_DIR = Path("logs/audit")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _json_default(o):
    # Numeric
    if isinstance(o, Decimal):
        return float(o)
    # Dates
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    # UUIDs
    if isinstance(o, UUID):
        return str(o)
    # Fallback
    return str(o)

def emit_event(trace_id: str, event_type: str, payload: dict):
    log_file = LOG_DIR / f"{trace_id}.jsonl"

    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "payload": payload
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(event, default=_json_default) + "\n")