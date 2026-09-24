"""Best-effort Langfuse tracing via its public ingestion API.

Enabled when LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are
set. Failures are logged and never affect the request.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)


def trace_generation(
    *,
    tenant_id: str,
    task: str,
    model: str,
    input: Any,
    output: Any,
    input_tokens: int,
    output_tokens: int,
    started: datetime,
    ended: datetime,
) -> None:
    host = os.environ.get("LANGFUSE_HOST")
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    if not (host and pk and sk):
        return
    trace_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    batch = [
        {
            "id": str(uuid.uuid4()),
            "type": "trace-create",
            "timestamp": now,
            "body": {"id": trace_id, "name": task, "userId": tenant_id, "tags": [task]},
        },
        {
            "id": str(uuid.uuid4()),
            "type": "generation-create",
            "timestamp": now,
            "body": {
                "traceId": trace_id,
                "name": task,
                "model": model,
                "input": input,
                "output": output,
                "startTime": started.isoformat(),
                "endTime": ended.isoformat(),
                "usage": {"input": input_tokens, "output": output_tokens, "unit": "TOKENS"},
            },
        },
    ]
    try:
        httpx.post(f"{host}/api/public/ingestion", json={"batch": batch}, auth=(pk, sk), timeout=5)
    except httpx.HTTPError as e:
        log.warning("langfuse trace failed: %s", e)
