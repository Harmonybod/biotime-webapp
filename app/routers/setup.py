from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.biotime_client import get_biotime_client, is_biotime_configured
from app.connection import normalize_base_url, save_connection, saved_connection, test_connection
from app.database import get_db

router = APIRouter(tags=["setup"])
templates = Jinja2Templates(directory="app/templates")


def _current(db: Session) -> dict:
    row = saved_connection(db)
    if row:
        return {"base_url": row.base_url, "username": row.username}
    if is_biotime_configured():
        client = get_biotime_client()
        return {"base_url": client.base_url, "username": client.username}
    return {"base_url": "", "username": ""}


@router.get("/setup")
def setup_page(request: Request, message: Optional[str] = None, db: Session = Depends(get_db)):
    current = _current(db)
    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "form": current,
            "connected": is_biotime_configured(),
            "has_saved_password": bool(saved_connection(db)),
            "message": message,
            "error": None,
        },
    )


@router.post("/setup")
def save_setup(
    request: Request,
    base_url: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    base_url = normalize_base_url(base_url)
    username = username.strip()

    row = saved_connection(db)
    # Blank password on an existing connection means "keep the current one".
    if not password and row and row.username == username:
        password = row.password

    error = None
    if not password:
        error = "Enter the BioTime password."
    else:
        error = test_connection(base_url, username, password)

    if error:
        return templates.TemplateResponse(
            "setup.html",
            {
                "request": request,
                "form": {"base_url": base_url, "username": username},
                "connected": is_biotime_configured(),
                "has_saved_password": bool(row),
                "message": None,
                "error": error,
            },
            status_code=400,
        )

    save_connection(db, base_url, username, password)
    return RedirectResponse(url=f"/leaves?message=Connected to BioTime at {base_url}.", status_code=303)
