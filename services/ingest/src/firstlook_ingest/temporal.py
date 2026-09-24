"""Start Temporal workflows by name (the workflow code lives in
firstlook_workflows, which depends on this package, not the reverse)."""

from __future__ import annotations

import logging
import uuid

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from firstlook_core.config import get_settings

log = logging.getLogger("firstlook.ingest.temporal")
_client: Client | None = None


async def _get() -> Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = await Client.connect(s.temporal_address, namespace=s.temporal_namespace)
    return _client


async def start_account_sync(tenant_id: str, account_id: str, interval_seconds: int = 300) -> str | None:
    """Start (or attach to) the account's long-lived sync workflow. Returns
    None when Temporal is unreachable so connecting an account still succeeds."""
    try:
        client = await _get()
        handle = await client.start_workflow(
            "AccountSyncWorkflow",
            args=[tenant_id, account_id, interval_seconds, 0],
            id=f"sync-{account_id}",
            task_queue=get_settings().temporal_task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
        return handle.id
    except Exception as e:  # noqa: BLE001
        log.warning("could not start sync workflow for %s: %s", account_id, e)
        return None


async def start_crm_import(tenant_id: str, user_id: str, vendor: str, sealed: str) -> str:
    client = await _get()
    handle = await client.start_workflow(
        "CrmApiImportWorkflow",
        args=[tenant_id, user_id, vendor, sealed],
        id=f"crm-import-{uuid.uuid4()}",
        task_queue=get_settings().temporal_task_queue,
    )
    return handle.id
