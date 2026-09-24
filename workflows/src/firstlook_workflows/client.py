"""Temporal client for the worker process."""

from __future__ import annotations

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from firstlook_core.config import get_settings

from .workflows import StrengthRecomputeWorkflow

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
