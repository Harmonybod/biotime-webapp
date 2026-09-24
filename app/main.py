from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.biotime_client import BioTimeClientError, BioTimeServerError, get_biotime_client
from app.config import settings
from app.database import SessionLocal
from app.routers import employees, leaves
from app.sync import sync_leaves

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BioTime Leave Integration")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(leaves.router)
app.include_router(employees.router)


@app.exception_handler(BioTimeClientError)
def biotime_client_error_handler(request: Request, exc: BioTimeClientError):
    return JSONResponse(status_code=exc.status_code or 400, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(BioTimeServerError)
def biotime_server_error_handler(request: Request, exc: BioTimeServerError):
    return JSONResponse(status_code=502, content={"detail": "BioTime server error, try again"})


scheduler: BackgroundScheduler | None = None


def _scheduled_sync_job() -> None:
    db = SessionLocal()
    try:
        sync_leaves(db, get_biotime_client())
    except Exception:
        logger.exception("Scheduled BioTime sync failed")
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    global scheduler
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
    get_biotime_client().close()
