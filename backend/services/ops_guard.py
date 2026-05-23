from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def require_write_auth(headers: Any) -> tuple[bool, str]:
    token = os.environ.get("EVOLVE_API_TOKEN", "").strip()
    if not token:
        return True, ""
    header_token = (headers.get("X-API-Token", "") or "").strip()
    if not header_token:
        auth = (headers.get("Authorization", "") or "").strip()
        if auth.lower().startswith("bearer "):
            header_token = auth[7:].strip()
    if header_token == token:
        return True, ""
    return False, "unauthorized write operation"


def append_audit_log(path: Path, action: str, detail: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "detail": detail,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
