from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.biotime_client import (
    BioTimeClientError,
    BioTimeServerError,
    close_biotime_client,
    get_biotime_client,
    is_biotime_configured,
)
from app.config import settings
from app.connection import load_connection
from app.database import SessionLocal
from app.routers import employees, integrations, leaves, reports, setup
from app.sync import sync_leaves

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BioTime Leave Integration")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(leaves.router)
app.include_router(employees.router)
app.include_router(integrations.router)
app.include_router(reports.router)
app.include_router(setup.router)


@app.middleware("http")
async def require_biotime_connection(request: Request, call_next):
    """Until a BioTime connection is set up, send every page to /setup."""
    path = request.url.path
    if not is_biotime_configured() and not path.startswith(("/setup", "/static")):
        if path.startswith("/api/"):
            return JSONResponse(status_code=503, content={"detail": "BioTime connection is not set up yet. Open /setup."})
        return RedirectResponse(url="/setup")
    return await call_next(request)


@app.exception_handler(BioTimeClientError)
def biotime_client_error_handler(request: Request, exc: BioTimeClientError):
    return JSONResponse(status_code=exc.status_code or 400, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(BioTimeServerError)
def biotime_server_error_handler(request: Request, exc: BioTimeServerError):
    return JSONResponse(status_code=502, content={"detail": "BioTime server error, try again"})


scheduler: BackgroundScheduler | None = None


def _scheduled_sync_job() -> None:
    if not is_biotime_configured():
        return
    db = SessionLocal()
    try:
        sync_leaves(db, get_biotime_client())
    except Exception:
        logger.exception("Scheduled BioTime sync failed")
    finally:
        db.close()


def _run_migrations() -> None:
    """Create/upgrade the database tables, so a fresh install needs no manual step."""
    config = Config("alembic.ini")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


@app.on_event("startup")
def startup() -> None:
    global scheduler
    _run_migrations()
    db = SessionLocal()
    try:
        load_connection(db)
    finally:
        db.close()
    if settings.sync_enabled:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            _scheduled_sync_job,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="biotime_leave_sync",
        )
        scheduler.start()
        logger.info("Scheduled BioTime leave sync every %s minutes", settings.sync_interval_minutes)


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler:
        scheduler.shutdown(wait=False)
    close_biotime_client()
