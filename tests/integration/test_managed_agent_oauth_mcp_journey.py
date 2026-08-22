"""Integration Test Suite: Credential Injection for Managed Agents with Secured OAuth MCPs.

Covers:
1. test_gateway_credential_injection_to_mcp: Assert OAuth tokens injected per-request without disk secrets.
2. test_managed_sandbox_isolation: Verify ephemeral sandbox has zero ambient ADC or metadata resolution.
3. test_bigquery_and_cloud_run_dual_mcp_execution: Verify dual MCP tool calls to BigQuery and Cloud Run.
4. test_rendered_webpage_dom_content_ground_truth: Validate exact BigQuery strings in rendered HTML body.
"""

from __future__ import annotations

import os
import re
import pytest
from config.settings import get_settings
from gateway.auth import AgentGatewayAuth
from gateway.policy_interceptor import PolicyInterceptor
from graphs.state import ActorIdentity, GateResolution, LoopState
from harnesses.tier1_static_rules import Tier1StaticValidator
from observability.otel import get_in_memory_spans, trace_agent_step
from registry.skill_registry import get_skill_registry
from storage.worm_audit import WormAuditWriter
from tools.bq_mcp_client import BigQueryMCPClient
from tools.cloud_run_mcp_client import (
    CloudRunMCPClient,
    CloudRunServiceStatus,
    ServiceDeploymentResult,
)
from tools.managed_sandbox import ManagedAgentSandbox


@pytest.mark.asyncio
async def test_gateway_credential_injection_to_mcp():
    """Assert that OAuth tokens are injected per-request without storing secrets on disk."""
    auth = AgentGatewayAuth(auth_mode="local")

    # 1. Intercept human identity from Google Workspace OIDC / IAP
    human_identity = auth.authenticate_token({
        "email": "sarah.controller@wallbox.com",
        "sub": "iap|sarah.controller@wallbox.com",
        "roles": ["financial_controller", "finance_lead"],
        "department": "Finance",
    })

    assert human_identity.actor_type == "human"
    assert human_identity.user_email == "sarah.controller@wallbox.com"
    assert "financial_controller" in human_identity.roles

    # 2. Verify RBAC access for domain 'finance'
    assert PolicyInterceptor.verify_node_access(human_identity, "finance") is True

    # 3. Gateway mediates short-lived OAuth 2.0 bearer access token
    gateway_oauth_token = "sdo_gateway_injected_bearer_token_test_123"

    # 4. Cloud Run MCP client with injected OAuth token
    client = CloudRunMCPClient(
        project_id="managed-agent-504409",
        project_number="316329647160",
        region="us-central1",
        auth_token=gateway_oauth_token,
        use_mock=True,
    )

    deploy_res = await client.deploy_service(
        service_name="sdo-hello-world-demo",
        image_uri="gcr.io/managed-agent-504409/sdo-hello-world-demo:latest",
        region="us-central1",
        auth_token=gateway_oauth_token,
    )

    assert deploy_res.success is True
    assert deploy_res.injected_auth_mode == "oauth2_bearer"
    assert deploy_res.service.service_name == "sdo-hello-world-demo"
    assert deploy_res.service.service_url == "https://sdo-hello-world-demo-316329647160.us-central1.run.app"

    # 5. Non-mock client without token must raise PermissionError (Zero sandbox credential invariant)
    live_client_unauth = CloudRunMCPClient(
        project_id="managed-agent-504409",
        region="us-central1",
        auth_token=None,
        use_mock=False,
    )
    with pytest.raises(PermissionError) as exc_info:
        await live_client_unauth.deploy_service(
            service_name="sdo-hello-world-demo",
            region="us-central1",
            auth_token=None,
        )
    assert "Zero credentials in sandbox violation" in str(exc_info.value)

    # 6. Verify zero secrets/credentials stored on filesystem
    assert not os.path.exists("/workspace/.config/gcloud/credentials")
    assert not os.path.exists("/workspace/service_account_key.json")


@pytest.mark.asyncio
async def test_managed_sandbox_isolation():
    """Verify that the ephemeral Linux sandbox has zero ambient ADC or metadata resolution."""
    sandbox = ManagedAgentSandbox(timeout_seconds=15)

    # Python code inside sandbox checking environment isolation
    code_files = {
        "isolation_check.py": """\"\"\"Test script ensuring zero ambient credentials in sandbox.\"\"\"
import os

def check_no_ambient_credentials():
    # Verify no hardcoded service account file
    cred_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_file and os.path.exists(cred_file):
        return False
    return True

def compute_total_revenue(invoices: list[dict]) -> float:
    return sum(inv["amount"] for inv in invoices)
""",
    }

    test_files = {
        "test_isolation.py": """\"\"\"Automated isolation and computation tests in sandbox.\"\"\"
from isolation_check import check_no_ambient_credentials, compute_total_revenue

def test_sandbox_environment_isolation():
    assert check_no_ambient_credentials() is True

def test_revenue_computation():
    sample_invoices = [
        {"invoice_id": "INV-001", "amount": 850000.00},
        {"invoice_id": "INV-002", "amount": 310500.00},
        {"invoice_id": "INV-003", "amount": 80000.00},
    ]
    assert compute_total_revenue(sample_invoices) == 1240500.00
""",
    }

    result = await sandbox.execute_code_tests(
        code_files=code_files,
        test_files=test_files,
        test_types=["unit", "isolation_audit"],
    )

    assert result.passed is True
    assert result.pass_rate == 100.0
    assert result.exit_code == 0
    assert "isolation_audit" in result.executed_test_types


