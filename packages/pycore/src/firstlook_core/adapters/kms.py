"""Key management: wrap and unwrap per-tenant data encryption keys.

Envelope encryption: each tenant has a random 256-bit data key (DEK). The DEK
is stored only in wrapped form (tenants.wrapped_dek); the KMS holds the key
that wraps it. Cloud KMS implementations replace LocalKms in Phase 4.
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings


class Kms(Protocol):
    key_ref: str

    def wrap(self, plaintext_key: bytes, context: bytes) -> bytes: ...

    def unwrap(self, wrapped_key: bytes, context: bytes) -> bytes: ...


class LocalKms:
    """AES-256-GCM key wrapping with a master key from the environment.

    context (the tenant id) is bound as associated data, so a wrapped key
    copied onto another tenant's row fails to unwrap.
    """

    key_ref = "local:v1"

    def __init__(self, master_key: bytes):
        if len(master_key) != 32:
            raise ValueError("local master key must be 32 bytes")
        self._aead = AESGCM(master_key)

    def wrap(self, plaintext_key: bytes, context: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._aead.encrypt(nonce, plaintext_key, context)

    def unwrap(self, wrapped_key: bytes, context: bytes) -> bytes:
        return self._aead.decrypt(wrapped_key[:12], wrapped_key[12:], context)


@lru_cache
def get_kms() -> Kms:
    settings = get_settings()
    if settings.kms_backend == "local":
        return LocalKms(base64.b64decode(settings.local_master_key))
    raise ValueError(f"unknown KMS backend {settings.kms_backend!r}")
