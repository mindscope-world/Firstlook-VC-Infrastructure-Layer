"""Tenant object storage: content-addressed and encrypted with the tenant's key.

Raw source objects are immutable (the audit trail), stored under the tenant's
prefix, and encrypted client-side so isolation doesn't depend on the storage
backend's own encryption. Keys hash the plaintext, so re-ingesting identical
bytes is a no-op.
"""

from __future__ import annotations

from uuid import UUID

import psycopg

from .adapters.storage import ObjectStore, content_key, get_store
from .crypto import TenantCipher, tenant_cipher


class TenantObjects:
    def __init__(
        self,
        conn: psycopg.Connection,
        tenant_id: UUID | str,
        store: ObjectStore | None = None,
        cipher: TenantCipher | None = None,
    ):
        self.tenant_id = str(tenant_id)
        self.store = store or get_store()
        self.cipher = cipher or tenant_cipher(conn, tenant_id)

    def put(
        self, namespace: str, data: bytes, content_type: str = "application/octet-stream", suffix: str = ""
    ) -> str:
        key = content_key(self.tenant_id, namespace, data, suffix)
        uri = self.store.uri_for(key)
        if self.store.exists(uri):
            return uri
        return self.store.put(key, self.cipher.encrypt(data), content_type)

    def get(self, uri: str) -> bytes:
        prefix = f"tenants/{self.tenant_id}/"
        if prefix not in uri:
            raise PermissionError("object belongs to another tenant")
        return self.cipher.decrypt(self.store.get(uri))
