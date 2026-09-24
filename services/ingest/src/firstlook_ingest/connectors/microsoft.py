"""Microsoft 365: Outlook mail + calendar via Microsoft Graph (read-only).

Uses Graph delta queries: the first pass over each folder is the backfill,
and the final @odata.deltaLink is stored as the incremental cursor. Raw MIME
comes from /messages/{id}/$value so the same resolver handles Gmail and Outlook.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from firstlook_core.config import get_settings

from .base import AuthError, OAuthTokens, RawItem, SyncPage, check_response

GRAPH = "https://graph.microsoft.com/v1.0"
BACKFILL_DAYS = 365
PAGE_SIZE = 50


def normalise_event(e: dict[str, Any]) -> dict[str, Any]:
    def iso(dt: dict[str, Any] | None) -> str | None:
        if not dt or not dt.get("dateTime"):
            return None
        value = dt["dateTime"]
        # Graph returns naive times in the requested zone (UTC by default).
        return value if "+" in value or value.endswith("Z") else f"{value.split('.')[0]}+00:00"

    organizer = (e.get("organizer") or {}).get("emailAddress") or {}
    return {
        "id": f"outlook-cal:{e['id']}",
        "series_id": e.get("seriesMasterId"),
        "title": e.get("subject", ""),
        "description": (e.get("bodyPreview") or ""),
        "start": iso(e.get("start")),
        "end": iso(e.get("end")),
        "status": "cancelled" if e.get("isCancelled") else "confirmed",
        "location": (e.get("location") or {}).get("displayName"),
        "conference_id": (e.get("onlineMeeting") or {}).get("joinUrl"),
        "organizer": {"email": organizer.get("address"), "name": organizer.get("name")},
        "attendees": [
            {
                "email": (a.get("emailAddress") or {}).get("address"),
                "name": (a.get("emailAddress") or {}).get("name"),
                "response": (a.get("status") or {}).get("response"),
            }
            for a in e.get("attendees", [])
            if a.get("type") != "resource"
        ],
    }


class MicrosoftConnector:
    provider = "microsoft"
    scopes = ["offline_access", "openid", "email", "User.Read", "Mail.Read", "Calendars.Read"]

    def __init__(self, http: httpx.Client | None = None):
        s = get_settings()
        self.client_id, self.client_secret, self.tenant = (
            s.microsoft_client_id,
            s.microsoft_client_secret,
            s.microsoft_tenant,
        )
        self.http = http or httpx.Client(timeout=60)

    @property
    def _base(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0"

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        if not self.client_id:
            raise AuthError("MICROSOFT_CLIENT_ID is not configured")
        return f"{self._base}/authorize?" + urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": " ".join(self.scopes),
                "state": state,
            }
        )

    def _token(self, data: dict[str, str]) -> OAuthTokens:
        r = self.http.post(
            f"{self._base}/token",
            data={
                **data,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": " ".join(self.scopes),
            },
        )
        if r.status_code in (400, 401):
            raise AuthError(f"microsoft token endpoint: {r.text[:300]}")
        body = check_response(r, "microsoft").json()
        return OAuthTokens(
            body["access_token"],
            body.get("refresh_token", data.get("refresh_token")),
            time.time() + body.get("expires_in", 3600),
            body.get("scope", ""),
        )

    def exchange_code(self, code: str, redirect_uri: str) -> tuple[OAuthTokens, str]:
        tokens = self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri})
        me = check_response(self.http.get(f"{GRAPH}/me", headers=self._h(tokens)), "microsoft").json()
        return tokens, (me.get("mail") or me["userPrincipalName"]).lower()

    def refresh(self, tokens: OAuthTokens) -> OAuthTokens:
        if not tokens.refresh_token:
            raise AuthError("no refresh token; reconnect the account")
        return self._token({"grant_type": "refresh_token", "refresh_token": tokens.refresh_token})

    def list_folders(self, tokens: OAuthTokens) -> list[dict[str, str]]:
        r = check_response(
            self.http.get(f"{GRAPH}/me/mailFolders", headers=self._h(tokens), params={"$top": 100}),
            "microsoft",
        )
        return [{"id": f["id"], "name": f["displayName"]} for f in r.json().get("value", [])]

    @staticmethod
    def _h(tokens: OAuthTokens) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}", "Prefer": 'outlook.timezone="UTC"'}

    def _fetch_mime(self, tokens: OAuthTokens, message_id: str) -> bytes:
        r = self.http.get(f"{GRAPH}/me/messages/{message_id}/$value", headers=self._h(tokens))
        return check_response(r, "microsoft").content

    def sync(self, tokens: OAuthTokens, settings: dict[str, Any], cursor: dict[str, Any]) -> SyncPage:
        cursor = json.loads(json.dumps(cursor))
        folders = settings.get("folders") or ["inbox", "sentitems"]
        personal = (
            {c.lower() for c in settings.get("personal_categories", ["Personal"])}
            if settings.get("exclude_personal", True)
            else set()
        )
        mail = cursor.setdefault("mail", {})
        since = (datetime.now(UTC) - timedelta(days=BACKFILL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Mail: one page from the first folder that still has pages to read.
        for folder in folders:
            state = mail.setdefault(folder, {})
            url = state.get("next") or state.get("delta")
            if url is None:
                url = f"{GRAPH}/me/mailFolders/{folder}/messages/delta?" + urllib.parse.urlencode(
                    {"$select": "id,categories,receivedDateTime", "$filter": f"receivedDateTime ge {since}"}
                )
            elif state.get("delta") and not state.get("next") and state.get("caught_up_at"):
                # Already caught up on this folder in this round; move on.
                continue
            r = self.http.get(url, headers={**self._h(tokens), "Prefer": f"odata.maxpagesize={PAGE_SIZE}"})
            if r.status_code == 410:
                mail[folder] = {}
                return SyncPage([], cursor, done=False)
            body = check_response(r, "microsoft").json()
            items, skipped = [], 0
            for m in body.get("value", []):
                if "@removed" in m:
                    continue
                if personal & {c.lower() for c in m.get("categories", [])}:
                    skipped += 1
                    continue
                items.append(
                    RawItem(
                        "email",
                        f"outlook:{m['id']}",
                        self._fetch_mime(tokens, m["id"]),
                        "message/rfc822",
                        {"folder": folder},
                    )
                )
            if body.get("@odata.nextLink"):
                state["next"] = body["@odata.nextLink"]
                state.pop("caught_up_at", None)
            else:
                state.pop("next", None)
                state["delta"] = body.get("@odata.deltaLink", state.get("delta"))
                state["caught_up_at"] = time.time()
            return SyncPage(items, cursor, done=False, skipped=skipped)

        # Calendar
        cal = cursor.setdefault("calendar", {})
        url = cal.get("next") or cal.get("delta")
        if url is None:
            end = (datetime.now(UTC) + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = f"{GRAPH}/me/calendarView/delta?" + urllib.parse.urlencode(
                {"startDateTime": since, "endDateTime": end}
            )
        r = self.http.get(
            url, headers={**self._h(tokens), "Prefer": 'odata.maxpagesize=100, outlook.timezone="UTC"'}
        )
        if r.status_code == 410:
            cursor["calendar"] = {}
            return SyncPage([], cursor, done=False)
        body = check_response(r, "microsoft").json()
        items = [
            RawItem(
                "meeting",
                f"outlook-cal:{e['id']}",
                json.dumps(normalise_event(e)).encode(),
                "application/json",
            )
            for e in body.get("value", [])
            if "@removed" not in e and e.get("start")
        ]
        if body.get("@odata.nextLink"):
            cal["next"] = body["@odata.nextLink"]
            return SyncPage(items, cursor, done=False)
        cal.pop("next", None)
        cal["delta"] = body.get("@odata.deltaLink", cal.get("delta"))
        # Round complete: clear per-round markers so the next sync starts over.
        for state in mail.values():
            state.pop("caught_up_at", None)
        return SyncPage(items, cursor, done=True)
