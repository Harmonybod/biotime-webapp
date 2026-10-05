from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.attendance import Schedule, build_report
from app.biotime_client import BioTimeClient, BioTimeError, get_biotime_client
from app.database import get_db
from app.models import LeaveRequest
from app.routers.employees import MAX_RECORDS, _department_name

router = APIRouter(tags=["reports"])
templates = Jinja2Templates(directory="app/templates")

MAX_RANGE_DAYS = 93

REPORTS = {
    "worked-hours": {"title": "Worked Hours", "nav": "Worked Hours"},
    "absence": {"title": "Absence Report", "nav": "Absence"},
    "late-arrivals": {"title": "Late Arrivals", "nav": "Late Arrivals"},
}


def _fetch_employees(client: BioTimeClient) -> list[dict]:
    employees = []
    for record in client.iter_all_employees(page_size=100):
        first = record.get("first_name") or ""
        last = record.get("last_name") or ""
        employees.append(
            {
                "emp_code": record.get("emp_code") or "",
                "name": f"{first} {last}".strip(),
                "department": _department_name(record.get("department")),
            }
        )
        if len(employees) >= MAX_RECORDS:
            break
    return sorted(employees, key=lambda e: (len(e["emp_code"]), e["emp_code"]))


def _approved_leaves(db: Session, start: date, end: date, emp_code: Optional[str]):
    query = db.query(LeaveRequest).filter(
        LeaveRequest.approval_status == 2,
        LeaveRequest.start_time <= datetime.combine(end, time.max),
        LeaveRequest.end_time >= datetime.combine(start, time.min),
    )
    if emp_code:
        query = query.filter(LeaveRequest.emp_code == emp_code)
    return [(row.emp_code, row.start_time, row.end_time) for row in query]


def _validate_range(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range is limited to {MAX_RANGE_DAYS} days")


def _run_report(
    client: BioTimeClient,
    db: Session,
    start: date,
    end: date,
    emp_code: Optional[str],
    employees: Optional[list[dict]] = None,
):
    employees = employees if employees is not None else _fetch_employees(client)
    if emp_code:
        employees = [e for e in employees if e["emp_code"] == emp_code]

    filters = {
        "start_time": f"{start.isoformat()} 00:00:00",
        "end_time": f"{end.isoformat()} 23:59:59",
    }
    if emp_code:
        filters["emp_code"] = emp_code
    transactions = list(client.iter_all_transactions(**filters))

    return build_report(
        employees,
        transactions,
        _approved_leaves(db, start, end, emp_code),
        start,
        end,
        Schedule.from_settings(),
    )


# ---------------------------------------------------------------------- #
# JSON API (shape follows the Attendance Report API spec)
# ---------------------------------------------------------------------- #
@router.get("/api/reports/attendance")
def api_attendance_report(
    start_date: date,
    end_date: date,
    emp_code: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_RECORDS),
    db: Session = Depends(get_db),
    client: BioTimeClient = Depends(get_biotime_client),
):
    _validate_range(start_date, end_date)
    reports = _run_report(client, db, start_date, end_date, emp_code)
    offset = (page - 1) * page_size
    return {
        "count": len(reports),
        "page": page,
        "page_size": page_size,
        "data": [r.to_dict(include_days=bool(emp_code)) for r in reports[offset : offset + page_size]],
    }


# ---------------------------------------------------------------------- #
# HTML pages
# ---------------------------------------------------------------------- #
@router.get("/reports/{kind}")
def report_page(
    kind: str,
    request: Request,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    emp_code: Optional[str] = None,
    db: Session = Depends(get_db),
    client: BioTimeClient = Depends(get_biotime_client),
):
    if kind not in REPORTS:
        raise HTTPException(status_code=404, detail="Unknown report")

    today = date.today()
    start = start_date or today.replace(day=1)
    end = end_date or today
    emp_code = emp_code or None

    context = {
        "request": request,
        "kind": kind,
        "report": REPORTS[kind],
        "reports_nav": REPORTS,
        "filters": {"start_date": start.isoformat(), "end_date": end.isoformat(), "emp_code": emp_code or ""},
        "schedule": Schedule.from_settings(),
        "employees": [],
        "results": [],
        "selected": None,
        "error": None,
    }

    try:
        _validate_range(start, end)
        employees = _fetch_employees(client)
        context["employees"] = employees
        results = _run_report(client, db, start, end, emp_code, employees)
        context["results"] = results
        if emp_code and results:
            context["selected"] = results[0]
        elif emp_code:
            context["error"] = f"No employee with code {emp_code}."
    except HTTPException as exc:
        context["error"] = exc.detail
    except BioTimeError as exc:
        context["error"] = f"Could not load data from BioTime: {exc.message}"

    return templates.TemplateResponse("report.html", context)