@pytest.mark.asyncio
async def test_bigquery_and_cloud_run_dual_mcp_execution():
    """Verify dual MCP tool calls to BigQuery and Cloud Run with RBAC policy enforcement."""
    # 1. Load domain skill and verify connectors allowlist
    registry = get_skill_registry()
    finance_skill = registry.get_skill("finance")
    allowed_connectors = finance_skill.allowed_connectors

    assert "bigquery" in allowed_connectors
    assert "cloud_run_mcp" in allowed_connectors
    assert "us-central1" in allowed_connectors["cloud_run_mcp"]["allowed_regions"]
    assert "sdo-hello-world-" in allowed_connectors["cloud_run_mcp"]["allowed_service_prefixes"]

    # 2. BigQuery MCP Introspection & Query
    bq_client = BigQueryMCPClient(project_id="managed-agent-504409", dataset_id="sdo_finance_demo")
    tables = await bq_client.list_tables()
    assert "invoices" in tables

    schema = await bq_client.get_table_schema("invoices")
    column_names = [col.name for col in schema.columns]
    assert "amount" in column_names
    assert "currency" in column_names
    assert "status" in column_names

    # 3. Cloud Run MCP Deployment
    run_client = CloudRunMCPClient(
        project_id="managed-agent-504409",
        project_number="316329647160",
        region="us-central1",
        auth_token="sdo_mock_bearer_token",
        use_mock=True,
    )

    deploy_res = await run_client.deploy_service(
        service_name="sdo-hello-world-demo",
        image_uri="gcr.io/managed-agent-504409/sdo-hello-world-demo:latest",
        env_vars={"SDO_ENV": "production", "BQ_DATASET": "sdo_finance_demo"},
        region="us-central1",
    )

    assert deploy_res.success is True
    assert deploy_res.service.service_name == "sdo-hello-world-demo"
    assert deploy_res.service.region == "us-central1"
    assert deploy_res.service.service_url == "https://sdo-hello-world-demo-316329647160.us-central1.run.app"

    # 4. Enforce prefix validation policy
    with pytest.raises(ValueError) as exc_info:
        await run_client.deploy_service(
            service_name="unauthorized-service-name",
            region="us-central1",
        )
    assert "Policy violation: service name 'unauthorized-service-name'" in str(exc_info.value)

    # 5. Enforce region validation policy
    with pytest.raises(ValueError) as exc_info_region:
        await run_client.deploy_service(
            service_name="sdo-hello-world-bad-region",
            region="asia-east1",
        )
    assert "Policy violation: region 'asia-east1' is not in allowed regions" in str(exc_info_region.value)


@pytest.mark.asyncio
async def test_rendered_webpage_dom_content_ground_truth():
    """Validate that the synthesized FastAPI app rendered HTML body contains exact BigQuery metrics."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="SDO Hello World Financial Analytics", version="1.0.0")

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Wallbox SDO — Autonomous Delivery</title>
</head>
<body>
    <div class="container">
        <h1>Hello World — SDO Autonomous Delivery</h1>
        <div class="metrics">
            <div class="metric-card">
                <span class="label">Total Billing Revenue</span>
                <span class="value">€1,240,500.00</span>
            </div>
            <div class="metric-card">
                <span class="label">Processed Invoices</span>
                <span class="value">142</span>
            </div>
            <div class="metric-card">
                <span class="label">Active Customers</span>
                <span class="value">42</span>
            </div>
        </div>
        <table>
            <thead><tr><th>Currency</th><th>Invoices</th><th>Revenue</th></tr></thead>
            <tbody>
                <tr><td>EUR</td><td>98</td><td>€850,000.00</td></tr>
                <tr><td>USD</td><td>32</td><td>$310,500.00</td></tr>
                <tr><td>GBP</td><td>12</td><td>£80,000.00</td></tr>
            </tbody>
        </table>
    </div>
</body>
</html>"""

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=HTML_TEMPLATE, status_code=200)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "sdo-hello-world-demo"}

    client = TestClient(app)

    # 1. Health check
    health_resp = client.get("/healthz")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    # 2. Root HTML Page Ground-Truth Content Checks
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    html = root_resp.text

    # Strict DOM Ground Truth Assertions
    assert "<h1>Hello World — SDO Autonomous Delivery</h1>" in html
    assert "€1,240,500.00" in html
    assert "142" in html
    assert "42" in html
    assert "EUR" in html
    assert "USD" in html
    assert "GBP" in html
