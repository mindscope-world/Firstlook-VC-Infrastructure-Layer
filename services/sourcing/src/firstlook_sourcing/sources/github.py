"""GitHub activity for companies with a known GitHub organisation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from ..model import Observation
from . import USER_AGENT


class GitHubSource:
    name = "github"

    def __init__(self, token: str | None = None, http: httpx.Client | None = None):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.http = http or httpx.Client(timeout=30, headers=headers)
        if http is not None:
            self.http.headers.update(headers)

    def observe(self, org: str) -> list[Observation]:
        url = f"https://api.github.com/orgs/{org}/repos"
        r = self.http.get(url, params={"per_page": 100, "sort": "pushed", "type": "public"})
        if r.status_code == 404:  # personal account rather than an org
            url = f"https://api.github.com/users/{org}/repos"
            r = self.http.get(url, params={"per_page": 100, "sort": "pushed"})
        if r.status_code in (403, 404, 429):
            return []  # rate-limited or gone: skip today, try again tomorrow
        r.raise_for_status()
        repos = [x for x in r.json() if not x.get("fork") and not x.get("archived")]
        cutoff = datetime.now(UTC) - timedelta(days=30)
        active = [
            x
            for x in repos
            if x.get("pushed_at") and datetime.fromisoformat(x["pushed_at"].replace("Z", "+00:00")) >= cutoff
        ]
        page = f"https://github.com/{org}"
        return [
            Observation(
                "github_stars", float(sum(x.get("stargazers_count", 0) for x in repos)), self.name, url=page
            ),
            Observation("github_public_repos", float(len(repos)), self.name, url=page),
            Observation(
                "github_active_repos_30d",
                float(len(active)),
                self.name,
                url=page,
                detail={"repos": [x["name"] for x in active[:10]]},
            ),
        ]
