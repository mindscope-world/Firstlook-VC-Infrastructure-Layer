"""Tenant-scoped database access.

All tenant data access goes through `tenant_tx`, which opens a transaction as
the RLS-bound app role and sets app.tenant_id / app.user_id / app.user_role
with SET LOCAL. The settings vanish when the transaction ends, so a pooled
connection can never carry one tenant's context into another request.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_pools: dict[str, ConnectionPool] = {}


def _pool(url: str) -> ConnectionPool:
    pool = _pools.get(url)
    if pool is None:
        pool = ConnectionPool(url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=True)
        _pools[url] = pool
    return pool


def close_pools() -> None:
    for pool in _pools.values():
        pool.close()
    _pools.clear()


def set_context(
    conn: psycopg.Connection, tenant_id: UUID | str, user_id: UUID | str | None, role: str
) -> None:
    conn.execute(
        "SELECT set_config('app.tenant_id', %s, true), set_config('app.user_id', %s, true),"
        " set_config('app.user_role', %s, true)",
        (str(tenant_id), str(user_id) if user_id else "", role),
    )


@contextmanager
def tenant_tx(
    tenant_id: UUID | str,
    user_id: UUID | str | None = None,
    role: str = "service",
    url: str | None = None,
) -> Iterator[psycopg.Connection]:
    """A transaction confined by RLS to one tenant.

    role is the user's role for user-initiated work, or "service" for
    background processing (which may see private interactions to process them).
    """
    with _pool(url or get_settings().database_url).connection() as conn, conn.transaction():
        set_context(conn, tenant_id, user_id, role)
        yield conn


@contextmanager
def system_tx(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Cross-tenant transaction for schedulers and the outbox relay only."""
    with _pool(url or get_settings().database_system_url).connection() as conn, conn.transaction():
        yield conn
