# BioTime Web App

A small web app that works alongside **ZKBio Time (BioTime) v9** and runs on your own Windows PC:

- **Leave requests**: see leave requests synced from BioTime and submit new ones (approvals stay in BioTime).
- **Manual punches**: add a check-in/check-out for an employee who forgot to punch (saved in BioTime as a Manual Log, optionally approved right away).
- **Attendance reports**: **Worked Hours**, **Absence** and **Late Arrivals**, calculated from the punches in BioTime, for all employees or one employee at a time.
- **Client API**: worked hours, absence and late arrivals (and leave requests) as JSON for an ERP or payroll system, protected by API keys you create on the **API Integrations** page.

Current version: **1.1.1** (see [CHANGELOG.md](CHANGELOG.md)).

The app works with **your own BioTime server**: nothing is pre-configured. Each installation asks for its BioTime address and login the first time it opens, and only talks to that server.

---

## What you need

- A **Windows 10 or 11** PC to run the app.
- Your **ZKBio Time (BioTime) server**, version 9 (tested on 9.0), installed and running, either on the same PC or on another computer the app's PC can reach on the network.
- The **address of your BioTime server**: the address you type in the browser to open BioTime, including the port, for example `http://<server-ip>:<port>`.
- A **BioTime user account** the app can log in with. An administrator account works; a restricted account needs access to employees, transactions, leaves and manual logs.
- An **internet connection for the first start**, to download Python and the app's packages.

You don't have to install Python yourself. The start script installs it if it's missing.

---

## Installation

### Step 1: Download the app

**Option A: download a ZIP (no tools needed)**

1. Open this project's GitHub page, **https://github.com/Harmonybod/biotime-webapp**. This is only where the app is downloaded from; it doesn't connect to anyone else's BioTime.
2. Click the green **Code** button, then **Download ZIP**.
3. Open your **Downloads** folder, right-click `biotime-webapp-master.zip` and choose **Extract All…**.
4. Pick a permanent location, for example `C:\Users\<you>\Documents\biotime-webapp`, and click **Extract**.

   Don't run the app from inside the ZIP, and don't leave it in a temporary folder.

**Option B: with Git**

```bat
git clone https://github.com/Harmonybod/biotime-webapp.git
```

### Step 2: Start the app

1. Open the extracted folder. Windows may put it inside a second folder with the same name; open the one that contains `start-server.bat` and the `app` folder.
2. Double-click **`start-server.bat`**.
3. If Windows shows **"Windows protected your PC"**, click **More info**, then **Run anyway**. Windows shows this for scripts downloaded from the internet.
4. A black window opens. **The first start takes a few minutes**: it installs Python 3.12 if needed, then downloads the app's packages. You'll see progress in the window.
5. When it's ready, your browser opens **http://127.0.0.1:8000** automatically.

**Keep the black window open while you use the app.** Closing it stops the app.

