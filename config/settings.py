"""Application settings and configuration management for SDO ADK Platform."""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Master application configuration backed by environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Target GCP Project & Region
    project_id: str = "managed-agent-504409"
    region: str = "global"
    vertex_location: str = "us-central1"

    # Core LLM Reasoning Model
    model_name: str = "gemini-3.7-flash"
    max_output_tokens: int = 8192
    temperature: float = 0.2

    # Storage & Compliance
    gcs_worm_bucket: str = "sdo-worm-audit-managed-agent-504409"
    kms_keyring: str = "sdo-keyring"
    kms_key_location: str = "global"
    kms_crypto_key: str = "sdo-gdpr-shredding-key"

    # BigQuery Data & Analytics
    bq_dataset: str = "sdo_finance_demo"
    bq_analytics_dataset: str = "sdo_analytics"

    # Ingress & Authentication
    auth_mode: Literal["oidc", "local"] = "local"
    google_workspace_domain: str = "wallbox.com"
    jwt_audience: str = "sdo-control-plane"

    # GitHub VCS Integration
    github_token: str | None = None
    github_owner: str = "wallbox"
    github_repo: str = "sdo-deliverables"
    use_mock_vcs: bool = True

    # Deterministic FSM Constraints
    max_retries_per_node: int = 3
    day30_watch_delay_seconds: int = 2592000  # 30 days in seconds


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for cached Settings instance."""
    return Settings()
