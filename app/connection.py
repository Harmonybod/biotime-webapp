"""Which BioTime server this install talks to.

Entered once on the /setup page and saved in the local database, so anyone
can run their own copy of the app against their own BioTime without editing
config files. Falls back to BIOTIME_* values in .env if nothing is saved yet.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.biotime_client import (
    BioTimeClient,
    BioTimeClientError,
    BioTimeServerError,
    configure_biotime_client,
)
from app.config import settings
from app.models import BioTimeConnection, LeaveRequest

logger = logging.getLogger(__name__)


def normalize_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if url and "://" not in url:
        url = f"http://{url}"
    return url


def saved_connection(db: Session) -> Optional[BioTimeConnection]:
    return db.query(BioTimeConnection).first()


def test_connection(base_url: str, username: str, password: str) -> Optional[str]:
    """Try to log in to BioTime. Returns None on success, else a readable error."""
    client = BioTimeClient(base_url=base_url, username=username, password=password)
    try:
        client.get_token(force=True)
        return None
    except BioTimeClientError as exc:
        if exc.status_code in (400, 401):
            return "BioTime rejected that username or password."
        return f"{base_url} answered, but it doesn't look like a BioTime server (HTTP {exc.status_code})."
    except BioTimeServerError:
        return "BioTime is reachable but returned a server error. Try again in a moment."
    except ValueError:
        return f"{base_url} answered, but it doesn't look like a BioTime server."
    except httpx.HTTPError:
        return (
            f"Couldn't reach BioTime at {base_url}. Check the address and port "
            "(the same one you open BioTime with in your browser) and that BioTime is running."
        )
    finally:
        client.close()


def save_connection(db: Session, base_url: str, username: str, password: str) -> None:
    row = saved_connection(db)
    if row and row.base_url != base_url:
        # Cached leaves belong to the old server; their ids would clash with the new one's.
        db.query(LeaveRequest).delete()
    if row is None:
        row = BioTimeConnection()
        db.add(row)
    row.base_url = base_url
    row.username = username
    row.password = password
    db.commit()
    configure_biotime_client(base_url, username, password)


def load_connection(db: Session) -> None:
    """On startup: use the saved connection, else .env values, else wait for /setup."""
    row = saved_connection(db)
    if row:
        configure_biotime_client(row.base_url, row.username, row.password)
        logger.info("Using BioTime at %s", row.base_url)
    elif settings.biotime_base_url and settings.biotime_username:
        configure_biotime_client(
            normalize_base_url(settings.biotime_base_url),
            settings.biotime_username,
            settings.biotime_password,
        )
        logger.info("Using BioTime at %s (from .env)", settings.biotime_base_url)
    else:
        logger.info("No BioTime connection yet; open /setup to add one")
