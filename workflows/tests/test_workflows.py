"""Workflow logic with stubbed activities, on Temporal's time-skipping test server."""

import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from firstlook_workflows.workflows import AccountSyncWorkflow


async def _env():
    try:
        return await WorkflowEnvironment.start_time_skipping()
    except Exception as e:  # noqa: BLE001 - test server download needs network
        pytest.skip(f"Temporal test server unavailable: {e}")


def _worker(env, activities):
    return Worker(env.client, task_queue="test", workflows=[AccountSyncWorkflow], activities=activities)


@pytest.mark.integration
async def test_sync_pages_until_done_then_stops_when_paused():
    pages = iter(
        [
            {"stored": 5, "duplicates": 0, "skipped": 1, "done": False},
            {"stored": 2, "duplicates": 1, "skipped": 0, "done": True},
        ]
    )
    statuses = iter(["active", "paused"])

    @activity.defn(name="account_status")
    async def account_status(tenant_id: str, account_id: str) -> str:
        return next(statuses)

    @activity.defn(name="sync_page")
    async def sync_page(tenant_id: str, account_id: str) -> dict:
        return next(pages)

    env = await _env()
    async with env, _worker(env, [account_status, sync_page]):
        result = await env.client.execute_workflow(
            AccountSyncWorkflow.run, args=["t", "a", 60, 0], id=f"wf-{uuid.uuid4()}", task_queue="test"
        )
    assert result == {"stored": 7, "duplicates": 1, "skipped": 1, "stopped": "paused"}


@pytest.mark.integration
async def test_auth_error_stops_workflow_without_retrying():
    calls = []

    @activity.defn(name="account_status")
    async def account_status(tenant_id: str, account_id: str) -> str:
        return "active"

    @activity.defn(name="sync_page")
    async def sync_page(tenant_id: str, account_id: str) -> dict:
        calls.append(1)
        raise ApplicationError("token revoked", type="AuthError", non_retryable=True)

    env = await _env()
    async with env, _worker(env, [account_status, sync_page]):
        result = await env.client.execute_workflow(
            AccountSyncWorkflow.run, args=["t", "a", 60, 0], id=f"wf-{uuid.uuid4()}", task_queue="test"
        )
    assert result["stopped"] == "AuthError" and len(calls) == 1


@pytest.mark.integration
async def test_sourcing_daily_collects_then_scores_each_tenant():
    from firstlook_workflows.workflows import SourcingDailyWorkflow

    order = []

    @activity.defn(name="list_tenants")
    async def list_tenants() -> list[str]:
        return ["t1", "t2"]

    @activity.defn(name="sourcing_collect")
    async def sourcing_collect(t: str) -> dict:
        order.append(("collect", t))
        return {"discovered": 1}

    @activity.defn(name="sourcing_score")
    async def sourcing_score(t: str) -> list[str]:
        order.append(("score", t))
        return [f"run-{t}"]

    env = await _env()
    async with (
        env,
        Worker(
            env.client,
            task_queue="test",
            workflows=[SourcingDailyWorkflow],
            activities=[list_tenants, sourcing_collect, sourcing_score],
        ),
    ):
        result = await env.client.execute_workflow(
            SourcingDailyWorkflow.run, id=f"wf-{uuid.uuid4()}", task_queue="test"
        )
    assert order == [("collect", "t1"), ("score", "t1"), ("collect", "t2"), ("score", "t2")]
    assert result["t2"]["runs"] == ["run-t2"]
