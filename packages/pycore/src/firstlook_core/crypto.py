"""Per-tenant envelope encryption for secrets and sensitive fields."""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID

import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .adapters.kms import Kms, get_kms

_VERSION = b"\x01"


class TenantCipher:
    def __init__(self, tenant_id: UUID | str, dek: bytes):
        self.tenant_id = str(tenant_id)
        self._aead = AESGCM(dek)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        return _VERSION + nonce + self._aead.encrypt(nonce, plaintext, self.tenant_id.encode())

    def decrypt(self, blob: bytes) -> bytes:
        if blob[:1] != _VERSION:
            raise ValueError("unknown ciphertext version")
        return self._aead.decrypt(blob[1:13], blob[13:], self.tenant_id.encode())

    def encrypt_json(self, value: Any) -> bytes:
        return self.encrypt(json.dumps(value).encode())

    def decrypt_json(self, blob: bytes) -> Any:
        return json.loads(self.decrypt(blob))


def new_wrapped_dek(tenant_id: UUID | str, kms: Kms | None = None) -> tuple[bytes, str]:
    kms = kms or get_kms()
    return kms.wrap(AESGCM.generate_key(256), str(tenant_id).encode()), kms.key_ref


def tenant_cipher(conn: psycopg.Connection, tenant_id: UUID | str, kms: Kms | None = None) -> TenantCipher:
    """Load and unwrap the tenant's data key. conn must be scoped to the tenant."""
    row = conn.execute("SELECT wrapped_dek FROM tenants WHERE id = %s", (str(tenant_id),)).fetchone()
    if row is None or row["wrapped_dek"] is None:
        raise LookupError(f"tenant {tenant_id} has no data key")
    kms = kms or get_kms()
    return TenantCipher(tenant_id, kms.unwrap(bytes(row["wrapped_dek"]), str(tenant_id).encode()))


def seal(conn: psycopg.Connection, tenant_id: UUID | str, value: Any) -> str:
    """Encrypt a JSON value with the tenant key as a base64 string, e.g. so
    credentials never appear in plaintext in workflow history."""
    import base64

    return base64.b64encode(tenant_cipher(conn, tenant_id).encrypt_json(value)).decode()


def unseal(conn: psycopg.Connection, tenant_id: UUID | str, sealed: str) -> Any:
    import base64

    return tenant_cipher(conn, tenant_id).decrypt_json(base64.b64decode(sealed))
