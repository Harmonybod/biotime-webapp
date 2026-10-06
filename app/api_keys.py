"""API keys and network rules for the client-facing API.

- Client endpoints (CLIENT_API_ROUTES) require an `X-API-Key` header.
- Requests from other computers may only reach those endpoints; every page
  and internal endpoint (manual punches, settings, sync…) stays local-only,
  because the web UI has no login of its own.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApiKey

KEY_PREFIX = "btk_"

# (method, path) pairs an external system may call.
CLIENT_API_ROUTES = {
    ("GET", "/api/reports/attendance"),
    ("GET", "/api/leaves"),
}


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def create_api_key(db: Session, name: str) -> str:
    """Store a new key and return it. This is the only time the full key is available."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    db.add(ApiKey(name=name, key_prefix=key[: len(KEY_PREFIX) + 6], key_hash=_hash(key)))
    db.commit()
    return key


def is_local(host: Optional[str]) -> bool:
    return bool(host) and (host == "::1" or host.startswith("127.") or host.startswith("::ffff:127."))


def require_api_key(
    x_api_key: Optional[str] = Header(None, description="API key created on the API Integrations page"),
    db: Session = Depends(get_db),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Send it in the X-API-Key header.")
    row = db.query(ApiKey).filter(ApiKey.key_hash == _hash(x_api_key.strip())).one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
    row.last_used_at = datetime.now()
    db.commit()
    return row
