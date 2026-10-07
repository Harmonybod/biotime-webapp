"""Leave types (BioTime "pay codes") offered on the New Leave Request form.

BioTime's API has no endpoint listing leave types, and their ids differ per
BioTime server. So the list is built from:
1. every leave type seen in leave requests synced from BioTime, and
2. LEAVE_TYPES in .env ("id:Name, id:Name"), for types not used yet.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LeaveRequest

logger = logging.getLogger(__name__)


def _configured_leave_types() -> dict[int, str]:
    types = {}
    for item in settings.leave_types.split(","):
        code, sep, name = item.partition(":")
        if not item.strip():
            continue
        if not sep or not code.strip().isdigit() or not name.strip():
            logger.warning("Ignoring LEAVE_TYPES entry %r (expected id:Name)", item.strip())
            continue
        types[int(code)] = name.strip()
    return types


def leave_types(db: Session) -> dict[int, str]:
    types = {
        code: name or f"Leave type {code}"
        for code, name in db.query(LeaveRequest.pay_code, LeaveRequest.pay_code_name).distinct()
        if code is not None
    }
    types.update(_configured_leave_types())
    return dict(sorted(types.items(), key=lambda item: item[1].lower()))
