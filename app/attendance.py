"""Worked hours / absence / late-arrival calculations from raw BioTime punches.

BioTime's own attendance reports stay empty unless shifts are scheduled and
its attendance calculation has run, and shift assignments aren't exposed over
the REST API. So these reports are computed here from the raw transactions,
against the single work schedule configured in settings.

Rules:
- Punches are grouped by calendar day and paired in time order
  (1st-2nd, 3rd-4th, ...). Devices often record every punch as "Check In",
  so punch_state is ignored. An odd punch count leaves the last punch
  unpaired and the day is flagged as having a missing punch.
- A scheduled workday with no punches and no approved leave is an absence;
  its absent hours are the full expected hours for that day.
- Late = first punch of a scheduled workday after shift start + grace.
- Only completed days count: today is left out until it is over (an employee
  who hasn't arrived yet isn't absent, and one still at work has no
  check-out yet). Days after today are ignored too.
- Shifts crossing midnight are not supported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional

from app.config import settings


@dataclass(frozen=True)
class Schedule:
    start: time
    end: time
    break_minutes: int
    work_days: frozenset[int]
    grace_minutes: int

    @property
    def expected_hours(self) -> float:
        span = datetime.combine(date.min, self.end) - datetime.combine(date.min, self.start)
        return max(span.total_seconds() / 3600 - self.break_minutes / 60, 0.0)

    @classmethod
    def from_settings(cls) -> "Schedule":
        return cls(
            start=time.fromisoformat(settings.shift_start),
            end=time.fromisoformat(settings.shift_end),
            break_minutes=settings.shift_break_minutes,
            work_days=frozenset(int(d) for d in settings.shift_work_days.split(",") if d.strip()),
            grace_minutes=settings.late_grace_minutes,
        )


@dataclass
class DayResult:
    day: date
    status: str  # Present, Absent, On leave, Off day, Worked on off day
    punches: list[datetime] = field(default_factory=list)
    worked_hours: float = 0.0
    expected_hours: float = 0.0
    absent_hours: float = 0.0
    late_minutes: float = 0.0
    missing_punch: bool = False

    @property
    def first_in(self) -> Optional[datetime]:
        return self.punches[0] if self.punches else None

    @property
    def last_out(self) -> Optional[datetime]:
        return self.punches[-1] if len(self.punches) > 1 else None


@dataclass
class EmployeeReport:
    emp_code: str
    name: str
    department: str
    days: list[DayResult]

    @property
    def worked_hours(self) -> float:
        return round(sum(d.worked_hours for d in self.days), 2)

    @property
    def expected_hours(self) -> float:
        return round(sum(d.expected_hours for d in self.days), 2)

    @property
    def absent_hours(self) -> float:
        return round(sum(d.absent_hours for d in self.days), 2)

    @property
    def absent_days(self) -> int:
        return sum(1 for d in self.days if d.status == "Absent")

    @property
    def present_days(self) -> int:
        return sum(1 for d in self.days if d.punches)

    @property
    def leave_days(self) -> int:
        return sum(1 for d in self.days if d.status == "On leave")

    @property
    def late_count(self) -> int:
        return sum(1 for d in self.days if d.late_minutes > 0)

    @property
    def late_hours(self) -> float:
        return round(sum(d.late_minutes for d in self.days) / 60, 2)

    @property
    def missing_punch_days(self) -> int:
        return sum(1 for d in self.days if d.missing_punch)

    def to_dict(self, metrics: Optional[list[str]] = None, include_days: bool = False) -> dict:
        """metrics: field names from METRICS (default: all of them)."""
        metrics = metrics or ALL_METRICS
        values = {
            "worked_hours": self.worked_hours,
            "expected_work_hours": self.expected_hours,
            "present_days": self.present_days,
            "missing_punch_days": self.missing_punch_days,
            "absent_hours": self.absent_hours,
            "absent_days": self.absent_days,
            "leave_days": self.leave_days,
            "late_hours": self.late_hours,
            "late_count": self.late_count,
        }
        data = {"emp_code": self.emp_code, "name": self.name, "department": self.department}
        data.update({m: values[m] for m in metrics})

        if include_days:
            groups = {METRIC_GROUP[m] for m in metrics}
            data["days"] = [_day_dict(d, groups) for d in self.days]
        return data


def _day_dict(d: DayResult, groups: set[str]) -> dict:
    day = {"date": d.day.isoformat(), "status": d.status}
    if "worked" in groups:
        day["punches"] = [p.strftime("%H:%M:%S") for p in d.punches]
        day["worked_hours"] = d.worked_hours
        day["expected_hours"] = d.expected_hours
        day["missing_punch"] = d.missing_punch
    if "absence" in groups:
        day["absent_hours"] = d.absent_hours
    if "late" in groups:
        day["first_punch"] = d.first_in.strftime("%H:%M:%S") if d.first_in else None
        day["late_minutes"] = d.late_minutes
    return day


# Metrics an API client can ask for, by group. A client can pass group names
# (worked, absence, late) or individual field names.
METRICS = {
    "worked": ["worked_hours", "expected_work_hours", "present_days", "missing_punch_days"],
    "absence": ["absent_hours", "absent_days", "leave_days"],
    "late": ["late_hours", "late_count"],
}
ALL_METRICS = [m for fields in METRICS.values() for m in fields]
METRIC_GROUP = {m: group for group, fields in METRICS.items() for m in fields}


def resolve_metrics(value: Optional[str]) -> list[str]:
    """Turn "worked,late_count" into field names, in canonical order. Raises ValueError."""
    if not value or not value.strip():
        return ALL_METRICS
    wanted: set[str] = set()
    unknown = []
    for item in (part.strip().lower() for part in value.split(",")):
        if not item:
            continue
        if item in METRICS:
            wanted.update(METRICS[item])
        elif item in METRIC_GROUP:
            wanted.add(item)
        else:
            unknown.append(item)
    if unknown:
        raise ValueError(
            f"Unknown metrics: {', '.join(unknown)}. "
            f"Use groups ({', '.join(METRICS)}) or fields ({', '.join(ALL_METRICS)})."
        )
    return [m for m in ALL_METRICS if m in wanted]


def parse_punch_time(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def worked_hours_for(punches: list[datetime]) -> tuple[float, bool]:
    """Sum paired in/out durations. Returns (hours, missing_punch)."""
    total = timedelta()
    for i in range(0, len(punches) - 1, 2):
        total += punches[i + 1] - punches[i]
    return round(total.total_seconds() / 3600, 2), len(punches) % 2 == 1


def build_day(
    day: date,
    punches: list[datetime],
    schedule: Schedule,
    on_leave: bool,
) -> DayResult:
    punches = sorted(punches)
    scheduled = day.weekday() in schedule.work_days
    worked, missing = worked_hours_for(punches)

    result = DayResult(day=day, status="", punches=punches, worked_hours=worked, missing_punch=missing)

    if not scheduled:
        result.status = "Worked on off day" if punches else "Off day"
        return result

    if on_leave:
        result.status = "On leave"
        return result

    result.expected_hours = round(schedule.expected_hours, 2)

    if not punches:
        result.status = "Absent"
        result.absent_hours = result.expected_hours
        return result

    result.status = "Present"
    shift_start = datetime.combine(day, schedule.start) + timedelta(minutes=schedule.grace_minutes)
    if punches[0] > shift_start:
        late = punches[0] - datetime.combine(day, schedule.start)
        result.late_minutes = round(late.total_seconds() / 60, 1)
    return result


def last_counted_day(today: Optional[date] = None, include_today: bool = False) -> date:
    today = today or date.today()
    return today if include_today else today - timedelta(days=1)


def build_report(
    employees: Iterable[dict],
    transactions: Iterable[dict],
    leaves: Iterable[tuple[str, datetime, datetime]],
    start: date,
    end: date,
    schedule: Schedule,
    today: Optional[date] = None,
    include_today: bool = False,
) -> list[EmployeeReport]:
    """employees: dicts with emp_code/name/department.
    transactions: raw BioTime transaction records.
    leaves: (emp_code, start_time, end_time) of approved leaves.
    include_today: count today even though it isn't over (used for "late
    today so far", where a check-in is already final).
    """
    today = today or date.today()
    last_day = min(end, last_counted_day(today, include_today))

    punches_by_emp: dict[str, dict[date, list[datetime]]] = {}
    for record in transactions:
        punch = parse_punch_time(record.get("punch_time"))
        if punch is None:
            continue
        code = str(record.get("emp_code") or "")
        punches_by_emp.setdefault(code, {}).setdefault(punch.date(), []).append(punch)

    leave_days_by_emp: dict[str, set[date]] = {}
    for emp_code, leave_start, leave_end in leaves:
        if not leave_start or not leave_end:
            continue
        d = leave_start.date()
        while d <= leave_end.date():
            leave_days_by_emp.setdefault(emp_code, set()).add(d)
            d += timedelta(days=1)

    reports = []
    for emp in employees:
        code = str(emp["emp_code"])
        emp_punches = punches_by_emp.get(code, {})
        emp_leaves = leave_days_by_emp.get(code, set())
        days = []
        d = start
        while d <= last_day:
            days.append(build_day(d, emp_punches.get(d, []), schedule, d in emp_leaves))
            d += timedelta(days=1)
        reports.append(
            EmployeeReport(
                emp_code=code,
                name=emp.get("name") or "",
                department=emp.get("department") or "",
                days=days,
            )
        )
    return reports
