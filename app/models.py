from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.sql import expression

from app.database import Base


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True)
    biotime_id = Column(Integer, unique=True, nullable=True, index=True)

    emp_code = Column(String, index=True)
    employee_name = Column(String)
    department = Column(String, index=True)

    pay_code = Column(Integer)
    pay_code_name = Column(String)

    start_time = Column(DateTime)
    end_time = Column(DateTime)
    leave_day = Column(Numeric, nullable=True)

    apply_reason = Column(Text)
    apply_time = Column(DateTime, nullable=True)

    approval_status = Column(Integer, index=True)
    approval_status_display = Column(String)
    approval_remark = Column(Text, nullable=True)
    approval_time = Column(DateTime, nullable=True)
    approver = Column(String, nullable=True)
    last_approver = Column(String, nullable=True)

    synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=expression.func.now(),
        nullable=False,
    )


class BioTimeConnection(Base):
    """The BioTime server this install talks to, entered on the /setup page.

    Single row. Stored locally so each person's copy of the app points at
    their own BioTime without editing any files.
    """

    __tablename__ = "biotime_connection"

    id = Column(Integer, primary_key=True)
    base_url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
