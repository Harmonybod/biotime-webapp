# Changelog

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
