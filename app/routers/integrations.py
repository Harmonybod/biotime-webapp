from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["integrations"])
templates = Jinja2Templates(directory="app/templates")

# APIs a client's ERP can actually call today.
AVAILABLE_APIS = [
    {
        "name": "Leave Report",
        "method": "GET",
        "path": "/api/leaves",
        "description": "Cached leave requests, optionally filtered by department, employee code, or approval status.",
        "params": "department, emp_code, approval_status (all optional)",
        "status": "available",
    },
    {
        "name": "Attendance Report (Worked Hours, Absence, Late Arrivals)",
        "method": "GET",
        "path": "/api/reports/attendance",
        "description": "Worked, expected, absent and late hours per employee, calculated from BioTime punches. "
        "Passing emp_code also returns a day-by-day breakdown.",
        "params": "start_date, end_date (required, YYYY-MM-DD); emp_code, page, page_size (optional)",
        "status": "available",
    },
]

# Reports that follow the same pattern but aren't built yet — shown so the
# team can offer them in client conversations without promising a live path.
PLANNED_APIS: list[dict] = []


@router.get("/integrations")
def integrations_page(request: Request):
    return templates.TemplateResponse(
        "integrations.html",
        {
            "request": request,
            "available_apis": AVAILABLE_APIS,
            "planned_apis": PLANNED_APIS,
        },
    )
