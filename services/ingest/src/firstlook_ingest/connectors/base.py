"""Connector interface: auth -> backfill -> incremental sync (-> webhooks).

A connector turns a provider account into RawItems. It never parses or
resolves anything: raw bytes go to object storage untouched (the audit trail),
and the resolver works from there.

Normalised JSON shapes for non-email kinds:

MeetingEvent = {
    "id", "series_id", "title", "description", "start", "end" (ISO 8601),
    "status" ("confirmed" | "cancelled"), "location", "conference_id",
    "organizer": {"email", "name"},
    "attendees": [{"email", "name", "response"}]
}
Transcript = {
    "id", "provider", "title", "start", "duration_s", "meeting_external_id",
    "participants": [{"name", "email"}],
    "segments": [{"speaker", "start", "end", "text"}]
}
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


class AuthError(RuntimeError):
    """Credentials are invalid or revoked. Not retryable: the user must reconnect."""


class RateLimited(RuntimeError):
    """Provider throttled us. Retryable after retry_after seconds."""

    def __init__(self, message: str, retry_after: float = 30.0):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RawItem:
    kind: str  # email, meeting, transcript
    external_id: str
    data: bytes
    content_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncPage:
    items: list[RawItem]
    cursor: dict[str, Any]  # persisted after the page is stored
    done: bool  # no more pages right now
    skipped: int = 0


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float
    scope: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at - 60

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OAuthTokens:
        return cls(**d)


class Connector(Protocol):
    provider: str
    scopes: list[str]

    def authorization_url(self, state: str, redirect_uri: str) -> str: ...

    def exchange_code(self, code: str, redirect_uri: str) -> tuple[OAuthTokens, str]:
        """Returns (tokens, account email)."""
        ...

    def refresh(self, tokens: OAuthTokens) -> OAuthTokens: ...

    def sync(self, tokens: OAuthTokens, settings: dict[str, Any], cursor: dict[str, Any]) -> SyncPage:
        """Fetch the next page of new items since cursor. An empty cursor means backfill."""
        ...


def check_response(r: httpx.Response, provider: str) -> httpx.Response:
    if r.status_code == 401:
        raise AuthError(f"{provider}: credentials rejected")
    if r.status_code == 429 or (r.status_code == 403 and "rate" in r.text.lower()):
        retry = float(r.headers.get("Retry-After", "30") or 30)
        raise RateLimited(f"{provider}: rate limited", retry)
    if r.status_code >= 500:
        raise RateLimited(f"{provider}: server error {r.status_code}", 15)
    r.raise_for_status()
    return r


def get_connector(provider: str) -> Connector:
    from .google import GoogleConnector
    from .meet import GoogleMeetConnector
    from .microsoft import MicrosoftConnector
    from .zoom import ZoomConnector

    connectors: dict[str, type] = {
        "google": GoogleConnector,
        "microsoft": MicrosoftConnector,
        "zoom": ZoomConnector,
        "google_meet": GoogleMeetConnector,
    }
    if provider not in connectors:
        raise KeyError(f"unknown connector {provider!r}")
    return connectors[provider]()
