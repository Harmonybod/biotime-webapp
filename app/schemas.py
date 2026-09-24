from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    biotime_id: Optional[int]
    emp_code: Optional[str]
    employee_name: Optional[str]
    department: Optional[str]
    pay_code: Optional[int]
    pay_code_name: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    leave_day: Optional[float]
    apply_reason: Optional[str]
    apply_time: Optional[datetime]
    approval_status: Optional[int]
    approval_status_display: Optional[str]
    approval_remark: Optional[str]
    approval_time: Optional[datetime]
    approver: Optional[str]
    last_approver: Optional[str]
    synced_at: Optional[datetime]


class LeaveRequestCreate(BaseModel):
    employee: str
    pay_code: int
    start_time: str  # "YYYY-MM-DD HH:MM:SS", per BioTime's expected format
    end_time: str
    apply_reason: str = ""


class SyncResult(BaseModel):
    created: int
    updated: int
