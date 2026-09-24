"""Google Meet transcripts via the Meet REST API (v2).

Separate from the Gmail/Calendar connector so the extra scope is only
requested from users who record meetings. Meet reports speakers by display
name, not email; the resolver matches names against known people.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .base import OAuthTokens, RawItem, SyncPage, check_response
from .google import GoogleConnector

MEET = "https://meet.googleapis.com/v2"
BACKFILL_DAYS = 180


def _seconds_between(a: str, b: str) -> float:
    fa = datetime.fromisoformat(a.replace("Z", "+00:00"))
    fb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return (fb - fa).total_seconds()


class GoogleMeetConnector(GoogleConnector):
    provider = "google_meet"
    scopes = ["openid", "email", "https://www.googleapis.com/auth/meetings.space.readonly"]

    def _paged(self, tokens: OAuthTokens, url: str, key: str, **params: Any) -> list[dict[str, Any]]:
        out, token = [], None
        while True:
            if token:
                params["pageToken"] = token
            body = self._get(tokens, url, **params).json()
            out += body.get(key, [])
            token = body.get("nextPageToken")
            if not token:
                return out

    def transcript_for(self, tokens: OAuthTokens, record: dict[str, Any]) -> RawItem | None:
        name = record["name"]  # conferenceRecords/{id}
        transcripts = [
            t
            for t in self._paged(tokens, f"{MEET}/{name}/transcripts", "transcripts")
            if t.get("state") == "FILE_GENERATED"
        ]
        if not transcripts:
            return None
        participants = {}
        for p in self._paged(tokens, f"{MEET}/{name}/participants", "participants"):
            who = p.get("signedinUser") or p.get("anonymousUser") or p.get("phoneUser") or {}
            participants[p["name"]] = who.get("displayName")
        entries = self._paged(
            tokens, f"{MEET}/{transcripts[0]['name']}/entries", "transcriptEntries", pageSize=100
        )
        start = record.get("startTime")
        segments = [
            {
                "speaker": participants.get(e.get("participant")),
                "start": _seconds_between(start, e["startTime"]) if start and e.get("startTime") else 0,
                "end": _seconds_between(start, e["endTime"]) if start and e.get("endTime") else 0,
                "text": e.get("text", ""),
            }
            for e in entries
        ]
        transcript = {
            "id": f"meet:{name}",
            "provider": "google_meet",
            "title": record.get("space", ""),
            "start": start.replace("Z", "+00:00"),
            "duration_s": int(_seconds_between(start, record["endTime"])) if record.get("endTime") else None,
            "meeting_external_id": record.get("space"),
            "participants": [
                {"name": n, "email": None} for n in sorted({v for v in participants.values() if v})
            ],
            "segments": segments,
        }
        return RawItem("transcript", transcript["id"], json.dumps(transcript).encode(), "application/json")

    def sync(self, tokens: OAuthTokens, settings: dict[str, Any], cursor: dict[str, Any]) -> SyncPage:
        cursor = dict(cursor)
        since = cursor.get("since") or (datetime.now(UTC) - timedelta(days=BACKFILL_DAYS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        params: dict[str, Any] = {"filter": f'end_time>="{since}"', "pageSize": 25}
        if cursor.get("page_token"):
            params["pageToken"] = cursor["page_token"]
        body = check_response(
            self.http.get(f"{MEET}/conferenceRecords", headers=self._h(tokens), params=params), "google_meet"
        ).json()
        records = body.get("conferenceRecords", [])
        items = [item for r in records if r.get("endTime") and (item := self.transcript_for(tokens, r))]
        if body.get("nextPageToken"):
            cursor["page_token"] = body["nextPageToken"]
            return SyncPage(items, cursor, done=False)
        cursor.pop("page_token", None)
        # Transcripts are generated some time after the call: overlap by a day.
        cursor["since"] = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return SyncPage(items, cursor, done=True)
