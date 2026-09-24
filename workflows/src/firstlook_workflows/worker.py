"""Temporal worker: `uv run python -m firstlook_workflows.worker`."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging

from temporalio.worker import Worker

from firstlook_core.config import get_settings

from . import activities
from .client import client, ensure_nightly_strength
from .workflows import AccountSyncWorkflow, CrmApiImportWorkflow, StrengthRecomputeWorkflow


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    c = await client()
    await ensure_nightly_strength()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        worker = Worker(
            c,
            task_queue=get_settings().temporal_task_queue,
            workflows=[AccountSyncWorkflow, StrengthRecomputeWorkflow, CrmApiImportWorkflow],
            activities=[
                activities.sync_page,
                activities.account_status,
                activities.list_tenants,
                activities.recompute_strength,
                activities.crm_api_import,
            ],
            activity_executor=pool,
        )
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
