"""Entry points used by workflows, the bus consumer and the CLI."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from firstlook_core.config import REPO_ROOT, get_settings
from firstlook_core.db import tenant_tx

from .collect import Collector, CollectStats
from .run import score_all, score_thesis
from .sources.github import GitHubSource
from .sources.jobs import JobBoardSource
from .sources.news import NewsSource
from .sources.vendor import SandboxVendor, VendorSource

log = logging.getLogger("firstlook.sourcing")

SANDBOX_VENDOR = REPO_ROOT / "packages" / "fixtures" / "data" / "vendor_sandbox.json"


def get_vendor() -> VendorSource | None:
    s = get_settings()
    if s.sourcing_vendor == "sandbox":
        return SandboxVendor(s.sourcing_vendor_path or SANDBOX_VENDOR)
    if s.sourcing_vendor in ("", "none"):
        return None
    raise ValueError(f"no adapter for vendor {s.sourcing_vendor!r} yet")


def collect_tenant(tenant_id: UUID | str, *, network: bool = True, **overrides: Any) -> CollectStats:
    """Discover and enrich companies for one tenant. network=False uses only the
    vendor adapter (the sandbox is a local file), for tests and offline dev."""
    s = get_settings()
    news = overrides.pop("news", None)
    if news is None and network:
        feeds = [f.strip() for f in s.sourcing_rss_feeds.split(",")] if s.sourcing_rss_feeds else None
        news = NewsSource(feeds)
    items = news.fetch() if news else []
    with tenant_tx(tenant_id) as conn:
        c = Collector(
            conn,
            tenant_id,
            vendor=overrides.pop("vendor", None) or get_vendor(),
            github=overrides.pop("github", None) or (GitHubSource(s.github_token) if network else None),
            jobs=overrides.pop("jobs", None) or (JobBoardSource() if network else None),
            **overrides,
        )
        c.discover(items)
        c.enrich(items)
        return c.stats


def score_tenant(tenant_id: UUID | str, thesis_version_id: UUID | str | None = None) -> list[str]:
    with tenant_tx(tenant_id) as conn:
        if thesis_version_id:
            return [str(score_thesis(conn, tenant_id, thesis_version_id))]
        return [str(r) for r in score_all(conn, tenant_id)]
