# BioTime Leave Integration

Internal FastAPI app that syncs leave requests with ZKBio Time v9.0.6 and lets
staff submit new leave requests (approvals stay inside BioTime's own UI).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your BioTime credentials and
Postgres connection string.

Create the database, then run migrations:

```bash
alembic upgrade head
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/leaves.

## Layout

- `app/biotime_client.py` — BioTime API client (auth, leaves, employees). Fully
  decoupled from the web/DB layer; swap `BIOTIME_AUTH_SCHEME` between
  `Token`/`JWT` via `.env` without touching callers.
- `app/sync.py` — pulls all leaves from BioTime and upserts them into
  `leave_requests`, matched on `biotime_id`.
- `app/routers/leaves.py` — HTML pages (`/leaves`, `/leaves/new`) plus a JSON
  API (`/api/leaves`, `/api/sync`).
- `app/routers/employees.py` — live employee lookup for the request form
  (`/api/employees?search=`).
- `app/main.py` — FastAPI app wiring, BioTime error → HTTP status mapping, and
  the APScheduler background sync job (`SYNC_INTERVAL_MINUTES`, disable with
  `SYNC_ENABLED=false`).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/leaves` | List cached leave requests (filter by department/emp_code/status) |
| GET | `/leaves/new` | New leave request form |
| POST | `/leaves/new` | Submit a new leave request to BioTime |
| POST | `/sync` | Trigger a manual sync from BioTime |
| GET | `/api/leaves` | JSON list of cached leave requests |
| POST | `/api/leaves` | JSON create (mirrors the form) |
| POST | `/api/sync` | JSON sync trigger |
| GET | `/api/employees` | Live employee search for the picker |
