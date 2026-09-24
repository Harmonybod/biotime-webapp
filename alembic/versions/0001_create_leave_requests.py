"""create leave_requests table

Revision ID: 0001
Revises:
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biotime_id", sa.Integer(), nullable=True),
        sa.Column("emp_code", sa.String(), nullable=True),
        sa.Column("employee_name", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("pay_code", sa.Integer(), nullable=True),
        sa.Column("pay_code_name", sa.String(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("leave_day", sa.Numeric(), nullable=True),
        sa.Column("apply_reason", sa.Text(), nullable=True),
        sa.Column("apply_time", sa.DateTime(), nullable=True),
        sa.Column("approval_status", sa.Integer(), nullable=True),
        sa.Column("approval_status_display", sa.String(), nullable=True),
        sa.Column("approval_remark", sa.Text(), nullable=True),
        sa.Column("approval_time", sa.DateTime(), nullable=True),
        sa.Column("approver", sa.String(), nullable=True),
        sa.Column("last_approver", sa.String(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leave_requests_biotime_id", "leave_requests", ["biotime_id"], unique=True)
    op.create_index("ix_leave_requests_emp_code", "leave_requests", ["emp_code"])
    op.create_index("ix_leave_requests_department", "leave_requests", ["department"])
    op.create_index("ix_leave_requests_approval_status", "leave_requests", ["approval_status"])


def downgrade() -> None:
    op.drop_index("ix_leave_requests_approval_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_department", table_name="leave_requests")
    op.drop_index("ix_leave_requests_emp_code", table_name="leave_requests")
    op.drop_index("ix_leave_requests_biotime_id", table_name="leave_requests")
    op.drop_table("leave_requests")
