from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from . import activities

SYNC_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=15),
    maximum_attempts=0,
    non_retryable_error_types=["AuthError", "NotFound"],
)


@workflow.defn
class AccountSyncWorkflow:
    """One long-lived workflow per connector account (id: sync-<account_id>).

    The first rounds page through history (backfill); after that each round
    fetches what changed since the cursor, then sleeps. continue_as_new keeps
    the event history bounded.
    """

    @workflow.run
    async def run(
        self, tenant_id: str, account_id: str, interval_seconds: int = 300, rounds: int = 0
    ) -> dict:
        totals = {"stored": 0, "duplicates": 0, "skipped": 0}
        while True:
            status = await workflow.execute_activity(
                activities.account_status,
                args=[tenant_id, account_id],
                start_to_close_timeout=timedelta(seconds=30),
            )
            if status in ("revoked", "paused"):
                return {**totals, "stopped": status}
            try:
                while True:
                    page = await workflow.execute_activity(
                        activities.sync_page,
                        args=[tenant_id, account_id],
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=SYNC_RETRY,
                    )
                    for k in totals:
                        totals[k] += page[k]
                    if page["done"]:
                        break
            except ActivityError as e:
                cause = e.cause
                if isinstance(cause, ApplicationError) and cause.type in ("AuthError", "NotFound"):
                    return {**totals, "stopped": cause.type}
                raise
            rounds += 1
            if rounds % 50 == 0:
                workflow.continue_as_new(args=[tenant_id, account_id, interval_seconds, rounds])
            await workflow.sleep(timedelta(seconds=interval_seconds))


@workflow.defn
class StrengthRecomputeWorkflow:
    """Nightly: recency decays even without new interactions."""

    @workflow.run
    async def run(self) -> dict[str, int]:
        tenants = await workflow.execute_activity(
            activities.list_tenants, start_to_close_timeout=timedelta(minutes=1)
        )
        out = {}
        for t in tenants:
            out[t] = await workflow.execute_activity(
                activities.recompute_strength, t, start_to_close_timeout=timedelta(minutes=30)
            )
        return out


@workflow.defn
class CrmApiImportWorkflow:
    @workflow.run
    async def run(self, tenant_id: str, user_id: str, vendor: str, sealed_credentials: str) -> dict[str, Any]:
        return await workflow.execute_activity(
            activities.crm_api_import,
            args=[tenant_id, user_id, vendor, sealed_credentials],
            start_to_close_timeout=timedelta(hours=2),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=30)),
        )
