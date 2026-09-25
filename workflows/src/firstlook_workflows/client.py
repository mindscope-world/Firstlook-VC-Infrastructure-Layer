"""Temporal client for the worker process."""

from __future__ import annotations

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from firstlook_core.config import get_settings

from .workflows import SourcingDailyWorkflow, SourcingDigestWorkflow, StrengthRecomputeWorkflow

_client: Client | None = None


async def client() -> Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = await Client.connect(s.temporal_address, namespace=s.temporal_namespace)
    return _client


async def ensure_nightly_strength() -> None:
    c = await client()
    await c.start_workflow(
        StrengthRecomputeWorkflow.run,
        id="strength-nightly",
        task_queue=get_settings().temporal_task_queue,
        cron_schedule="0 3 * * *",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def ensure_sourcing_schedules() -> None:
    """Daily sourcing at 04:00 UTC (07:00 Nairobi); digest Mondays 05:00 UTC."""
    c = await client()
    q = get_settings().temporal_task_queue
    await c.start_workflow(
        SourcingDailyWorkflow.run,
        id="sourcing-daily",
        task_queue=q,
        cron_schedule="0 4 * * *",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    await c.start_workflow(
        SourcingDigestWorkflow.run,
        id="sourcing-digest",
        task_queue=q,
        cron_schedule="0 5 * * 1",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
