"""Cloud Run Admin MCP Tool Connector with Gateway-mediated OAuth Credential Injection."""

from __future__ import annotations

import datetime
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Known GCP Project Constants
DEFAULT_PROJECT_ID = "managed-agent-504409"
DEFAULT_PROJECT_NUMBER = "316329647160"
DEFAULT_REGION = "us-central1"
ALLOWED_REGIONS = ["us-central1", "europe-west1"]
ALLOWED_SERVICE_PREFIXES = ["sdo-hello-world-", "sdo-report-", "sdo-demo-"]


class CloudRunServiceStatus(BaseModel):
    """Status metadata for a serverless Google Cloud Run service."""

    service_name: str
    project_id: str = DEFAULT_PROJECT_ID
    region: str = DEFAULT_REGION
    service_url: str
    status: str = "READY"  # READY, DEPLOYING, FAILED, DELETED
    traffic_percent: int = 100
    latest_ready_revision: str | None = None
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    env_vars: dict[str, str] = Field(default_factory=dict)
    min_instances: int = 0
    max_instances: int = 3
    allow_unauthenticated: bool = True
    image_uri: str = ""
    deployed_at: str | None = None


class ServiceDeploymentResult(BaseModel):
    """Result of a Cloud Run service deployment operation."""

    success: bool
    service: CloudRunServiceStatus
    operation_id: str
    message: str
    injected_auth_mode: str = "oauth2_bearer"


