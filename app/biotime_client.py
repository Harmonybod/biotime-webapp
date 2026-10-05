"""HTTP client for the ZKBio Time v9.0.6 API.

Deliberately decoupled from the web/API layer and from the database: it only
knows how to talk to BioTime (authenticate, list/create leaves, list
employees). Auth scheme (Token vs JWT) is swappable via config without
touching callers.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class BioTimeError(Exception):
    """Base error for a failed BioTime API call."""

    def __init__(self, message: str, status_code: Optional[int] = None, code: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class BioTimeClientError(BioTimeError):
    """4xx: bad request, bad credentials, validation error, etc."""


class BioTimeServerError(BioTimeError):
    """5xx: BioTime itself is failing."""


class BioTimeNotConfigured(BioTimeClientError):
    """No BioTime connection has been set up yet (see /setup)."""


class BioTimeClient:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth_scheme: str | None = None,
    ):
        self.base_url = (base_url or settings.biotime_base_url).rstrip("/")
        self.username = username or settings.biotime_username
        self.password = password or settings.biotime_password
        self.auth_scheme = auth_scheme or settings.biotime_auth_scheme

        self._token: Optional[str] = None
        self._lock = threading.Lock()
        self._http = httpx.Client(base_url=self.base_url, timeout=30.0)

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    def get_token(self, force: bool = False) -> str:
        """Fetch and cache the auth token. Thread-safe; re-fetches when forced."""
        with self._lock:
            if self._token and not force:
                return self._token

            resp = self._http.post(
                "/jwt-api-token-auth/",
                json={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/json"},
            )
            self._raise_for_status(resp)
            data = resp.json()
            token = data.get("token")
            if not token:
                raise BioTimeClientError(
                    "BioTime auth response did not contain a token", resp.status_code, data.get("code")
                )
            self._token = token
            return token

    def _auth_header(self) -> dict[str, str]:
        token = self.get_token()
        return {"Authorization": f"{self.auth_scheme} {token}"}

    # ------------------------------------------------------------------ #
    # Request helper with one automatic re-auth-and-retry on 401
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("Content-Type", "application/json")
        headers.update(self._auth_header())

        resp = self._http.request(method, path, headers=headers, **kwargs)

        if resp.status_code == 401:
            headers.update({"Authorization": f"{self.auth_scheme} {self.get_token(force=True)}"})
            resp = self._http.request(method, path, headers=headers, **kwargs)

        self._raise_for_status(resp)
        return resp

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return

        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        msg = payload.get("msg") or resp.text or "Unknown error"
        code = payload.get("code")

        if resp.status_code >= 500:
            raise BioTimeServerError("BioTime server error, try again", resp.status_code, code)
        raise BioTimeClientError(msg, resp.status_code, code)

    # ------------------------------------------------------------------ #
    # Leaves
    # ------------------------------------------------------------------ #
    def list_leaves(self, page: int = 1, page_size: int = 50, **filters) -> dict:
        params = {"page": page, "page_size": page_size, **filters}
        resp = self._request("GET", "/att/api/leaves/", params=params)
        return resp.json()

    def iter_all_leaves(self, page_size: int = 50, **filters):
        """Yield every leave record, following BioTime's `next` pagination."""
        page = self.list_leaves(page=1, page_size=page_size, **filters)
        while True:
            for record in page.get("data", []):
                yield record
            next_url = page.get("next")
            if not next_url:
                break
            page = self._get_absolute(next_url)

    def _get_absolute(self, url: str) -> dict:
        """Follow a full `next` URL returned by BioTime (may include host)."""
        resp = self._request("GET", url)
        return resp.json()

    def create_leave(
        self,
        employee: str,
        pay_code: int,
        start_time: str,
        end_time: str,
        apply_reason: str = "",
    ) -> dict:
        body = {
            "employee": employee,
            "pay_code": pay_code,
            "start_time": start_time,
            "end_time": end_time,
            "apply_reason": apply_reason,
        }
        resp = self._request("POST", "/att/api/leaves/", json=body)
        created = resp.json()
        return self._fetch_created_leave(employee, created) or created

    def _fetch_created_leave(self, employee: str, created: dict) -> Optional[dict]:
        """BioTime's create response omits id, names, department and status.

        Re-read the record from the list endpoint so the caller gets the same
        enriched shape a sync would produce; falls back to None if it can't be
        matched, since the leave itself was still created.
        """
        try:
            page = self.list_leaves(page=1, page_size=100, employee=employee)
        except BioTimeError:
            logger.warning("Leave created but the follow-up lookup failed", exc_info=True)
            return None

        matches = [
            record
            for record in page.get("data", [])
            if record.get("start_time") == created.get("start_time")
            and record.get("end_time") == created.get("end_time")
        ]
        if not matches:
            return None
        return max(matches, key=lambda record: record.get("id") or 0)

    # ------------------------------------------------------------------ #
    # Employees
    # ------------------------------------------------------------------ #
    def list_employees(self, page: int = 1, page_size: int = 50, **filters) -> dict:
        params = {"page": page, "page_size": page_size, **filters}
        resp = self._request("GET", "/personnel/api/employees/", params=params)
        return resp.json()

    def iter_all_employees(self, page_size: int = 50, **filters):
        page = self.list_employees(page=1, page_size=page_size, **filters)
        while True:
            for record in page.get("data", []):
                yield record
            next_url = page.get("next")
            if not next_url:
                break
            page = self._get_absolute(next_url)

    # ------------------------------------------------------------------ #
    # Transactions (raw punches)
    # ------------------------------------------------------------------ #
    def list_transactions(self, page: int = 1, page_size: int = 50, **filters) -> dict:
        """Filters: emp_code, start_time / end_time ("YYYY-MM-DD HH:MM:SS")."""
        params = {"page": page, "page_size": page_size, **filters}
        resp = self._request("GET", "/iclock/api/transactions/", params=params)
        return resp.json()

    def iter_all_transactions(self, page_size: int = 200, **filters):
        page = self.list_transactions(page=1, page_size=page_size, **filters)
        while True:
            for record in page.get("data", []):
                yield record
            next_url = page.get("next")
            if not next_url:
                break
            page = self._get_absolute(next_url)

    def close(self) -> None:
        self._http.close()


_client: Optional[BioTimeClient] = None


def configure_biotime_client(base_url: str, username: str, password: str) -> None:
    """Point the app at a BioTime server, replacing any previous connection."""
    global _client
    previous = _client
    _client = BioTimeClient(base_url=base_url, username=username, password=password)
    if previous:
        previous.close()


def is_biotime_configured() -> bool:
    return _client is not None


def get_biotime_client() -> BioTimeClient:
    """Process-wide singleton so the token cache is shared across requests."""
    if _client is None:
        raise BioTimeNotConfigured("BioTime connection is not set up yet. Open /setup.", 503)
    return _client


def close_biotime_client() -> None:
    if _client:
        _client.close()
