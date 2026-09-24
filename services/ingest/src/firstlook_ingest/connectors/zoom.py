"""Zoom cloud-recording transcripts.

Lists the user's cloud recordings in 30-day windows (the API's maximum range)
and downloads each TRANSCRIPT file (VTT). Participant emails come from the
past-meeting participants report when the account has that scope.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from firstlook_core.config import get_settings

from .base import AuthError, OAuthTokens, RawItem, SyncPage, check_response
from .vtt import parse_vtt

API = "https://api.zoom.us/v2"
BACKFILL_DAYS = 180


class ZoomConnector:
    provider = "zoom"
    scopes = [
        "cloud_recording:read:list_user_recordings",
        "cloud_recording:read:list_recording_files",
        "meeting:read:list_past_participants",
        "user:read:email",
    ]

    def __init__(self, http: httpx.Client | None = None):
        s = get_settings()
        self.client_id, self.client_secret = s.zoom_client_id, s.zoom_client_secret
        self.http = http or httpx.Client(timeout=60, follow_redirects=True)

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        if not self.client_id:
            raise AuthError("ZOOM_CLIENT_ID is not configured")
        return "https://zoom.us/oauth/authorize?" + urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )

    def _token(self, data: dict[str, str]) -> OAuthTokens:
        r = self.http.post(
            "https://zoom.us/oauth/token", data=data, auth=(self.client_id or "", self.client_secret or "")
        )
        if r.status_code in (400, 401):
            raise AuthError(f"zoom token endpoint: {r.text[:300]}")
        body = check_response(r, "zoom").json()
        return OAuthTokens(
            body["access_token"],
            body.get("refresh_token"),
            time.time() + body.get("expires_in", 3600),
            body.get("scope", ""),
        )

    def exchange_code(self, code: str, redirect_uri: str) -> tuple[OAuthTokens, str]:
        tokens = self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri})
        me = check_response(self.http.get(f"{API}/users/me", headers=self._h(tokens)), "zoom").json()
        return tokens, me["email"].lower()

    def refresh(self, tokens: OAuthTokens) -> OAuthTokens:
        if not tokens.refresh_token:
            raise AuthError("no refresh token; reconnect the account")
        return self._token({"grant_type": "refresh_token", "refresh_token": tokens.refresh_token})

    @staticmethod
    def _h(tokens: OAuthTokens) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}"}

    def _participants(self, tokens: OAuthTokens, meeting_uuid: str) -> list[dict[str, Any]]:
        # UUIDs starting with / or containing // must be double-encoded.
        encoded = urllib.parse.quote(urllib.parse.quote(meeting_uuid, safe=""), safe="")
        r = self.http.get(
            f"{API}/past_meetings/{encoded}/participants", headers=self._h(tokens), params={"page_size": 300}
        )
        if r.status_code in (400, 403, 404):
            return []  # scope not granted or report unavailable: speakers stay name-only
        body = check_response(r, "zoom").json()
        seen, out = set(), []
        for p in body.get("participants", []):
            key = (p.get("user_email") or p.get("name") or "").lower()
            if key and key not in seen:
                seen.add(key)
                out.append({"name": p.get("name"), "email": p.get("user_email") or None})
        return out

    def transcript_for(self, tokens: OAuthTokens, meeting: dict[str, Any]) -> RawItem | None:
        files = [f for f in meeting.get("recording_files", []) if f.get("file_type") == "TRANSCRIPT"]
        if not files:
            return None
        f = files[0]
        vtt = check_response(self.http.get(f["download_url"], headers=self._h(tokens)), "zoom").text
        transcript = {
            "id": f"zoom:{meeting['uuid']}",
            "provider": "zoom",
            "title": meeting.get("topic", ""),
            "start": meeting["start_time"].replace("Z", "+00:00"),
            "duration_s": int(meeting.get("duration", 0)) * 60,
            "meeting_external_id": str(meeting.get("id")),
            "participants": self._participants(tokens, meeting["uuid"]),
            "segments": parse_vtt(vtt),
        }
        return RawItem("transcript", transcript["id"], json.dumps(transcript).encode(), "application/json")

    def sync(self, tokens: OAuthTokens, settings: dict[str, Any], cursor: dict[str, Any]) -> SyncPage:
        cursor = dict(cursor)
        today = datetime.now(UTC).date()
        start = (
            date.fromisoformat(cursor["from"])
            if cursor.get("from")
            else today - timedelta(days=BACKFILL_DAYS)
        )
        end = min(start + timedelta(days=30), today)
        params: dict[str, Any] = {"from": start.isoformat(), "to": end.isoformat(), "page_size": 100}
        if cursor.get("page_token"):
            params["next_page_token"] = cursor["page_token"]
        body = check_response(
            self.http.get(f"{API}/users/me/recordings", headers=self._h(tokens), params=params), "zoom"
        ).json()
        items = [item for m in body.get("meetings", []) if (item := self.transcript_for(tokens, m))]
        if body.get("next_page_token"):
            cursor["page_token"] = body["next_page_token"]
            return SyncPage(items, cursor, done=False)
        cursor.pop("page_token", None)
        if end >= today:
            # Caught up. Re-scan the last two days next time: transcripts arrive late.
            cursor["from"] = (today - timedelta(days=2)).isoformat()
            return SyncPage(items, cursor, done=True)
        cursor["from"] = end.isoformat()
        return SyncPage(items, cursor, done=False)