If the script stops with an error, see [Manual installation](#manual-installation-if-start-serverbat-fails) or [Troubleshooting](#troubleshooting).

### Step 3: Connect to your BioTime

On the first start, the app opens the **BioTime Connection** page:

| Field | What to enter |
|---|---|
| **BioTime address** | Your BioTime server's address, exactly as in the browser's address bar when you open BioTime, for example `http://<server-ip>:<port>`. If BioTime runs on the same PC as the app, `http://localhost:<port>` also works. |
| **Username / Password** | Your BioTime user account. |

Not sure of the address? Open BioTime in your browser and copy everything before the first `/` after the port (for example from `http://<server-ip>:<port>/base/dashboard/`, copy `http://<server-ip>:<port>`).

Click **Connect**. The app tests the login and tells you what's wrong if it can't connect. Once connected:

1. Go to **Leave Requests** and click **Sync from BioTime** to load existing leave requests.
2. Open **Worked Hours**, **Absence** or **Late Arrivals**, pick an employee and a date range.

To change the BioTime connection later, click **BioTime Connection** in the top-right corner.

### Step 4: Match the app to your BioTime

A few settings can't be read from BioTime automatically. Check them once:

| What | Why | How |
|---|---|---|
| **Work schedule** | Worked hours, absence and late arrivals are calculated against it. | In BioTime, look up your shift under **Attendance → Timetable** (start, end, break) and **Shift** (which weekdays). Copy them into `.env` as `SHIFT_START`, `SHIFT_END`, `SHIFT_BREAK_MINUTES` and `SHIFT_WORK_DAYS` (see [Settings](#settings-env)), then restart the app. |
| **Leave types** | The New Leave Request form needs your BioTime's leave types. | Click **Sync from BioTime** on the Leave Requests page: types used in existing leave requests are added automatically. For types never used yet, add one leave of that type in BioTime and sync again, or list them in `.env` as `LEAVE_TYPES=id:Name, id:Name`. |
| **Approved leave** | Approved leave isn't counted as absence. | Leaves sync every 15 minutes automatically; click **Sync from BioTime** to update straight away. |
| **Punches** | Reports only see punches that reached BioTime. | Make sure your devices upload to BioTime (**Attendance → Transactions** should show recent punches). |

### Next time

Double-click `start-server.bat` again. It skips the setup and starts in a few seconds.

---

## Manual installation (if `start-server.bat` fails)

Use this if the script can't install Python or a package, for example because of a proxy, a firewall, or no `winget`.

**1. Install Python 3.12**

1. Download the **Windows installer (64-bit)** from https://www.python.org/downloads/release/python-31210/.
2. Run it. **Tick "Add python.exe to PATH"** at the bottom of the first screen, then click **Install Now**.

Use Python 3.12; 3.10 and 3.11 also work. The app is tested on 3.12, and newer versions (3.13+) may fail to install some of its packages.

**2. Open a terminal in the app folder**

Open the app folder in File Explorer, click the address bar, type `cmd` and press **Enter**. A Command Prompt opens in that folder.

**3. Run these commands one at a time**

```bat
:: Needed on PCs with ZKBioTime installed (its installer breaks other Pythons); harmless otherwise
set PYTHONHOME=
set PYTHONPATH=

:: Create the app's Python environment (use "python" instead of "py -3.12" if py isn't found)
py -3.12 -m venv .venv
.venv\Scripts\activate

:: Install the packages
python -m pip install --upgrade pip
pip install -r requirements.txt

:: Create the settings file
copy .env.example .env

:: Start the app
python -m uvicorn app.main:app --port 8000
```

Then open **http://127.0.0.1:8000** in your browser and continue with [Step 3](#step-3-connect-to-your-biotime).

If one package fails to install, run `pip install -r requirements.txt` again; downloads sometimes fail on a slow connection. If it keeps failing, install that package on its own (for example `pip install uvicorn[standard]==0.30.6`, using the version from `requirements.txt`) and read the error message it prints.

**To start it again later** (manual install), open `cmd` in the app folder and run:

```bat
set PYTHONHOME=
.venv\Scripts\activate
python -m uvicorn app.main:app --port 8000
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Windows protected your PC" | Click **More info**, then **Run anyway**. Or right-click `start-server.bat` → **Properties** → tick **Unblock** → **OK**. |
| "Python was installed but this window can't see it yet" | Close the window and double-click `start-server.bat` again. |
| Python or packages fail to download | Check the internet connection (and proxy/firewall), then run `start-server.bat` again. If it still fails, use the [manual installation](#manual-installation-if-start-serverbat-fails). |
| `SRE module mismatch` or `No module named 'encodings'` | ZKBioTime's `PYTHONHOME` setting is interfering. `start-server.bat` handles this. When running commands manually, run `set PYTHONHOME=` first. |
| `error while attempting to bind on address ... 8000` | The app is already running in another window, or another program uses port 8000. Close the other window, or change `--port 8000` to `--port 8001` in `start-server.bat` and open http://127.0.0.1:8001. |
| "Couldn't reach BioTime at …" | Check that the address opens BioTime in your browser, including the port. If BioTime is on another PC, that PC's firewall must allow the port. |
| "BioTime rejected that username or password" | Use the same login you use on the BioTime website. |
| New Leave Request has no leave types | See **Leave types** in [Step 4](#step-4-match-the-app-to-your-biotime). |
| Hours, absences or late arrivals look wrong | Check the work schedule in `.env` matches your BioTime shift ([Step 4](#step-4-match-the-app-to-your-biotime)) and restart the app. |
| Reports show no hours | Check the date range, and that BioTime has punches for it (in BioTime: **Attendance → Transactions**). |
| Start completely fresh | Close the app, delete `biotime.db` in the app folder (cached data and saved connection) and the folder `%LOCALAPPDATA%\biotime-webapp`, then run `start-server.bat` again. |

---

## How the attendance reports are calculated

The reports are calculated from BioTime's punch records (**Attendance → Transactions**), against the work schedule set in `.env` (default **08:00–17:00, Monday–Friday, 60-minute break = 8 hours a day**). Set it to match the shift in BioTime (**Attendance → Shift** and **Timetable**), see [Settings](#settings-env).

- **Worked hours**: each day's punches are paired in time order (1st–2nd, 3rd–4th, …) and the durations are added up. A day with an odd number of punches is flagged **Missing punch**.
- **Absence**: a scheduled workday with no punches and no approved leave. Absent hours = that day's expected hours. Approved leave comes from the last **Sync from BioTime**.
- **Late arrivals**: the first punch of a workday after the shift start (plus an optional grace period).

- **Only completed days count.** Today is included once it's over: until then, employees may not have arrived or checked out yet, so they'd look absent or short of hours. Late arrivals that already happened today are shown separately at the bottom of the Late Arrivals page. The API's `calculated_through` field gives the last day counted.

The schedule is the same for every employee, and shifts that cross midnight aren't supported.

---

## Settings (`.env`)

`start-server.bat` creates `.env` from `.env.example`. Edit it in Notepad and restart the app to apply changes.

| Setting | Default | Meaning |
|---|---|---|
| `SHIFT_START` / `SHIFT_END` | `08:00` / `17:00` | Scheduled working hours. |
| `SHIFT_BREAK_MINUTES` | `60` | Unpaid break, subtracted from the expected hours. |
| `SHIFT_WORK_DAYS` | `0,1,2,3,4` | Workdays: 0 = Monday … 6 = Sunday. |
| `LATE_GRACE_MINUTES` | `0` | Minutes after shift start before an arrival counts as late. |
| `API_NETWORK_ACCESS` | `false` | `true` lets systems on other computers call the client API (see below). |
| `LEAVE_TYPES` | blank | Extra leave types as `id:Name, id:Name` (BioTime pay code ids). Types in synced leaves are found automatically. |
| `SYNC_ENABLED` / `SYNC_INTERVAL_MINUTES` | `true` / `15` | Automatic leave sync from BioTime. |
| `DATABASE_URL` | `sqlite:///./biotime.db` | Local database file. A `postgresql+pg8000://…` URL also works. |
| `BIOTIME_BASE_URL` / `_USERNAME` / `_PASSWORD` | blank | Optional. Normally entered on the BioTime Connection page instead. |

---

## Connecting an ERP or payroll system (client API)

Everything is set up on the **API Integrations** page in the app, which also has the full API reference with examples.

1. **Choose how the system connects.** A system running on the same PC works straight away (`http://127.0.0.1:8000`). For a system on another computer, set `API_NETWORK_ACCESS=true` in `.env`, restart `start-server.bat`, and allow Python on **Private networks** if Windows Firewall asks. The page then shows this PC's network address to use as the base URL.
2. **Create an API key** for the system on the page. Copy it straight away; it's only shown once. Create one key per system so each can be revoked separately.
3. **Call the API** with the key in the `X-API-Key` header, for example:

   ```
   GET http://<base-url>/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-31&metrics=worked,late
   X-API-Key: btk_...
   ```

   `metrics` picks what's returned: `worked`, `absence`, `late`, any combination, or single field names.

---

## Security notes

- By default the app only listens on **this PC**. With `API_NETWORK_ACCESS=true`, other computers can reach **only** the client API (`/api/reports/attendance`, `/api/leaves`), and only with a valid API key. All pages, including manual punches and settings, stay available on this PC only.
- API keys are stored as hashes; revoke a key on the API Integrations page to cut off that system.
- The BioTime password is saved in `biotime.db` in the app folder. Don't share that file, or your `.env`.

---

## For developers

| Layer | What we use |
|---|---|
| Backend | Python 3.12, [FastAPI](https://fastapi.tiangolo.com/) |
| Frontend | Server-rendered Jinja2 templates (`app/templates/`), plain CSS (`app/static/style.css`), no JS framework |
| Database | SQLite (`biotime.db`) via SQLAlchemy; PostgreSQL also works (`pg8000`) |
| Migrations | Alembic (`alembic/`), applied automatically on startup |
| App server | Uvicorn, started by `start-server.bat` (venv in `%LOCALAPPDATA%\biotime-webapp\venv`) |
| Background jobs | APScheduler, in-process (periodic leave sync) |
| Upstream | ZKBio Time v9 REST API via `httpx` (`app/biotime_client.py`) |

Run with auto-reload while developing:

```bat
uvicorn app.main:app --reload --port 8000
```

### Layout

- `app/main.py`: app wiring, startup (migrations, BioTime connection), redirect to `/setup` until connected, background sync job.
- `app/biotime_client.py`: BioTime API client (auth, leaves, employees, transactions). `BIOTIME_AUTH_SCHEME` switches between `Token` and `JWT`.
- `app/connection.py` and `app/routers/setup.py`: the BioTime Connection page; tests, saves and loads the connection.
- `app/attendance.py`: worked-hours / absence / late calculations (pure functions).
- `app/routers/punches.py`: the Manual Punch page (BioTime `/att/api/manuallogs/`).
- `app/routers/reports.py`: report pages and the attendance JSON API.
- `app/routers/leaves.py`, `app/sync.py`: leave pages, JSON API and the BioTime → local cache sync.
- `app/routers/employees.py`: live employee search.
- `app/routers/integrations.py`: the API Integrations page (connection details, API keys, API reference).
- `app/api_keys.py`: API key creation/checking and the rule that other computers may only reach the client API.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/setup` | BioTime Connection page |
| GET | `/leaves` | Leave requests (filter by department / emp_code / status) |
| GET/POST | `/leaves/new` | New leave request form / submit to BioTime |
| POST | `/sync` | Sync leaves from BioTime |
| GET/POST | `/punches` | Manual punches: list / add (check-in and/or check-out, optional auto-approve) |
| POST | `/punches/{id}/approve`, `/punches/{id}/delete` | Approve or delete a manual punch in BioTime |
| GET | `/reports/worked-hours`, `/reports/absence`, `/reports/late-arrivals` | Attendance report pages (`?emp_code=&start_date=&end_date=`) |
| GET/POST | `/integrations`, `/integrations/keys`, `/integrations/keys/{id}/revoke` | API Integrations page: connection details, API keys, API reference |
| GET | `/api/reports/attendance` | **Client API, needs `X-API-Key`.** Attendance report JSON. Required: `start_date`, `end_date`. Optional: `metrics` (any of `worked`, `absence`, `late`, or field names; default all), `emp_code`, `department`, `include_days`, `page`, `page_size`. Full docs on the `/integrations` page. |
| GET | `/api/leaves` | **Client API, needs `X-API-Key`.** Leave requests JSON |
| POST | `/api/leaves` | Create a leave request (this PC only) |
| POST | `/api/sync` | Sync trigger (this PC only) |
| GET | `/api/employees` | Employee search for the pages (this PC only) |
