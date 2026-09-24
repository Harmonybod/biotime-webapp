"""Pulls leave requests from BioTime and upserts them into the local cache."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.biotime_client import BioTimeClient
from app.models import LeaveRequest

logger = logging.getLogger(__name__)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            logger.warning("Could not parse BioTime datetime %r", value)
            return None


def record_to_row_fields(record: dict[str, Any]) -> dict[str, Any]:
    first = record.get("first_name") or ""
    last = record.get("last_name") or ""
    return {
        "biotime_id": record.get("id"),
        "emp_code": record.get("emp_code"),
        "employee_name": f"{first} {last}".strip(),
        "department": record.get("department"),
        "pay_code": record.get("pay_code"),
        "pay_code_name": record.get("pay_code_name"),
        "start_time": _parse_dt(record.get("start_time")),
        "end_time": _parse_dt(record.get("end_time")),
        "leave_day": record.get("leave_day"),
        "apply_reason": record.get("apply_reason") or "",
        "apply_time": _parse_dt(record.get("apply_time")),
        "approval_status": record.get("approval_status"),
        "approval_status_display": record.get("approval_status_display"),
        "approval_remark": record.get("approval_remark"),
        "approval_time": _parse_dt(record.get("approval_time")),
        "approver": record.get("approver"),
        "last_approver": record.get("last_approver"),
        "synced_at": datetime.utcnow(),
    }


def sync_leaves(db: Session, client: BioTimeClient) -> dict[str, int]:
    """Upsert every BioTime leave record into `leave_requests`, matched on biotime_id.

    Returns a small summary dict for logging / API responses.
    """
    created = 0
    updated = 0

    for record in client.iter_all_leaves():
        biotime_id = record.get("id")
        if biotime_id is None:
            continue

        fields = record_to_row_fields(record)
        row = db.query(LeaveRequest).filter(LeaveRequest.biotime_id == biotime_id).one_or_none()

        if row is None:
            db.add(LeaveRequest(**fields))
            created += 1
        else:
            for key, value in fields.items():
                setattr(row, key, value)
            updated += 1

    db.commit()
    summary = {"created": created, "updated": updated}
    logger.info("BioTime leave sync complete: %s", summary)
    return summary
