"""Session tokens shared by every service.

services/api issues a short-lived HS256 JWT after login (WorkOS or dev
login); Python services verify it. Service-to-service calls use a separate
internal token plus an explicit tenant header.
"""

from __future__ import annotations

import hmac
import time
from dataclasses import dataclass
from uuid import UUID

import jwt

from .config import get_settings

ISSUER = "firstlook"


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    role: str
    email: str


def issue_session(p: Principal, ttl_seconds: int = 12 * 3600) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": str(p.user_id),
        "tid": str(p.tenant_id),
        "role": p.role,
        "email": p.email,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, get_settings().session_secret, algorithm="HS256")


def verify_session(token: str) -> Principal:
    claims = jwt.decode(
        token,
        get_settings().session_secret,
        algorithms=["HS256"],
        issuer=ISSUER,
        options={"require": ["exp", "sub", "tid", "role"]},
    )
    return Principal(UUID(claims["sub"]), UUID(claims["tid"]), claims["role"], claims.get("email", ""))


def verify_internal_token(token: str | None) -> bool:
    return token is not None and hmac.compare_digest(token, get_settings().internal_service_token)
