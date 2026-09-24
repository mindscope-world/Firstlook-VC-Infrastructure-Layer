"""Temporal activities. Thin wrappers over service code, translating errors
into Temporal retry semantics:

  AuthError   -> non-retryable (the user must reconnect)
  RateLimited -> retryable, after the provider's Retry-After
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from firstlook_core.crypto import unseal
from firstlook_core.db import system_tx, tenant_tx
from firstlook_ingest.accounts import sync_once
from firstlook_ingest.connectors.base import AuthError, RateLimited
from firstlook_resolver import strength


@activity.defn
def sync_page(tenant_id: str, account_id: str) -> dict[str, Any]:
    try:
        return asdict(sync_once(tenant_id, account_id))
    except AuthError as e:
        raise ApplicationError(str(e), type="AuthError", non_retryable=True) from e
    except RateLimited as e:
        raise ApplicationError(
            str(e), type="RateLimited", next_retry_delay=timedelta(seconds=e.retry_after)
        ) from e
    except LookupError as e:
        raise ApplicationError(str(e), type="NotFound", non_retryable=True) from e


@activity.defn
def account_status(tenant_id: str, account_id: str) -> str:
    with tenant_tx(tenant_id) as conn:
        row = conn.execute("SELECT status FROM connector_accounts WHERE id = %s", (account_id,)).fetchone()
    return row["status"] if row else "revoked"


@activity.defn
def list_tenants() -> list[str]:
    with system_tx() as conn:
        return [str(r["id"]) for r in conn.execute("SELECT id FROM tenants ORDER BY created_at").fetchall()]


@activity.defn
def recompute_strength(tenant_id: str) -> int:
    with tenant_tx(tenant_id) as conn:
        return strength.recompute(conn, tenant_id)


@activity.defn
def crm_api_import(tenant_id: str, user_id: str, vendor: str, sealed_credentials: str) -> dict[str, Any]:
    from firstlook_ingest.connectors.base import RawItem
    from firstlook_ingest.crm import api_import
    from firstlook_ingest.crm.importer import import_records
    from firstlook_ingest.raw import land

    with tenant_tx(tenant_id) as conn:
        creds = unseal(conn, tenant_id, sealed_credentials)
    fetchers = {
        "hubspot": lambda: api_import.fetch_hubspot(creds["token"]),
        "affinity": lambda: api_import.fetch_affinity(creds["api_key"]),
        "salesforce": lambda: api_import.fetch_salesforce(creds["instance_url"], creds["access_token"]),
        "airtable": lambda: api_import.fetch_airtable(
            creds["token"],
            creds["base_id"],
            creds["table"],
            creds.get("object_type", "people"),
            creds.get("mapping"),
        ),
    }
    if vendor not in fetchers:
        raise ApplicationError(f"unknown CRM vendor {vendor}", non_retryable=True)
    records = fetchers[vendor]()
    snapshot = json.dumps(
        {k: [r.__dict__ for r in getattr(records, k)] for k in ("companies", "people", "deals", "notes")},
        default=str,
    ).encode()
    with tenant_tx(tenant_id, user_id, "service") as conn:
        source_id = land(
            conn,
            tenant_id,
            f"crm_{vendor}",
            RawItem(
                "crm_export", f"api:{hashlib.sha256(snapshot).hexdigest()}", snapshot, "application/json"
            ),
        )
        result = import_records(conn, tenant_id, vendor, records, source_id=source_id, actor_id=UUID(user_id))
    return asdict(result)
