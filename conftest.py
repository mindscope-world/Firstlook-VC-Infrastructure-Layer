"""Shared pytest setup.

DB tests run against the `firstlook_test` database in the local Postgres
(created by compose/postgres/init). The schema is rebuilt once per session.
Tests connect as the RLS-bound app role, exactly like the services do.
"""

import os
import tempfile

_PG = os.environ.get("TEST_PG_HOSTPORT", "localhost:15432")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", f"postgresql://firstlook_app:firstlook_app@{_PG}/firstlook_test")
os.environ.setdefault("DATABASE_OWNER_URL", f"postgresql://firstlook:firstlook@{_PG}/firstlook_test")
os.environ.setdefault(
    "DATABASE_SYSTEM_URL", f"postgresql://firstlook_system:firstlook_system@{_PG}/firstlook_test"
)
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_LOCAL_ROOT", tempfile.mkdtemp(prefix="firstlook-test-objects-"))
os.environ.setdefault("BUS_BACKEND", "memory")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import psycopg  # noqa: E402
import pytest  # noqa: E402


def _db_available() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_OWNER_URL"], connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def migrated_db():
    if not _db_available():
        pytest.skip("local Postgres not running (make up)")
    from firstlook_core.migrate import migrate, reset

    reset()
    migrate(verbose=False)
    yield
    from firstlook_core.db import close_pools

    close_pools()


@pytest.fixture
def llm():
    from firstlook_core.llm import FakeLlm, set_llm

    fake = FakeLlm()
    set_llm(fake)
    yield fake
    set_llm(None)


@pytest.fixture
def make_tenant(migrated_db):
    """Create a tenant with one admin user. Returns (tenant_id, user_id, person_id)."""
    import uuid

    from firstlook_core.db import tenant_tx
    from firstlook_core.tenants import create_tenant, create_user

    def _make(name: str = "Test Fund", users: list[tuple[str, str, str]] | None = None):
        slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        with (
            psycopg.connect(os.environ["DATABASE_URL"], row_factory=psycopg.rows.dict_row) as conn,
            conn.transaction(),
        ):
            tenant_id = create_tenant(conn, name, slug)
        created = []
        with tenant_tx(tenant_id) as conn:
            for email, uname, role in users or [(f"admin@{slug}.vc", "Admin User", "admin")]:
                created.append(create_user(conn, tenant_id, email, uname, role))
        return tenant_id, created

    return _make
