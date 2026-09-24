"""Service configuration, read from the environment (12-factor).

Every setting has a local-development default that matches compose/, so a
fresh checkout runs with no .env at all.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    env: str = "local"

    # Postgres: services connect as the RLS-bound app role; migrations and
    # cross-tenant jobs use the owner/system roles.
    database_url: str = "postgresql://firstlook_app:firstlook_app@localhost:15432/firstlook"
    database_owner_url: str = "postgresql://firstlook:firstlook@localhost:15432/firstlook"
    database_system_url: str = "postgresql://firstlook_system:firstlook_system@localhost:15432/firstlook"

    # Object storage: "local" (filesystem) or "s3" (SeaweedFS locally, any S3 later).
    storage_backend: str = "s3"
    storage_local_root: Path = REPO_ROOT / ".data" / "objects"
    s3_endpoint: str | None = "http://localhost:18333"
    s3_access_key: str = "firstlook"
    s3_secret_key: str = "firstlook-secret"
    s3_region: str = "us-east-1"
    s3_bucket: str = "firstlook-raw"

    # Event bus: "memory" or "kafka" (Redpanda locally).
    bus_backend: str = "kafka"
    kafka_bootstrap: str = "localhost:19092"

    # KMS: "local" wraps tenant data keys with LOCAL_MASTER_KEY (base64, 32 bytes).
    kms_backend: str = "local"
    local_master_key: str = "Zmlyc3Rsb29rLWxvY2FsLWRldi1tYXN0ZXIta2V5ISE="

    # Auth: session JWTs are issued by services/api and verified everywhere.
    session_secret: str = "local-dev-session-secret-change-me"
    internal_service_token: str = "local-dev-internal-token"

    # LLM gateway (services/gateway).
    gateway_url: str = "http://localhost:14300"

    temporal_address: str = "localhost:17233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "firstlook"

    smtp_host: str = "localhost"
    smtp_port: int = 11025

    # Public URLs used for OAuth redirects.
    web_url: str = "http://localhost:13000"
    ingest_public_url: str = "http://localhost:13000/api/ingest"

    # OAuth apps (test mode during development, see docs/connectors.md).
    google_client_id: str | None = None
    google_client_secret: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_tenant: str = "common"
    zoom_client_id: str | None = None
    zoom_client_secret: str | None = None
    slack_client_id: str | None = None
    slack_client_secret: str | None = None
    slack_signing_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
