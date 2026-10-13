"""Work schedules synced from BioTime.

BioTime describes schedules in four parts, all readable over its API:
- timetables ("timeintervals"): a working period, e.g. 09:00-18:00, 540 work minutes
- shifts ("attshifts" + "shift_details"): which timetable(s) apply on each day
  of a repeating cycle (weekly, daily or monthly)
- schedules ("attschedules"): which shift an employee follows, from/to a date
- one-off changes ("tempschedules") and holidays ("holidays")

`sync_shifts` copies all of it into the local database (so reports don't hit
BioTime for it every time); `ShiftData.schedule_for` then answers "what was
this employee scheduled to work on this day?".

Employees with no schedule in BioTime follow a fallback chosen on the Work
Schedule page: one of the BioTime shifts, the app's default schedule from
.env (SHIFT_*), or "not scheduled" (no expected hours, no absence/lateness).

Assumption: for weekly shifts BioTime numbers days from Sunday (day 0 =
Sunday, 1 = Monday ... 6 = Saturday). Shifts crossing midnight count their
expected hours, but punches are still grouped per calendar day.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.biotime_client import BioTimeClient, BioTimeError
from app.config import settings
from app.settings_store import delete_settings, get_setting, set_setting

logger = logging.getLogger(__name__)

SNAPSHOT_KEY = "shift_snapshot"
FALLBACK_KEY = "unscheduled_shift"
FALLBACK_NONE = "none"
FALLBACK_APP_DEFAULT = "settings"

WEEKDAYS_FROM_SUNDAY = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
# Display order on the Work Schedule page (BioTime day index for Monday..Sunday).
DISPLAY_WEEK = [1, 2, 3, 4, 5, 6, 0]

REQUIRED_SOURCES = {
    "timeintervals": "/att/api/timeintervals/",
    "attshifts": "/att/api/attshifts/",
    "shift_details": "/att/api/shift_details/",
    "attschedules": "/att/api/attschedules/",
}
OPTIONAL_SOURCES = {
    "tempschedules": "/att/api/tempschedules/",
    "holidays": "/att/api/holidays/",
}


# ---------------------------------------------------------------------- #
# Model
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class TimeSlot:
    name: str
    start: time
    end: time
    work_minutes: float
    cross_day: bool = False

    @property
    def label(self) -> str:
        return f"{self.start:%H:%M}–{self.end:%H:%M}"


@dataclass(frozen=True)
class DaySchedule:
    """What an employee was scheduled for on one day."""

    shift_name: str
    slots: tuple[TimeSlot, ...] = ()
    holiday: Optional[str] = None

    @property
    def is_workday(self) -> bool:
        return bool(self.slots) and not self.holiday

    @property
    def start(self) -> Optional[time]:
        return min(s.start for s in self.slots) if self.slots else None

    @property
    def expected_hours(self) -> float:
        return round(sum(s.work_minutes for s in self.slots) / 60, 2) if self.is_workday else 0.0


@dataclass
class Shift:
    id: int
    name: str
    cycle_unit: str  # "Week", "Day" or "Month"
    cycle: int
    days: dict[int, list[TimeSlot]] = field(default_factory=dict)

    def day_index(self, day: date, anchor: date) -> int:
        n = max(self.cycle or 1, 1)
        unit = (self.cycle_unit or "Week").lower()
        if unit.startswith("week"):
            from_sunday = (day.weekday() + 1) % 7
            anchor_sunday = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
            return ((day - anchor_sunday).days // 7 % n) * 7 + from_sunday
        if unit.startswith("month"):
            months = (day.year - anchor.year) * 12 + day.month - anchor.month
            return (months % n) * 31 + day.day - 1
        return (day - anchor).days % n

    def schedule_for(self, day: date, anchor: date) -> DaySchedule:
        return DaySchedule(self.name, tuple(self.days.get(self.day_index(day, anchor), [])))

    @property
    def weekly_hours(self) -> Optional[float]:
        if (self.cycle_unit or "").lower().startswith("week") and (self.cycle or 1) == 1:
            return round(sum(s.work_minutes for slots in self.days.values() for s in slots) / 60, 2)
        return None

    def display_days(self) -> list[tuple[str, list[TimeSlot]]]:
        """(label, slots) rows for the Work Schedule page."""
        unit = (self.cycle_unit or "Week").lower()
        n = max(self.cycle or 1, 1)
        if unit.startswith("week"):
            rows = []
            for week in range(n):
                prefix = f"Week {week + 1}, " if n > 1 else ""
                for idx in DISPLAY_WEEK:
                    rows.append((prefix + WEEKDAYS_FROM_SUNDAY[idx], self.days.get(week * 7 + idx, [])))
            return rows
        if unit.startswith("month"):
            return [(f"Day {i + 1} of the month", self.days.get(i, [])) for i in range(31 * n) if i in self.days]
        return [(f"Day {i + 1}", self.days.get(i, [])) for i in range(n)]


@dataclass
class Assignment:
    employee_id: int
    shift_id: int
    start: date
    end: date


def _parse_time(value) -> Optional[time]:
    try:
        return time.fromisoformat(str(value)[:8])
    except (TypeError, ValueError):
        return None


def _parse_date(value) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _parse_datetime(value) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("T", " ")[:19])
    except (TypeError, ValueError):
        return None


def _minutes(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _slot_from_interval(record: dict) -> Optional[TimeSlot]:
    start = _parse_time(record.get("in_time"))
    if start is None:
        return None
    duration = _minutes(record.get("duration")) or 0.0
    end = _parse_time(record.get("out_time")) or (datetime.combine(date.min, start) + timedelta(minutes=duration)).time()
    work = _minutes(record.get("work_time_duration"))
    if work is None:
        work = max(duration - (_minutes(record.get("break_time_duration")) or 0.0), 0.0)
    return TimeSlot(
        name=record.get("alias") or f"Timetable {record.get('id')}",
        start=start,
        end=end,
        work_minutes=work,
        cross_day=bool(record.get("cross_day")),
    )


def app_default_shift() -> Shift:
    """The schedule from .env (SHIFT_*), as a weekly shift."""
    start, end = time.fromisoformat(settings.shift_start), time.fromisoformat(settings.shift_end)
    span = (datetime.combine(date.min, end) - datetime.combine(date.min, start)).total_seconds() / 60
    slot = TimeSlot("App default", start, end, max(span - settings.shift_break_minutes, 0.0))
    monday_based = [int(d) for d in settings.shift_work_days.split(",") if d.strip()]
    return Shift(-1, "App default schedule", "Week", 1, {(d + 1) % 7: [slot] for d in monday_based})


@dataclass
class ShiftData:
    synced_at: Optional[datetime]
    slots: dict[int, TimeSlot]
    shifts: dict[int, Shift]
    assignments: list[Assignment]
    temp: dict[tuple[int, date], list[TimeSlot]]
    holidays: list[tuple[str, date, date]]

    @classmethod
    def from_raw(cls, raw: dict) -> "ShiftData":
        slots = {}
        for record in raw.get("timeintervals", []):
            slot = _slot_from_interval(record)
            if slot and record.get("id") is not None:
                slots[record["id"]] = slot

        shifts = {
            record["id"]: Shift(
                id=record["id"],
                name=record.get("alias") or f"Shift {record['id']}",
                cycle_unit=record.get("cycle_unit") or "Week",
                cycle=int(record.get("shift_cycle") or 1),
            )
            for record in raw.get("attshifts", [])
            if record.get("id") is not None
        }
        for detail in raw.get("shift_details", []):
            shift = shifts.get(detail.get("shift"))
            slot = slots.get(detail.get("time_interval"))
            if shift and slot and detail.get("day_index") is not None:
                shift.days.setdefault(int(detail["day_index"]), []).append(slot)
        for shift in shifts.values():
            for day_slots in shift.days.values():
                day_slots.sort(key=lambda s: s.start)

        assignments = []
        for record in raw.get("attschedules", []):
            start, end = _parse_date(record.get("start_date")), _parse_date(record.get("end_date"))
            if record.get("employee") is not None and record.get("shift") in shifts and start and end:
                assignments.append(Assignment(record["employee"], record["shift"], start, end))
        assignments.sort(key=lambda a: a.start)

        temp: dict[tuple[int, date], list[TimeSlot]] = {}
        for record in raw.get("tempschedules", []):
            start, end = _parse_datetime(record.get("start_time")), _parse_datetime(record.get("end_time"))
            if record.get("employee") is None or not start or not end or end <= start:
                continue
            slot = TimeSlot("Temporary schedule", start.time(), end.time(),
                            (end - start).total_seconds() / 60, cross_day=end.date() > start.date())
            temp.setdefault((record["employee"], start.date()), []).append(slot)

        holidays = []
        for record in raw.get("holidays", []):
            start = _parse_date(record.get("start_date") or record.get("start_time"))
            if not start:
                continue
            end = _parse_date(record.get("end_date") or record.get("end_time"))
            if end is None:
                days = int(_minutes(record.get("duration_day")) or 1)
                end = start + timedelta(days=max(days, 1) - 1)
            holidays.append((record.get("alias") or "Holiday", start, end))

        return cls(_parse_datetime(raw.get("synced_at")), slots, shifts, assignments, temp, holidays)

    # -------------------------------------------------------------- #
    def scheduled_employee_ids(self) -> set[int]:
        return {a.employee_id for a in self.assignments}

    def holiday_on(self, day: date) -> Optional[str]:
        return next((name for name, start, end in self.holidays if start <= day <= end), None)

    def default_fallback(self) -> str:
        if len(self.shifts) == 1:
            return str(next(iter(self.shifts)))
        return FALLBACK_APP_DEFAULT if not self.shifts else FALLBACK_NONE

    def fallback_shift(self, choice: str) -> Optional[Shift]:
        if choice == FALLBACK_APP_DEFAULT:
            return app_default_shift()
        if choice.isdigit() and int(choice) in self.shifts:
            return self.shifts[int(choice)]
        return None

    def resolver(self, fallback_choice: str) -> Callable[[dict, date], Optional[DaySchedule]]:
        """Returns schedule_for(employee, day): None means "not scheduled"."""
        fallback = self.fallback_shift(fallback_choice)
        by_employee: dict[int, list[Assignment]] = {}
        for a in self.assignments:
            by_employee.setdefault(a.employee_id, []).append(a)

        def schedule_for(employee: dict, day: date) -> Optional[DaySchedule]:
            emp_id = employee.get("id")
            base: Optional[DaySchedule] = None
            if (emp_id, day) in self.temp:
                base = DaySchedule("Temporary schedule", tuple(sorted(self.temp[(emp_id, day)], key=lambda s: s.start)))
            else:
                current = [a for a in by_employee.get(emp_id, []) if a.start <= day <= a.end]
                if current:
                    a = current[-1]  # latest-starting schedule wins if they overlap
                    base = self.shifts[a.shift_id].schedule_for(day, a.start)
                elif emp_id not in by_employee and fallback:
                    base = fallback.schedule_for(day, date(2000, 1, 2))
            if base is None:
                return None
            holiday = self.holiday_on(day)
            return DaySchedule(base.shift_name, base.slots, holiday) if holiday else base

        return schedule_for


# ---------------------------------------------------------------------- #
# Sync / storage
# ---------------------------------------------------------------------- #
def sync_shifts(db: Session, client: BioTimeClient) -> dict[str, int]:
    raw: dict = {}
    for key, path in REQUIRED_SOURCES.items():
        raw[key] = list(client.iter_all_records(path))
    for key, path in OPTIONAL_SOURCES.items():
        try:
            raw[key] = list(client.iter_all_records(path))
        except BioTimeError:
            logger.warning("Could not read %s from BioTime; continuing without it", key, exc_info=True)
            raw[key] = []
    raw["synced_at"] = datetime.now().isoformat(timespec="seconds")
    set_setting(db, SNAPSHOT_KEY, json.dumps(raw))
    summary = {
        "shifts": len(raw["attshifts"]),
        "schedules": len(raw["attschedules"]),
        "holidays": len(raw["holidays"]),
    }
    logger.info("BioTime shift sync complete: %s", summary)
    return summary


def load_shift_data(db: Session) -> Optional[ShiftData]:
    value = get_setting(db, SNAPSHOT_KEY)
    if not value:
        return None
    try:
        return ShiftData.from_raw(json.loads(value))
    except (ValueError, TypeError):
        logger.warning("Stored shift data is unreadable; it will be synced again", exc_info=True)
        return None


def get_shift_data(db: Session, client: BioTimeClient) -> ShiftData:
    """The stored shift data, syncing from BioTime first if there's none yet."""
    data = load_shift_data(db)
    if data is None:
        sync_shifts(db, client)
        data = load_shift_data(db)
    return data


def fallback_choice(db: Session, data: ShiftData) -> str:
    choice = get_setting(db, FALLBACK_KEY)
    if choice in (FALLBACK_NONE, FALLBACK_APP_DEFAULT) or (choice and data.fallback_shift(choice)):
        return choice
    return data.default_fallback()


def set_fallback_choice(db: Session, choice: str) -> None:
    set_setting(db, FALLBACK_KEY, choice)


def clear_shift_data(db: Session) -> None:
    """Forget synced shifts (e.g. when switching to another BioTime server)."""
    delete_settings(db, SNAPSHOT_KEY, FALLBACK_KEY)


def describe_fallback(data: ShiftData, choice: str) -> str:
    if choice == FALLBACK_NONE:
        return "not scheduled (no expected hours, absences or late arrivals)"
    shift = data.fallback_shift(choice)
    return f"the {shift.name}" if shift and shift.id == -1 else f"the {shift.name} shift" if shift else "not scheduled"
