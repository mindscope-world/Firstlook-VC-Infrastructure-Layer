"""Suite results, thresholds and the tenants evals run in."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = PACKAGE_ROOT / "golden"
THRESHOLDS = PACKAGE_ROOT / "thresholds.yaml"
EVAL_TENANT_SLUG = "firstlook-evals"


@dataclass
class SuiteResult:
    suite: str
    mode: str  # deterministic (no model) | golden (fixture answers) | gateway (live model)
    metrics: dict[str, float]
    cases: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class Check:
    suite: str
    metric: str
    minimum: float
    value: float | None

    @property
    def passed(self) -> bool:
        return self.value is not None and self.value >= self.minimum - 1e-9


def load_yaml(name: str) -> Any:
    return yaml.safe_load((GOLDEN / name).read_text())


def load_thresholds(path: Path = THRESHOLDS) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def checks_for(result: SuiteResult, thresholds: dict[str, Any]) -> list[Check]:
    """Thresholds under `always` apply in every mode. Those under `live` measure
    model quality and only apply when a real model answered."""
    spec = thresholds.get(result.suite, {})
    gates = dict(spec.get("always", {}))
    if result.mode == "gateway":
        gates.update(spec.get("live", {}))
    return [Check(result.suite, m, float(v), result.metrics.get(m)) for m, v in gates.items()]


@contextmanager
def scratch_tenant(name: str) -> Iterator[UUID]:
    """A throwaway tenant, purged afterwards (also on failure)."""
    from firstlook_core.db import system_tx, tenant_tx
    from firstlook_core.tenants import create_tenant

    slug = f"eval-{name}-{uuid.uuid4().hex[:8]}"
    with tenant_tx("00000000-0000-0000-0000-000000000000") as conn:
        tenant_id = create_tenant(conn, f"Eval: {name}", slug)
    try:
        yield tenant_id
    finally:
        with system_tx() as conn:
            conn.execute("SELECT purge_tenant(%s)", (str(tenant_id),))


def eval_tenant() -> UUID:
    """The persistent tenant that live-model evals are billed to in the gateway,
    so their spend shows up in llm_usage like any other tenant's."""
    from firstlook_core.db import system_tx, tenant_tx
    from firstlook_core.tenants import create_tenant

    with system_tx() as conn:
        row = conn.execute("SELECT id FROM tenants WHERE slug = %s", (EVAL_TENANT_SLUG,)).fetchone()
    if row:
        return row["id"]
    with tenant_tx("00000000-0000-0000-0000-000000000000") as conn:
        return create_tenant(conn, "Firstlook evals", EVAL_TENANT_SLUG)
