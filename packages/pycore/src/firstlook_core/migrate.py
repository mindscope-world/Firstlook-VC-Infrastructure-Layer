"""Minimal forward-only migration runner for packages/schema/migrations.

Migrations are plain SQL files named NNNN_description.sql, applied in order as
the owner role, each in its own transaction, and recorded in
schema_migrations with a checksum so edited history is detected.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import psycopg

from .config import REPO_ROOT, get_settings

MIGRATIONS_DIR = REPO_ROOT / "packages" / "schema" / "migrations"


def _files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def migrate(url: str | None = None, verbose: bool = True) -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(url or get_settings().database_owner_url, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
        for path in _files():
            version = path.stem
            sql = path.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"migration {version} was edited after being applied")
                continue
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)", (version, checksum)
                )
            applied_now.append(version)
            if verbose:
                print(f"applied {version}")
    return applied_now


def reset(url: str | None = None) -> None:
    """Drop and recreate the public schema. Local development and tests only."""
    if get_settings().env not in {"local", "test", "ci"}:
        raise RuntimeError("refusing to reset a non-local database")
    with psycopg.connect(url or get_settings().database_owner_url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute("GRANT USAGE ON SCHEMA public TO firstlook_app, firstlook_system")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firstlook-migrate")
    parser.add_argument("--reset", action="store_true", help="drop everything first (local only)")
    parser.add_argument("--url", help="owner connection URL (defaults to DATABASE_OWNER_URL)")
    args = parser.parse_args(argv)
    if args.reset:
        reset(args.url)
    migrate(args.url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
