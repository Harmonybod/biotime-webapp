from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.biotime_client import BioTimeClient, BioTimeError, get_biotime_client
from app.routers.reports import fetch_employees
from app.templating import templates

router = APIRouter(tags=["punches"])

CHECK_IN = "0"
CHECK_OUT = "1"
RECENT_LIMIT = 100


def _redirect(message: str = "", error: str = "") -> RedirectResponse:
    params = f"message={quote(message)}" if message else f"error={quote(error)}"
    return RedirectResponse(url=f"/punches?{params}", status_code=303)


def _parse_time(value: str) -> Optional[time]:
    value = value.strip()
    return time.fromisoformat(value) if value else None


@router.get("/punches")
def punches_page(
    request: Request,
    emp_code: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    client: BioTimeClient = Depends(get_biotime_client),
):
    employees, logs = [], []
    try:
        employees = fetch_employees(client)
        filters = {"emp_code": emp_code} if emp_code else {}
        logs = [
            log
            for log in client.iter_all_manual_logs(**filters)
            if not emp_code or log.get("emp_code") == emp_code
        ]
        logs.sort(key=lambda log: log.get("punch_time") or "", reverse=True)
    except BioTimeError as exc:
        error = f"Could not load data from BioTime: {exc.message}"

    return templates.TemplateResponse(
        "punches.html",
        {
            "request": request,
            "employees": employees,
            "logs": logs[:RECENT_LIMIT],
            "total_logs": len(logs),
            "filters": {"emp_code": emp_code or ""},
            "today": date.today().isoformat(),
            "message": message,
            "error": error,
        },
    )


@router.post("/punches")
def add_punches(
    emp_code: str = Form(...),
    punch_date: date = Form(...),
    check_in: str = Form(""),
    check_out: str = Form(""),
    apply_reason: str = Form(""),
    approve: bool = Form(False),
    client: BioTimeClient = Depends(get_biotime_client),
):
    try:
        in_time, out_time = _parse_time(check_in), _parse_time(check_out)
    except ValueError:
        return _redirect(error="Enter times as HH:MM.")
    if not in_time and not out_time:
        return _redirect(error="Enter a check-in time, a check-out time, or both.")
    if in_time and out_time and out_time <= in_time:
        return _redirect(error="Check-out must be after check-in.")

    punches = []
    if in_time:
        punches.append((CHECK_IN, datetime.combine(punch_date, in_time)))
    if out_time:
        punches.append((CHECK_OUT, datetime.combine(punch_date, out_time)))

    try:
        employee = next((e for e in fetch_employees(client) if e["emp_code"] == emp_code), None)
        if employee is None:
            return _redirect(error=f"No employee with code {emp_code}.")

        added, not_approved = [], []
        for state, punch_time in punches:
            label = "check-in" if state == CHECK_IN else "check-out"
            record = client.create_manual_log(
                employee=employee["id"],
                emp_code=emp_code,
                punch_time=punch_time.strftime("%Y-%m-%d %H:%M:%S"),
                punch_state=state,
                apply_reason=apply_reason.strip(),
            )
            added.append(f"{label} {punch_time:%H:%M}")
            if approve and record and record.get("approval_status") != 2:
                try:
                    client.approve_manual_log(record["id"])
                except BioTimeError:
                    not_approved.append(label)
            elif approve and not record:
                not_approved.append(label)
    except BioTimeError as exc:
        return _redirect(error=f"BioTime refused the punch: {exc.message}")

    message = f"Added {' and '.join(added)} for {employee['name'] or emp_code} on {punch_date:%d %b %Y}."
    if not approve:
        message += " Waiting for approval in BioTime."
    if not_approved:
        message += (
            f" Could not approve the {' and '.join(not_approved)} automatically; "
            "approve it in BioTime (Attendance → Manual Log)."
        )
    return _redirect(message=message)


@router.post("/punches/{log_id}/approve")
def approve_punch(log_id: int, client: BioTimeClient = Depends(get_biotime_client)):
    try:
        client.approve_manual_log(log_id)
    except BioTimeError as exc:
        return _redirect(error=f"Could not approve: {exc.message}")
    return _redirect(message="Punch approved.")


@router.post("/punches/{log_id}/delete")
def delete_punch(log_id: int, client: BioTimeClient = Depends(get_biotime_client)):
    try:
        client.delete_manual_log(log_id)
    except BioTimeError as exc:
        return _redirect(error=f"Could not delete: {exc.message}")
    return _redirect(message="Punch deleted.")