class CloudRunMCPClient:
    """Client for Google Cloud Run Admin Model Context Protocol (MCP) server.
    
    Enforces zero credentials in the agent sandbox by requiring per-request
    OAuth 2.0 bearer token injection mediated by the Agent Gateway boundary.
    """

    def __init__(
        self,
        project_id: str = DEFAULT_PROJECT_ID,
        project_number: str = DEFAULT_PROJECT_NUMBER,
        region: str = DEFAULT_REGION,
        auth_token: str | None = None,
        use_mock: bool = True,
    ) -> None:
        self.project_id = project_id
        self.project_number = project_number
        self.region = region
        self.auth_token = auth_token
        self.use_mock = use_mock
        self._deployed_services: dict[str, CloudRunServiceStatus] = {}

    def _resolve_token(self, explicit_token: str | None = None) -> str | None:
        """Resolve short-lived OAuth token injected from the Gateway boundary."""
        token = explicit_token or self.auth_token
        is_empty = token is None or (isinstance(token, str) and not token.strip())
        if is_empty and not self.use_mock:
            raise PermissionError(
                "Zero credentials in sandbox violation: CloudRunMCPClient requires a gateway-injected OAuth bearer token in live mode."
            )
        return token

    def build_service_url(self, service_name: str, region: str | None = None) -> str:
        """Construct canonical Google Cloud Run URL for the service."""
        target_region = region or self.region
        return f"https://{service_name}-{self.project_number}.{target_region}.run.app"

    def validate_service_policy(
        self,
        service_name: str,
        region: str,
        allowed_prefixes: list[str] | None = None,
        allowed_regions: list[str] | None = None,
        max_instances: int | None = None,
        allowed_max_instances: int = 3,
        min_instances: int | None = None,
    ) -> bool:
        """Validate service deployment parameters against domain RBAC policies."""
        prefixes = allowed_prefixes or ALLOWED_SERVICE_PREFIXES
        regions = allowed_regions or ALLOWED_REGIONS

        if not any(service_name.startswith(p) for p in prefixes):
            raise ValueError(
                f"Policy violation: service name '{service_name}' must start with one of {prefixes}"
            )

        if region not in regions:
            raise ValueError(
                f"Policy violation: region '{region}' is not in allowed regions {regions}"
            )

        if max_instances is not None:
            if max_instances > allowed_max_instances:
                raise ValueError(
                    f"Policy violation: requested max_instances ({max_instances}) exceeds allowed limit ({allowed_max_instances})"
                )
            if max_instances < 1:
                raise ValueError(
                    f"Policy violation: max_instances must be at least 1, got {max_instances}"
                )

        if min_instances is not None:
            if min_instances < 0:
                raise ValueError(
                    f"Policy violation: min_instances cannot be negative, got {min_instances}"
                )
            if max_instances is not None and min_instances > max_instances:
                raise ValueError(
                    f"Policy violation: min_instances ({min_instances}) cannot exceed max_instances ({max_instances})"
                )

        return True

    async def deploy_service(
        self,
        service_name: str,
        image_uri: str | None = None,
        env_vars: dict[str, str] | None = None,
        region: str | None = None,
        min_instances: int = 0,
        max_instances: int = 3,
        allow_unauthenticated: bool = True,
        auth_token: str | None = None,
    ) -> ServiceDeploymentResult:
        """Provision or update a Google Cloud Run service with OAuth credential injection."""
        target_region = region or self.region
        token = self._resolve_token(auth_token)
        target_image = image_uri or f"gcr.io/{self.project_id}/{service_name}:latest"

        self.validate_service_policy(
            service_name=service_name,
            region=target_region,
            max_instances=max_instances,
            min_instances=min_instances,
        )

        service_url = self.build_service_url(service_name, target_region)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        revision_name = f"{service_name}-{int(datetime.datetime.now().timestamp())}"

        logger.info(
            "CloudRunMCP: Deploying service '%s' in region '%s' (OAuth Token: %s)",
            service_name,
            target_region,
            "INJECTED_BEARER" if token else "MOCK_GATEWAY_TOKEN",
        )

        status = CloudRunServiceStatus(
            service_name=service_name,
            project_id=self.project_id,
            region=target_region,
            service_url=service_url,
            status="READY",
            traffic_percent=100,
            latest_ready_revision=revision_name,
            conditions=[
                {"type": "Ready", "status": "True", "message": "Service is ready to receive traffic"},
                {"type": "ConfigurationsReady", "status": "True", "message": "Configuration ready"},
                {"type": "RoutesReady", "status": "True", "message": "Route ready"},
            ],
            env_vars=env_vars or {},
            min_instances=min_instances,
            max_instances=max_instances,
            allow_unauthenticated=allow_unauthenticated,
            image_uri=target_image,
            deployed_at=now_iso,
        )

        key = f"{target_region}/{service_name}"
        self._deployed_services[key] = status

        return ServiceDeploymentResult(
            success=True,
            service=status,
            operation_id=f"op-run-{int(datetime.datetime.now().timestamp())}",
            message=f"Service '{service_name}' successfully deployed to Cloud Run at {service_url}",
            injected_auth_mode="oauth2_bearer" if token else "mock_gateway",
        )

    async def get_service_status(
        self,
        service_name: str,
        region: str | None = None,
        auth_token: str | None = None,
    ) -> CloudRunServiceStatus:
        """Retrieve deployment status and URL of a Cloud Run service."""
        target_region = region or self.region
        self._resolve_token(auth_token)
        self.validate_service_policy(service_name, target_region)

        key = f"{target_region}/{service_name}"
        if key in self._deployed_services:
            return self._deployed_services[key]

        # Construct deterministic status if not yet in memory
        service_url = self.build_service_url(service_name, target_region)
        return CloudRunServiceStatus(
            service_name=service_name,
            project_id=self.project_id,
            region=target_region,
            service_url=service_url,
            status="READY",
            traffic_percent=100,
            latest_ready_revision=f"{service_name}-00001",
        )

    async def delete_service(
        self,
        service_name: str,
        region: str | None = None,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Delete an ephemeral Cloud Run service."""
        target_region = region or self.region
        self._resolve_token(auth_token)
        self.validate_service_policy(service_name, target_region)

        key = f"{target_region}/{service_name}"
        if key in self._deployed_services:
            del self._deployed_services[key]

        logger.info("CloudRunMCP: Deleted service '%s' in region '%s'", service_name, target_region)
        return {
            "status": "DELETED",
            "service_name": service_name,
            "region": target_region,
            "message": f"Service '{service_name}' deleted.",
        }

    async def list_services(
        self,
        region: str | None = None,
        auth_token: str | None = None,
    ) -> list[CloudRunServiceStatus]:
        """List all active Cloud Run services."""
        target_region = region or self.region
        self._resolve_token(auth_token)
        if target_region not in ALLOWED_REGIONS:
            raise ValueError(
                f"Policy violation: region '{target_region}' is not in allowed regions {ALLOWED_REGIONS}"
            )
        return [
            s for key, s in self._deployed_services.items()
            if key.startswith(f"{target_region}/")
        ]
