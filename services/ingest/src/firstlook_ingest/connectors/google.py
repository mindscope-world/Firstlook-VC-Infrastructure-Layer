"""Google Workspace: Gmail + Google Calendar (read-only).

During development the OAuth app runs in Google's "testing" mode with the
team's own accounts as test users; restricted-scope verification (CASA) is a
Phase 4 task. See docs/connectors.md.

Sync phases, driven by the cursor:
  1. gmail backfill   messages.list over the selected labels, newest first
  2. calendar backfill events.list, which ends with a nextSyncToken
  3. incremental      gmail history.list from the historyId captured at the
                      start of backfill, then calendar events with syncToken
"""

from __future__ import annotations

import base64
import json
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from firstlook_core.config import get_settings

from .base import AuthError, OAuthTokens, RawItem, SyncPage, check_response

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR = "https://www.googleapis.com/calendar/v3/calendars/primary"

# Gmail's automated tabs are noise for relationship intelligence.
EXCLUDED_LABELS = {
    "SPAM",
    "TRASH",
    "DRAFT",
    "CATEGORY_PROMOTIONS",
    "CATEGORY_SOCIAL",
    "CATEGORY_UPDATES",
    "CATEGORY_FORUMS",
}
BACKFILL_DAYS = 365
MESSAGES_PER_PAGE = 50


def gmail_query(settings: dict[str, Any]) -> str:
    parts = [
        f"newer_than:{BACKFILL_DAYS}d",
        "-in:chats",
        "-category:promotions",
        "-category:social",
        "-category:updates",
        "-category:forums",
    ]
    labels = settings.get("labels") or []
    if labels:
        parts.append("{" + " ".join(f'label:"{label}"' for label in labels) + "}")
    for label in (
        settings.get("personal_labels", ["Personal"]) if settings.get("exclude_personal", True) else []
    ):
        parts.append(f'-label:"{label}"')
    return " ".join(parts)


def normalise_event(e: dict[str, Any]) -> dict[str, Any]:
    start = e.get("start", {})
    end = e.get("end", {})
    return {
        "id": f"gcal:{e['id']}",
        "series_id": e.get("recurringEventId"),
        "title": e.get("summary", ""),
        "description": e.get("description", ""),
        "start": start.get("dateTime") or f"{start.get('date')}T00:00:00+00:00",
        "end": end.get("dateTime") or (f"{end.get('date')}T00:00:00+00:00" if end.get("date") else None),
        "status": e.get("status", "confirmed"),
        "location": e.get("location"),
        "conference_id": (e.get("conferenceData") or {}).get("conferenceId"),
        "organizer": {
            "email": (e.get("organizer") or {}).get("email"),
            "name": (e.get("organizer") or {}).get("displayName"),
        },
        "attendees": [
            {"email": a.get("email"), "name": a.get("displayName"), "response": a.get("responseStatus")}
            for a in e.get("attendees", [])
            if not a.get("resource")
        ],
    }


