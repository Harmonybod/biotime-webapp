from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.biotime_client import BioTimeClient, BioTimeError, get_biotime_client
from app.database import get_db
from app.models import LeaveRequest
from app.pay_codes import PAY_CODES
from app.schemas import LeaveRequestCreate, LeaveRequestOut, SyncResult
from app.sync import record_to_row_fields, sync_leaves

router = APIRouter(tags=["leaves"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------- #
# JSON API
# ---------------------------------------------------------------------- #
@router.get("/api/leaves", response_model=list[LeaveRequestOut])
def api_list_leaves(
    department: Optional[str] = None,
    emp_code: Optional[str] = None,
    approval_status: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(LeaveRequest)
    if department:
        query = query.filter(LeaveRequest.department == department)
    if emp_code:
        query = query.filter(LeaveRequest.emp_code == emp_code)
    if approval_status is not None:
        query = query.filter(LeaveRequest.approval_status == approval_status)
    return query.order_by(LeaveRequest.start_time.desc()).all()


@router.post("/api/sync", response_model=SyncResult)
def api_sync(db: Session = Depends(get_db), client: BioTimeClient = Depends(get_biotime_client)):
    return sync_leaves(db, client)


@router.post("/api/leaves", response_model=LeaveRequestOut)
def api_create_leave(
    body: LeaveRequestCreate,
    db: Session = Depends(get_db),
    client: BioTimeClient = Depends(get_biotime_client),
):
    record = client.create_leave(
        employee=body.employee,
        pay_code=body.pay_code,
        start_time=body.start_time,
        end_time=body.end_time,
        apply_reason=body.apply_reason,
    )
    data = record.get("data", record)
    fields = record_to_row_fields(data)
    row = LeaveRequest(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------- #
# HTML pages
# ---------------------------------------------------------------------- #
@router.get("/")
def root():
    return RedirectResponse(url="/leaves")


@router.get("/leaves")
def leaves_page(
    request: Request,
    department: Optional[str] = None,
    emp_code: Optional[str] = None,
    approval_status: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(LeaveRequest)
    if department:
        query = query.filter(LeaveRequest.department == department)
    if emp_code:
        query = query.filter(LeaveRequest.emp_code == emp_code)
    if approval_status not in (None, ""):
        query = query.filter(LeaveRequest.approval_status == int(approval_status))

    leaves = query.order_by(LeaveRequest.start_time.desc()).all()
    departments = [d for (d,) in db.query(LeaveRequest.department).distinct() if d]

    return templates.TemplateResponse(
        "leaves_list.html",
        {
            "request": request,
            "leaves": leaves,
            "departments": sorted(departments),
            "filters": {
                "department": department or "",
                "emp_code": emp_code or "",
                "approval_status": approval_status or "",
            },
            "message": message,
            "error": error,
        },
    )


@router.post("/sync")
def sync_action(db: Session = Depends(get_db), client: BioTimeClient = Depends(get_biotime_client)):
    try:
        result = sync_leaves(db, client)
        message = f"Synced: {result['created']} new, {result['updated']} updated."
        return RedirectResponse(url=f"/leaves?message={message}", status_code=303)
    except BioTimeError as exc:
        return RedirectResponse(url=f"/leaves?error={exc.message}", status_code=303)


@router.get("/leaves/new")
def new_leave_form(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        "leave_form.html",
        {"request": request, "pay_codes": PAY_CODES, "error": error},
    )


@router.post("/leaves/new")
def submit_leave(
    request: Request,
    employee: str = Form(...),
    pay_code: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    apply_reason: str = Form(""),
    db: Session = Depends(get_db),
    client: BioTimeClient = Depends(get_biotime_client),
):
    try:
        record = client.create_leave(
            employee=employee,
            pay_code=pay_code,
            start_time=start_time,
            end_time=end_time,
            apply_reason=apply_reason,
        )
    except BioTimeError as exc:
        return templates.TemplateResponse(
            "leave_form.html",
            {"request": request, "pay_codes": PAY_CODES, "error": exc.message},
            status_code=400,
        )

    data = record.get("data", record)
    fields = record_to_row_fields(data)
    db.add(LeaveRequest(**fields))
    db.commit()

    return RedirectResponse(url="/leaves?message=Leave request submitted.", status_code=303)
