# Changelog

## 1.2.0 — 2026-10-13

- **Shifts come from BioTime**: timetables, shifts, employee schedules, temporary schedules and holidays
  are synced over BioTime's API and used for every calculation (reports and client API), per employee
  and per day. No more copying the schedule into `.env`.
- New **Work Schedule** page showing the synced shifts (day by day), who follows which shift, holidays,
  and what employees without a BioTime schedule follow (one of the shifts, or "not scheduled").
- The API Integrations page shows which work schedule the calculations use; API day details include
  `shift` and `scheduled_start`, and new day statuses (Holiday, Not scheduled, …).
- **Leave requests deleted in BioTime are removed** from the app on the next sync.
- **Delete leave requests from the app** (removes them in BioTime too).

## 1.1.1 — 2026-10-07

- README and setup page are now general: no example addresses that match a specific BioTime server,
  plus a clear explanation of how to find your own BioTime address.
- New "Step 4: Match the app to your BioTime" checklist (work schedule, leave types, approved
  leave, punches).
- Leave types are no longer hard-coded to one server: they're learned from leaves synced from
  BioTime, with an optional `LEAVE_TYPES` setting, and the form explains what to do when none are known.

## 1.1.0 — 2026-10-07

- **Client API ready for clients**: per-system API keys (created, listed and revoked on the API
  Integrations page, sent as `X-API-Key`), and an `API_NETWORK_ACCESS` setting so an ERP on another
  computer can connect. Other computers can only reach the client API; all pages stay on this PC.
- **Pick what the attendance API returns** with `metrics` (`worked`, `absence`, `late`, or single
  fields), plus `department` and `include_days` filters and `next`/`previous` page links.
- **Only completed days are counted**: today is left out of worked hours, absence and late totals
  until it's over. The API returns `calculated_through`; the Late Arrivals page lists today's late
  arrivals so far separately.
- **Manual Punch page**: add check-ins/check-outs to BioTime as Manual Logs, approve or delete them.
- API Integrations page rewritten as client-facing setup and reference documentation.
- Version shown in the page footer.

## 1.0.0

- Leave requests (sync from BioTime, submit new ones), Worked Hours / Absence / Late Arrivals
  reports, BioTime Connection setup page, SQLite database, one-click `start-server.bat`.
