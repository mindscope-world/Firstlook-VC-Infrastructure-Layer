"""Administrative commands.

    uv run python -m firstlook_core.admin add-user --email you@fund.vc --name "Your Name"
        [--role admin] [--tenant savanna] [--tenant-name "Savanna Ventures"]

Adds a user to a tenant (creating the tenant if the slug doesn't exist), so
they can sign in: with dev login locally, or with SSO once their email and the
tenant's WorkOS organization are set up.
"""

from __future__ import annotations

import argparse
import sys

from .db import system_tx, tenant_tx
from .tenants import create_tenant, create_user

ROLES = ("admin", "partner", "associate", "platform", "finance", "viewer")


def add_user(email: str, name: str, role: str, tenant_slug: str, tenant_name: str | None) -> str:
    email = email.strip().lower()
    with system_tx() as conn:
        tenant = conn.execute("SELECT id, name FROM tenants WHERE slug = %s", (tenant_slug,)).fetchone()
        if tenant:
            existing = conn.execute(
                "SELECT role::text AS role FROM users WHERE tenant_id = %s AND email = %s",
                (tenant["id"], email),
            ).fetchone()
            if existing:
                return f"{email} already exists in {tenant['name']} as {existing['role']}."
    if tenant is None:
        tenant_label = tenant_name or tenant_slug.replace("-", " ").title()
        with tenant_tx("00000000-0000-0000-0000-000000000000") as conn:
            tenant_id = create_tenant(conn, tenant_label, tenant_slug)
        created_tenant = True
    else:
        tenant_id, tenant_label, created_tenant = tenant["id"], tenant["name"], False
    with tenant_tx(tenant_id) as conn:
        create_user(conn, tenant_id, email, name, role)
    note = f" (new tenant '{tenant_slug}')" if created_tenant else ""
    return f"Added {name} <{email}> to {tenant_label}{note} as {role}."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firstlook-admin")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add-user", help="add a user who can sign in")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", default="admin", choices=ROLES)
    p.add_argument("--tenant", default="savanna", help="tenant slug (created if missing)")
    p.add_argument("--tenant-name", help="display name when creating a new tenant")
    args = parser.parse_args(argv)
    if "@" not in args.email:
        parser.error("--email must be an email address")
    print(add_user(args.email, args.name, args.role, args.tenant, args.tenant_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
