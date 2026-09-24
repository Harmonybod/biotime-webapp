from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.biotime_client import BioTimeClient, get_biotime_client

router = APIRouter(prefix="/api/employees", tags=["employees"])

# Safety cap so a live lookup can't drag in an entire large workforce table
# on every form load.
MAX_RECORDS = 500


def _department_name(department) -> str:
    if isinstance(department, dict):
        return department.get("dept_name") or department.get("name") or ""
    return department or ""


@router.get("")
def search_employees(
    search: str = Query("", description="Substring match on emp_code or name"),
    limit: int = Query(200, le=MAX_RECORDS),
    client: BioTimeClient = Depends(get_biotime_client),
):
    """Live lookup against BioTime, for populating the employee picker."""
    needle = search.strip().lower()
    results = []

    for record in client.iter_all_employees(page_size=100):
        if len(results) >= limit and not needle:
            break
        if len(results) >= MAX_RECORDS:
            break

        emp_code = record.get("emp_code") or ""
        first = record.get("first_name") or ""
        last = record.get("last_name") or ""
        name = f"{first} {last}".strip()
        dept = _department_name(record.get("department"))

        if needle and needle not in emp_code.lower() and needle not in name.lower():
            continue

        results.append(
            {
                "id": record.get("id"),
                "emp_code": emp_code,
                "name": name,
                "department": dept,
            }
        )

        if needle and len(results) >= limit:
            break

    return results
