"""CLI:
uv run python -m firstlook_sourcing collect --tenant savanna [--offline]
uv run python -m firstlook_sourcing score --tenant savanna
uv run python -m firstlook_sourcing registry --tenant savanna --file extract.csv [--registry ke-brs]
uv run python -m firstlook_sourcing digest --tenant savanna
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from firstlook_core.db import system_tx, tenant_tx

from . import digest
from .collect import import_registry
from .service import collect_tenant, score_tenant


def _tenant(slug: str) -> str:
    with system_tx() as conn:
        row = conn.execute("SELECT id FROM tenants WHERE slug = %s", (slug,)).fetchone()
    if row is None:
        sys.exit(f"no tenant with slug {slug!r}")
    return str(row["id"])


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="firstlook-sourcing")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("collect", "score", "registry", "digest"):
        p = sub.add_parser(name)
        p.add_argument("--tenant", required=True, help="tenant slug")
        if name == "collect":
            p.add_argument("--offline", action="store_true", help="vendor adapter only; no network sources")
        if name == "registry":
            p.add_argument("--file", required=True, type=Path)
            p.add_argument("--registry", default="ke-brs")
            p.add_argument("--country", default="KE")
    args = parser.parse_args(argv)
    tenant_id = _tenant(args.tenant)
    if args.cmd == "collect":
        print(collect_tenant(tenant_id, network=not args.offline))
    elif args.cmd == "score":
        print(score_tenant(tenant_id))
    elif args.cmd == "registry":
        with tenant_tx(tenant_id) as conn:
            print(import_registry(conn, tenant_id, args.file.read_text(), args.registry, args.country))
    elif args.cmd == "digest":
        with tenant_tx(tenant_id) as conn:
            print(digest.send(conn, tenant_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
