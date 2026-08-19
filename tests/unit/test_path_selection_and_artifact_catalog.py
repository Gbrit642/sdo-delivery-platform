"""Unit tests for Delivery Path Selection & GCS/BigQuery Artifact Cataloging."""

import pytest
from httpx import ASGITransport, AsyncClient
from agents.tradeoff_evaluator import TradeoffEvaluator, TradeoffComparison
from storage.artifact_catalog import ArtifactCatalogManager, get_artifact_catalog
from web.app import app


@pytest.mark.asyncio
async def test_tradeoff_evaluator_recommends_direct_connector_for_reporting():
    """Verify that pure analytical/reporting briefs recommend Direct Connector Automation."""
    brief = "Create a weekly currency variance analysis view comparing EUR invoices with USD receipts in BigQuery."
    tradeoff = TradeoffEvaluator.evaluate_brief(brief, domain="finance")

    assert isinstance(tradeoff, TradeoffComparison)
    assert tradeoff.recommended_path == "direct_connector_automation"
    assert "Direct Connector Automation" in tradeoff.direct_connector_option.title
    assert len(tradeoff.direct_connector_option.pros) >= 3
    assert len(tradeoff.direct_connector_option.cons) >= 1
    assert "< 5 seconds" in tradeoff.direct_connector_option.estimated_speed
    assert "Gate H1" in tradeoff.direct_connector_option.governance_model
    assert "Gate H2" in tradeoff.direct_connector_option.governance_model


@pytest.mark.asyncio
async def test_tradeoff_evaluator_recommends_multi_agent_for_custom_software():
    """Verify that briefs requiring custom code or APIs recommend Autonomous Multi-Agent Software Development."""
    brief = "Build a custom Python microservice with API webhook to decode OCPP 1.6J charge-point error frames."
    tradeoff = TradeoffEvaluator.evaluate_brief(brief, domain="firmware")

    assert isinstance(tradeoff, TradeoffComparison)
    assert tradeoff.recommended_path == "multi_agent_software_dev"
    assert "Autonomous Multi-Agent" in tradeoff.multi_agent_option.title
    assert len(tradeoff.multi_agent_option.pros) >= 4
    assert "Linux sandbox" in tradeoff.multi_agent_option.summary
    assert "Gate H1" in tradeoff.multi_agent_option.governance_model
    assert "Gate H2" in tradeoff.multi_agent_option.governance_model


@pytest.mark.asyncio
async def test_artifact_catalog_gcs_hierarchy_and_bigquery_indexing():
    """Verify GCS partitioned storage paths and BigQuery artifact catalog indexing."""
    catalog = ArtifactCatalogManager(bucket_name="sdo-test-artifacts", dataset_id="sdo_analytics")

    rec1 = await catalog.store_and_catalog_artifact(
        domain="finance",
        loop_id="01KZZTEST001",
        artifact_name="spec.md",
        artifact_type="SPECIFICATION",
        content="# Feature: FX Variance Analysis\nGiven exchange rates...",
        created_by="sarah.controller@wallbox.com",
    )

    assert rec1.gcs_uri == "gs://sdo-test-artifacts/processes/finance/01KZZTEST001/spec.md"
    assert rec1.artifact_type == "SPECIFICATION"
    assert len(rec1.content_sha256) == 64
    assert rec1.size_bytes > 0

    rec2 = await catalog.store_and_catalog_artifact(
        domain="finance",
        loop_id="01KZZTEST001",
        artifact_name="fx_variance_view.sql",
        artifact_type="SQL_VIEW",
        content="CREATE OR REPLACE VIEW `sdo_finance_demo.fx_variance` AS SELECT 1;",
        created_by="sdo-engine",
    )

    assert rec2.gcs_uri == "gs://sdo-test-artifacts/processes/finance/01KZZTEST001/fx_variance_view.sql"

    # Query by loop_id
    loop_artifacts = await catalog.list_artifacts_for_loop("01KZZTEST001")
    assert len(loop_artifacts) == 2
    assert {a.artifact_name for a in loop_artifacts} == {"spec.md", "fx_variance_view.sql"}

    # Query all artifacts by domain
    all_finance = await catalog.list_all_artifacts(domain="finance")
    assert len(all_finance) >= 2


@pytest.mark.asyncio
async def test_api_tradeoff_and_artifact_endpoints():
    """Verify REST API trade-off evaluation and artifact catalog query endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Evaluate Trade-Offs
        tradeoff_resp = await client.post(
            "/api/v1/tradeoffs/evaluate",
            json={
                "node_id": "sales",
                "brief_text": "Create a monthly pipeline conversion report aggregating CRM opportunities.",
            },
        )
        assert tradeoff_resp.status_code == 200
        tradeoff_data = tradeoff_resp.json()
        assert "recommended_path" in tradeoff_data
        assert "direct_connector_option" in tradeoff_data
        assert "multi_agent_option" in tradeoff_data

        # 2. Create loop and confirm artifacts cataloged
        create_resp = await client.post(
            "/api/v1/loops",
            json={
                "node_id": "finance",
                "brief_text": "Create currency variance view in BigQuery.",
                "owner_email": "sarah.controller@wallbox.com",
                "delivery_path": "direct_connector_automation",
            },
        )
        assert create_resp.status_code == 201
        loop_data = create_resp.json()
        loop_id = loop_data["loop_id"]
        assert loop_data["delivery_path"] == "direct_connector_automation"
        assert "tradeoff_analysis" in loop_data
        assert "SPECIFICATION" in loop_data.get("gcs_artifact_uris", {})

        # 3. Query artifacts for the created loop
        artifacts_resp = await client.get(f"/api/v1/loops/{loop_id}/artifacts")
        assert artifacts_resp.status_code == 200
        artifacts = artifacts_resp.json()
        assert len(artifacts) >= 1
        assert artifacts[0]["artifact_name"] == "spec.md"
        assert "gs://" in artifacts[0]["gcs_uri"]
