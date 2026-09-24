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
    pages = iter([{"stored": 5, "duplicates": 0, "skipped": 1, "done": False},
                  {"stored": 2, "duplicates": 1, "skipped": 0, "done": True}])
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
            AccountSyncWorkflow.run, args=["t", "a", 60, 0], id=f"wf-{uuid.uuid4()}", task_queue="test")
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
            AccountSyncWorkflow.run, args=["t", "a", 60, 0], id=f"wf-{uuid.uuid4()}", task_queue="test")
    assert result["stopped"] == "AuthError" and len(calls) == 1
