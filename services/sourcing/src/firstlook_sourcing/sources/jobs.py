"""Open roles from public job boards (Greenhouse, Lever). Hiring velocity is
the change in open roles over time, computed from these daily observations."""

from __future__ import annotations

import httpx

from ..model import Observation
from . import USER_AGENT


class JobBoardSource:
    name = "jobs"

    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})

    def observe(self, board: str) -> list[Observation]:
        kind, _, key = board.partition(":")
        if kind == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{key}/jobs"
            r = self.http.get(url)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
            titles = [j.get("title", "") for j in jobs]
        elif kind == "lever":
            url = f"https://api.lever.co/v0/postings/{key}"
            r = self.http.get(url, params={"mode": "json"})
            if r.status_code == 404:
                return []
            r.raise_for_status()
            titles = [j.get("text", "") for j in r.json()]
        else:
            return []
        engineering = sum(
            1 for t in titles if any(w in t.lower() for w in ("engineer", "developer", "data", "ml"))
        )
        return [
            Observation("open_roles", float(len(titles)), kind, url=url, detail={"titles": titles[:15]}),
            Observation("open_engineering_roles", float(engineering), kind, url=url),
        ]
