import base64
import json
import time

import httpx
import respx

from firstlook_ingest.connectors.base import OAuthTokens, RateLimited
from firstlook_ingest.connectors.google import GMAIL, GoogleConnector, gmail_query
from firstlook_ingest.connectors.microsoft import GRAPH, MicrosoftConnector
from firstlook_ingest.connectors.vtt import parse_vtt
from firstlook_ingest.connectors.zoom import ZoomConnector

TOKENS = OAuthTokens("at", "rt", time.time() + 3600)
RAW = b"From: a@b.com\r\nTo: c@d.com\r\nSubject: hi\r\nMessage-ID: <1@x>\r\n\r\nhello\r\n"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def test_gmail_query_excludes_noise_and_personal():
    q = gmail_query({"labels": ["Deals", "INBOX"], "exclude_personal": True, "personal_labels": ["Family"]})
    assert "-category:promotions" in q and '-label:"Family"' in q and '{label:"Deals" label:"INBOX"}' in q


@respx.mock
def test_google_sync_phases():
    respx.get(f"{GMAIL}/labels").respond(json={"labels": [{"id": "Label_9", "name": "Personal"}]})
    respx.get(f"{GMAIL}/profile").respond(json={"historyId": "100"})
    respx.get(f"{GMAIL}/messages").respond(json={"messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]})
    respx.get(f"{GMAIL}/messages/m1").respond(json={"raw": b64(RAW), "labelIds": ["INBOX"], "threadId": "t1"})
    respx.get(f"{GMAIL}/messages/m2").respond(json={"raw": b64(RAW), "labelIds": ["CATEGORY_PROMOTIONS"]})
    respx.get(f"{GMAIL}/messages/m3").respond(json={"raw": b64(RAW), "labelIds": ["Label_9"]})
    events_route = respx.get("https://www.googleapis.com/calendar/v3/calendars/primary/events")
    events_route.respond(
        json={
            "items": [
                {
                    "id": "e1",
                    "summary": "Call",
                    "start": {"dateTime": "2026-09-01T10:00:00+03:00"},
                    "end": {"dateTime": "2026-09-01T10:30:00+03:00"},
                    "attendees": [{"email": "x@y.com", "responseStatus": "accepted"}],
                }
            ],
            "nextSyncToken": "sync-1",
        }
    )
    respx.get(f"{GMAIL}/history").respond(
        json={"history": [{"messagesAdded": [{"message": {"id": "m1"}}]}], "historyId": "120"}
    )

    c = GoogleConnector(http=httpx.Client())
    page = c.sync(TOKENS, {"exclude_personal": True}, {})
    assert [i.external_id for i in page.items] == ["gmail:m1"]
    assert page.items[0].data == RAW and page.skipped == 2
    assert page.cursor["gmail"]["backfill_done"] and page.cursor["gmail"]["history_id"] == "100"

    page = c.sync(TOKENS, {"exclude_personal": True}, page.cursor)
    assert page.items[0].kind == "meeting"
    assert json.loads(page.items[0].data)["attendees"][0]["email"] == "x@y.com"
    assert page.cursor["calendar"]["sync_token"] == "sync-1"

    page = c.sync(TOKENS, {"exclude_personal": True}, page.cursor)
    assert page.done and page.cursor["gmail"]["history_id"] == "120"


@respx.mock
def test_google_rate_limit_raises_retryable():
    respx.get(f"{GMAIL}/labels").respond(json={"labels": []})
    respx.get(f"{GMAIL}/profile").respond(429, headers={"Retry-After": "12"})
    try:
        GoogleConnector(http=httpx.Client()).sync(TOKENS, {}, {})
    except RateLimited as e:
        assert e.retry_after == 12
    else:
        raise AssertionError("expected RateLimited")


@respx.mock
def test_microsoft_delta_and_personal_category():
    respx.get(url__startswith=f"{GRAPH}/me/mailFolders/inbox/messages/delta").respond(
        json={
            "value": [{"id": "a"}, {"id": "b", "categories": ["Personal"]}, {"id": "c", "@removed": {}}],
            "@odata.deltaLink": f"{GRAPH}/delta-inbox",
        }
    )
    respx.get(f"{GRAPH}/me/messages/a/$value").respond(content=RAW)
    c = MicrosoftConnector(http=httpx.Client())
    page = c.sync(TOKENS, {"folders": ["inbox"]}, {})
    assert [i.external_id for i in page.items] == ["outlook:a"] and page.skipped == 1
    assert page.cursor["mail"]["inbox"]["delta"] == f"{GRAPH}/delta-inbox"


def test_vtt_parsing_merges_speaker_turns():
    vtt = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
Paul Otieno: Thanks for joining.

2
00:00:04.500 --> 00:00:06.000
Paul Otieno: Let's start.

3
00:00:06.000 --> 00:00:09.000
<v Wanjiru Kamau>Happy to be here.</v>
"""
    segs = parse_vtt(vtt)
    assert [s["speaker"] for s in segs] == ["Paul Otieno", "Wanjiru Kamau"]
    assert segs[0]["text"] == "Thanks for joining. Let's start." and segs[1]["text"] == "Happy to be here."


@respx.mock
def test_zoom_transcripts():
    respx.get(url__startswith="https://api.zoom.us/v2/users/me/recordings").respond(
        json={
            "meetings": [
                {
                    "uuid": "abc==",
                    "id": 99,
                    "topic": "Founder call",
                    "start_time": "2026-09-01T10:00:00Z",
                    "duration": 30,
                    "recording_files": [
                        {"file_type": "TRANSCRIPT", "download_url": "https://zoom.us/rec/download/t1"}
                    ],
                }
            ]
        }
    )
    respx.get("https://zoom.us/rec/download/t1").respond(
        text="WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\nA: hi\n"
    )
    respx.get(url__startswith="https://api.zoom.us/v2/past_meetings/").respond(
        json={"participants": [{"name": "A", "user_email": "a@x.io"}]}
    )
    page = ZoomConnector(http=httpx.Client()).sync(TOKENS, {}, {})
    t = json.loads(page.items[0].data)
    assert t["id"] == "zoom:abc==" and t["participants"] == [{"name": "A", "email": "a@x.io"}]
    assert t["segments"][0]["speaker"] == "A"