class GoogleConnector:
    provider = "google"
    scopes = [
        "openid",
        "email",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    def __init__(self, http: httpx.Client | None = None):
        s = get_settings()
        self.client_id, self.client_secret = s.google_client_id, s.google_client_secret
        self.http = http or httpx.Client(timeout=60)

    # -- OAuth -----------------------------------------------------------------

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        if not self.client_id:
            raise AuthError("GOOGLE_CLIENT_ID is not configured")
        return (
            AUTH_URL
            + "?"
            + urllib.parse.urlencode(
                {
                    "client_id": self.client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": " ".join(self.scopes),
                    "access_type": "offline",
                    "prompt": "consent",
                    "include_granted_scopes": "true",
                    "state": state,
                }
            )
        )

    def _token(self, data: dict[str, str]) -> dict[str, Any]:
        r = self.http.post(
            TOKEN_URL, data={**data, "client_id": self.client_id, "client_secret": self.client_secret}
        )
        if r.status_code in (400, 401):
            raise AuthError(f"google token endpoint: {r.text[:300]}")
        return check_response(r, "google").json()

    def exchange_code(self, code: str, redirect_uri: str) -> tuple[OAuthTokens, str]:
        body = self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri})
        tokens = OAuthTokens(
            body["access_token"],
            body.get("refresh_token"),
            time.time() + body.get("expires_in", 3600),
            body.get("scope", ""),
        )
        info = check_response(
            self.http.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens.access_token}"}), "google"
        ).json()
        return tokens, info["email"]

    def refresh(self, tokens: OAuthTokens) -> OAuthTokens:
        if not tokens.refresh_token:
            raise AuthError("no refresh token; reconnect the account")
        body = self._token({"grant_type": "refresh_token", "refresh_token": tokens.refresh_token})
        return OAuthTokens(
            body["access_token"],
            tokens.refresh_token,
            time.time() + body.get("expires_in", 3600),
            body.get("scope", tokens.scope),
        )

    def list_labels(self, tokens: OAuthTokens) -> list[dict[str, str]]:
        r = check_response(self.http.get(f"{GMAIL}/labels", headers=self._h(tokens)), "google")
        return [
            {"id": x["id"], "name": x["name"], "type": x.get("type", "")} for x in r.json().get("labels", [])
        ]

    # -- sync ------------------------------------------------------------------

    @staticmethod
    def _h(tokens: OAuthTokens) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}"}

    def _get(self, tokens: OAuthTokens, url: str, **params: Any) -> httpx.Response:
        return check_response(self.http.get(url, headers=self._h(tokens), params=params), "google")

    def _fetch_message(
        self, tokens: OAuthTokens, message_id: str, settings: dict[str, Any]
    ) -> RawItem | None:
        msg = self._get(tokens, f"{GMAIL}/messages/{message_id}", format="raw").json()
        labels = set(msg.get("labelIds", []))
        if labels & EXCLUDED_LABELS:
            return None
        excluded_ids = set(settings.get("_personal_label_ids", []))
        if settings.get("exclude_personal", True) and labels & excluded_ids:
            return None
        raw = base64.urlsafe_b64decode(msg["raw"] + "=" * (-len(msg["raw"]) % 4))
        return RawItem(
            "email",
            f"gmail:{message_id}",
            raw,
            "message/rfc822",
            {"gmail_thread_id": msg.get("threadId"), "labels": sorted(labels)},
        )

    def sync(self, tokens: OAuthTokens, settings: dict[str, Any], cursor: dict[str, Any]) -> SyncPage:
        cursor = json.loads(json.dumps(cursor))  # never mutate the caller's copy
        gmail = cursor.setdefault("gmail", {})
        cal = cursor.setdefault("calendar", {})
        if settings.get("exclude_personal", True) and "_personal_label_ids" not in settings:
            names = {n.lower() for n in settings.get("personal_labels", ["Personal"])}
            settings = {
                **settings,
                "_personal_label_ids": [
                    label["id"] for label in self.list_labels(tokens) if label["name"].lower() in names
                ],
            }

        # 1. Gmail backfill
        if not gmail.get("backfill_done"):
            if "history_id" not in gmail:
                gmail["history_id"] = self._get(tokens, f"{GMAIL}/profile").json()["historyId"]
            params: dict[str, Any] = {"q": gmail_query(settings), "maxResults": MESSAGES_PER_PAGE}
            if gmail.get("page_token"):
                params["pageToken"] = gmail["page_token"]
            listing = self._get(tokens, f"{GMAIL}/messages", **params).json()
            items, skipped = [], 0
            for m in listing.get("messages", []):
                item = self._fetch_message(tokens, m["id"], settings)
                if item:
                    items.append(item)
                else:
                    skipped += 1
            gmail["page_token"] = listing.get("nextPageToken")
            if not gmail["page_token"]:
                gmail["backfill_done"] = True
                gmail.pop("page_token", None)
            return SyncPage(items, cursor, done=False, skipped=skipped)

        # 2. Calendar backfill (ends with a sync token)
        if not cal.get("sync_token"):
            params = {
                "singleEvents": "true",
                "maxResults": 250,
                "showDeleted": "false",
                "timeMin": (datetime.now(UTC) - timedelta(days=BACKFILL_DAYS)).isoformat(),
            }
            if cal.get("page_token"):
                params["pageToken"] = cal["page_token"]
            body = self._get(tokens, f"{CALENDAR}/events", **params).json()
            items = [
                RawItem(
                    "meeting", f"gcal:{e['id']}", json.dumps(normalise_event(e)).encode(), "application/json"
                )
                for e in body.get("items", [])
                if e.get("start")
            ]
            cal["page_token"] = body.get("nextPageToken")
            if body.get("nextSyncToken"):
                cal["sync_token"] = body["nextSyncToken"]
                cal.pop("page_token", None)
            return SyncPage(items, cursor, done=False)

        # 3. Incremental
        items = []
        params = {"startHistoryId": gmail["history_id"], "historyTypes": "messageAdded", "maxResults": 100}
        if gmail.get("history_page"):
            params["pageToken"] = gmail["history_page"]
        r = self.http.get(f"{GMAIL}/history", headers=self._h(tokens), params=params)
        if r.status_code == 404:
            # historyId expired (roughly a week of inactivity): re-run a backfill.
            cursor["gmail"] = {}
            return SyncPage([], cursor, done=False)
        body = check_response(r, "google").json()
        seen: set[str] = set()
        skipped = 0
        for h in body.get("history", []):
            for added in h.get("messagesAdded", []):
                mid = added["message"]["id"]
                if mid in seen:
                    continue
                seen.add(mid)
                item = self._fetch_message(tokens, mid, settings)
                if item:
                    items.append(item)
                else:
                    skipped += 1
        gmail["history_page"] = body.get("nextPageToken")
        if not gmail["history_page"]:
            gmail.pop("history_page", None)
            gmail["history_id"] = body.get("historyId", gmail["history_id"])

        params = {"syncToken": cal["sync_token"], "maxResults": 250}
        if cal.get("page_token"):
            params["pageToken"] = cal["page_token"]
        r = self.http.get(f"{CALENDAR}/events", headers=self._h(tokens), params=params)
        if r.status_code == 410:
            cursor["calendar"] = {}  # sync token invalidated: full calendar resync
            return SyncPage(items, cursor, done=False, skipped=skipped)
        body = check_response(r, "google").json()
        items += [
            RawItem("meeting", f"gcal:{e['id']}", json.dumps(normalise_event(e)).encode(), "application/json")
            for e in body.get("items", [])
            if e.get("start")
        ]
        cal["page_token"] = body.get("nextPageToken")
        if body.get("nextSyncToken"):
            cal["sync_token"] = body["nextSyncToken"]
            cal.pop("page_token", None)

        done = not gmail.get("history_page") and not cal.get("page_token")
        return SyncPage(items, cursor, done=done, skipped=skipped)
