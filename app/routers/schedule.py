from __future__ import annotations

from datetime import date
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.biotime_client import BioTimeClient, BioTimeError, get_biotime_client
from app.config import settings
from app.database import get_db
from app.routers.reports import fetch_employees
from app.shifts import (
    FALLBACK_APP_DEFAULT,
    FALLBACK_NONE,
    describe_fallback,
    fallback_choice,
    get_shift_data,
    set_fallback_choice,
    sync_shifts,
)
from app.templating import templates

router = APIRouter(tags=["schedule"])


def _app_default_text() -> str:
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = [names[int(d)] for d in settings.shift_work_days.split(",") if d.strip().isdigit() and int(d) < 7]
    return f"{settings.shift_start}–{settings.shift_end}, {', '.join(days)}"


@router.get("/shifts")
def schedule_page(
    request: Request,
    message: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
    client: BioTimeClient = Depends(get_biotime_client),
):
    context = {"request": request, "message": message, "error": error, "data": None}
    try:
        data = get_shift_data(db, client)
        employees = fetch_employees(client)
    except BioTimeError as exc:
        context["error"] = f"Could not load the work schedule from BioTime: {exc.message}"
        return templates.TemplateResponse("schedule.html", context)

    by_id = {e["id"]: e for e in employees}
    today = date.today()
    assignments = [
        {
            "employee": by_id.get(a.employee_id, {"emp_code": "?", "name": f"Employee #{a.employee_id}"}),
            "shift": data.shifts[a.shift_id].name,
            "start": a.start,
            "end": a.end,
            "state": "Current" if a.start <= today <= a.end else "Ended" if a.end < today else "Upcoming",
        }
        for a in data.assignments
    ]
    assignments.sort(key=lambda row: (len(row["employee"]["emp_code"]), row["employee"]["emp_code"], row["start"]))
    scheduled = data.scheduled_employee_ids()
    choice = fallback_choice(db, data)

    context.update(
        {
            "data": data,
            "shifts": sorted(data.shifts.values(), key=lambda s: s.name.lower()),
            "assignments": assignments,
            "unscheduled": [e for e in employees if e["id"] not in scheduled],
            "choice": choice,
            "fallback_text": describe_fallback(data, choice),
            "fallback_none": FALLBACK_NONE,
            "fallback_app_default": FALLBACK_APP_DEFAULT,
            "app_default_text": _app_default_text(),
            "temp": sorted(
                ((by_id.get(emp_id, {"name": f"Employee #{emp_id}", "emp_code": "?"}), day, slots)
                 for (emp_id, day), slots in data.temp.items()),
                key=lambda row: row[1],
            ),
            "grace_minutes": settings.late_grace_minutes,
        }
    )
    return templates.TemplateResponse("schedule.html", context)


@router.post("/shifts/sync")
def sync_schedule(db: Session = Depends(get_db), client: BioTimeClient = Depends(get_biotime_client)):
    try:
        result = sync_shifts(db, client)
    except BioTimeError as exc:
        return RedirectResponse(url=f"/shifts?error={quote(exc.message)}", status_code=303)
    message = f"Synced from BioTime: {result['shifts']} shift(s), {result['schedules']} employee schedule(s), {result['holidays']} holiday(s)."
    return RedirectResponse(url=f"/shifts?message={quote(message)}", status_code=303)


@router.post("/shifts/fallback")
def save_fallback(choice: str = Form(...), db: Session = Depends(get_db)):
    set_fallback_choice(db, choice)
    return RedirectResponse(url=f"/shifts?message={quote('Saved.')}", status_code=303)
