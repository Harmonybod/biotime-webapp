from __future__ import annotations

import socket
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api_keys import create_api_key
from app.config import settings
from app.database import get_db
from app.models import ApiKey
from app.templating import templates

router = APIRouter(tags=["integrations"])

ATTENDANCE_PARAMS = [
    ("start_date", "Yes", "First day of the period, YYYY-MM-DD."),
    ("end_date", "Yes", "Last day of the period, YYYY-MM-DD (at most 93 days after start_date)."),
    ("metrics", "No", "What to return, comma-separated: worked, absence, late, or single field names "
     "(see Metrics). Omitted: everything."),
    ("emp_code", "No", "Only this employee."),
    ("department", "No", "Only employees in this department (not case-sensitive)."),
    ("include_days", "No", "true adds a day-by-day breakdown per employee. Default false."),
    ("page", "No", "Page number, default 1."),
    ("page_size", "No", "Employees per page, default 50, max 500."),
]

ATTENDANCE_METRICS = [
    ("worked", "worked_hours", "Hours actually worked (check-in to check-out, summed)."),
    ("worked", "expected_work_hours", "Scheduled hours in the period, excluding approved leave."),
    ("worked", "present_days", "Days with at least one punch."),
    ("worked", "missing_punch_days", "Days with a check-in but no matching check-out."),
    ("absence", "absent_hours", "Scheduled hours on days with no punches and no approved leave."),
    ("absence", "absent_days", "Number of those days."),
    ("absence", "leave_days", "Scheduled days covered by approved leave (not counted as absent)."),
    ("late", "late_hours", "Total time between shift start and first punch, on late days."),
    ("late", "late_count", "Number of days the employee arrived late."),
]

LEAVE_PARAMS = [
    ("department", "No", "Only this department."),
    ("emp_code", "No", "Only this employee."),
    ("approval_status", "No", "0 Pending, 1 Cancelled, 2 Approved, 3 Rejected."),
]

ERRORS = [
    ("400", "A parameter is missing or invalid (the message says which)."),
    ("401", "The X-API-Key header is missing, wrong, or the key was revoked."),
    ("403", "The endpoint isn't available from other computers."),
    ("502", "BioTime returned an error; try again shortly."),
    ("503", "This installation isn't connected to BioTime yet."),
]


def _network_addresses() -> list[str]:
    """This PC's addresses on the local network, for the base URL."""
    addresses = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # UDP: nothing is sent, just picks the outgoing interface
            addresses.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not addr.startswith("127."):
                addresses.add(addr)
    except OSError:
        pass
    return sorted(addresses)


def _render(request: Request, db: Session, new_key: Optional[str] = None, new_key_name: str = "",
            message: Optional[str] = None, error: Optional[str] = None, status_code: int = 200):
    port = request.url.port or 80
    local_url = f"http://127.0.0.1:{port}"
    network_urls = [f"http://{addr}:{port}" for addr in _network_addresses()]
    base_url = network_urls[0] if settings.api_network_access and network_urls else local_url
    return templates.TemplateResponse(
        "integrations.html",
        {
            "request": request,
            "network_access": settings.api_network_access,
            "local_url": local_url,
            "network_urls": network_urls,
            "base_url": base_url,
            "keys": db.query(ApiKey).order_by(ApiKey.created_at.desc()).all(),
            "new_key": new_key,
            "new_key_name": new_key_name,
            "example_key": new_key or "YOUR_API_KEY",
            "attendance_params": ATTENDANCE_PARAMS,
            "attendance_metrics": ATTENDANCE_METRICS,
            "leave_params": LEAVE_PARAMS,
            "errors": ERRORS,
            "message": message,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/integrations")
def integrations_page(request: Request, message: Optional[str] = None, db: Session = Depends(get_db)):
    return _render(request, db, message=message)


@router.post("/integrations/keys")
def create_key(request: Request, name: str = Form(""), db: Session = Depends(get_db)):
    name = name.strip()
    if not name:
        return _render(request, db, error="Give the key a name, e.g. the client or system using it.", status_code=400)
    # Rendered directly (not redirected) so the key never ends up in a URL or browser history.
    return _render(request, db, new_key=create_api_key(db, name), new_key_name=name)


@router.post("/integrations/keys/{key_id}/revoke")
def revoke_key(key_id: int, db: Session = Depends(get_db)):
    row = db.get(ApiKey, key_id)
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse(url=f"/integrations?message=Key \"{row.name if row else ''}\" revoked.", status_code=303)
