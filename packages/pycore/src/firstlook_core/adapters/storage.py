"""Object storage for raw, immutable source objects (emails, files, exports)."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from ..config import get_settings


class ObjectStore(Protocol):
    scheme: str

    def uri_for(self, key: str) -> str: ...

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store bytes and return a URI for them."""
        ...

    def get(self, uri: str) -> bytes: ...

    def exists(self, uri: str) -> bool: ...


def content_key(tenant_id: str, namespace: str, data: bytes, suffix: str = "") -> str:
    """Content-addressed key under the tenant's prefix: re-ingesting identical
    bytes is idempotent and raw objects are never overwritten."""
    digest = hashlib.sha256(data).hexdigest()
    return f"tenants/{tenant_id}/{namespace}/{digest[:2]}/{digest}{suffix}"


class LocalFsStore:
    scheme = "file"

    def __init__(self, root: Path):
        self.root = root

    def uri_for(self, key: str) -> str:
        return f"file://{key}"

    def _path(self, uri_or_key: str) -> Path:
        key = uri_or_key.removeprefix("file://")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("key escapes storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return self.uri_for(key)

    def get(self, uri: str) -> bytes:
        return self._path(uri).read_bytes()

    def exists(self, uri: str) -> bool:
        return self._path(uri).exists()


class S3Store:
    scheme = "s3"

    def __init__(self, bucket: str, endpoint: str | None, access_key: str, secret_key: str, region: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 5}),
        )
        self._bucket_ready = False

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        from botocore.exceptions import ClientError

        try:
            self._s3.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._s3.create_bucket(Bucket=self.bucket)
        self._bucket_ready = True

    def uri_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def _split(self, uri: str) -> tuple[str, str]:
        rest = uri.removeprefix("s3://")
        bucket, _, key = rest.partition("/")
        return bucket, key

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._ensure_bucket()
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return self.uri_for(key)

    def get(self, uri: str) -> bytes:
        bucket, key = self._split(uri)
        return self._s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    def exists(self, uri: str) -> bool:
        from botocore.exceptions import ClientError

        bucket, key = self._split(uri)
        try:
            self._s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False


@lru_cache
def get_store() -> ObjectStore:
    s = get_settings()
    if s.storage_backend == "local":
        return LocalFsStore(s.storage_local_root)
    if s.storage_backend == "s3":
        return S3Store(s.s3_bucket, s.s3_endpoint, s.s3_access_key, s.s3_secret_key, s.s3_region)
    raise ValueError(f"unknown storage backend {s.storage_backend!r}")
