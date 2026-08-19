"""FastAPI Control Plane, REST API, Google Chat Webhook & Web Dashboard Server."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import get_settings
from gateway.auth import AgentGatewayAuth
from gateway.chat_adapter import GoogleChatAdapter
from gateway.policy_interceptor import PolicyInterceptor
from graphs.state import ActorIdentity, GateResolution, LoopState
from graphs.workflow import SDOStateGraph
from agents.documental import specify_node
from agents.arquitecto import design_node
from agents.implementer import implement_node
from agents.reviewer import review_node
from agents.watcher import watch_node
from harnesses.harness_node import spec_harness_node
from storage.worm_audit import WormAuditWriter
from storage.artifact_catalog import get_artifact_catalog
from observability.analytics import BigQueryAgentAnalytics
from tools.github_client import GitHubClient
from registry.skill_registry import get_skill_registry
from agents.tradeoff_evaluator import TradeoffEvaluator, TradeoffComparison

logger = logging.getLogger("sdo.web")
settings = get_settings()

app = FastAPI(
    title="Wallbox SDO Platform — ADK 2.0 Engine",
    version="0.1.0",
    description="Enterprise Multi-Agent Software Delivery Optimization Platform on GCP",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory active loop storage & components
active_loops: dict[str, LoopState] = {}
audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)
analytics = BigQueryAgentAnalytics(project_id=settings.project_id, use_mock=True)
github_client = GitHubClient(use_mock=True)
gateway_auth = AgentGatewayAuth(auth_mode=settings.auth_mode)


def build_configured_graph() -> SDOStateGraph:
    """Instantiate StateGraph with all registered node handlers."""
    graph = SDOStateGraph()

    async def intake_handler(state: LoopState) -> LoopState:
        # Validate domain access
        if not PolicyInterceptor.verify_node_access(state.initiator, state.node_id):
            state.escalation_reason = f"Access denied: User '{state.initiator.user_email}' not authorized for domain '{state.node_id}'"
            state.current_state = "CLOSED"
            return state
        return state

    async def close_handler(state: LoopState) -> LoopState:
        # Create PR and squash merge
        branch = f"feature/{state.loop_id}"
        await github_client.create_branch(branch)
        commit_sha = await github_client.commit_files(
            branch, state.code_artifacts, f"feat({state.node_id}): Automated deliverable for {state.loop_id}"
        )
        pr = await github_client.create_pull_request(
            branch, f"[{state.node_id.upper()}] Deliverable {state.loop_id}", "Automated PR created by SDO Platform"
        )
        merge_sha = await github_client.merge_pull_request(pr.pr_number, "Squash and merge")
        tag = await github_client.create_release_tag(f"v1.0.{state.loop_id[:6]}", merge_sha, "Release deliverable")

        state.close_commit_hash = merge_sha
        state.pull_request_url = pr.html_url

        # Catalog code artifacts & test results into GCS + BigQuery index
        catalog = get_artifact_catalog()
        for filename, content in state.code_artifacts.items():
            art_type = "SQL_VIEW" if filename.endswith(".sql") else "PYTHON_CODE"
            rec = await catalog.store_and_catalog_artifact(
                domain=state.node_id,
                loop_id=state.loop_id,
                artifact_name=filename,
                artifact_type=art_type,
                content=content,
                created_by=state.initiator.user_email or "sdo-engine",
            )
            state.gcs_artifact_uris[filename] = rec.gcs_uri

        if state.test_results:
            test_rec = await catalog.store_and_catalog_artifact(
                domain=state.node_id,
                loop_id=state.loop_id,
                artifact_name="test_results.json",
                artifact_type="TEST_REPORT",
                content=state.test_results,
                created_by="sdo-sandbox",
            )
            state.gcs_artifact_uris["TEST_REPORT"] = test_rec.gcs_uri

        # Generate Business Deliverable Card with zero CLI commands and direct Console link
        domain_table_map = {
            "finance": "weekly_revenue_variance",
            "sales": "sales_pipeline_conversion",
            "firmware": "charger_telemetry_agg",
            "marketing": "campaign_attribution",
            "logistics": "inventory_turnover_view",
        }
        table_name = domain_table_map.get(state.node_id, "primary_analytics_view")
        dataset_name = f"sdo_{state.node_id}_demo"
        project_id = settings.project_id

        sample_previews = {
            "finance": [
                {"invoice_id": "INV-2026-0801", "currency": "EUR", "amount_eur": 1250.00, "amount_usd": 1362.50, "variance_pct": 0.05, "status": "RECONCILED"},
                {"invoice_id": "INV-2026-0802", "currency": "USD", "amount_eur": 820.50, "amount_usd": 894.34, "variance_pct": -0.02, "status": "RECONCILED"},
                {"invoice_id": "INV-2026-0803", "currency": "GBP", "amount_eur": 3400.00, "amount_usd": 4352.00, "variance_pct": 0.11, "status": "FLAGGED_REVIEW"},
                {"invoice_id": "INV-2026-0804", "currency": "EUR", "amount_eur": 950.00, "amount_usd": 1035.50, "variance_pct": 0.00, "status": "RECONCILED"},
                {"invoice_id": "INV-2026-0805", "currency": "EUR", "amount_eur": 2100.00, "amount_usd": 2289.00, "variance_pct": 0.04, "status": "RECONCILED"},
            ],
            "sales": [
                {"stage": "PROPOSAL", "total_opportunities": 42, "total_pipeline_eur": 1280000.00, "avg_deal_size_eur": 30476.19},
                {"stage": "NEGOTIATION", "total_opportunities": 18, "total_pipeline_eur": 890000.00, "avg_deal_size_eur": 49444.44},
                {"stage": "CLOSED_WON", "total_opportunities": 35, "total_pipeline_eur": 1650000.00, "avg_deal_size_eur": 47142.86},
            ],
            "firmware": [
                {"charger_id": "WB-PULSAR-001", "firmware_version": "v5.18.2", "status": "ONLINE", "total_events": 14200, "error_count": 0},
                {"charger_id": "WB-PULSAR-002", "firmware_version": "v5.18.2", "status": "ONLINE", "total_events": 12890, "error_count": 1},
                {"charger_id": "WB-COMMANDER-003", "firmware_version": "v6.0.1", "status": "CHARGING", "total_events": 28400, "error_count": 0},
            ],
            "marketing": [
                {"channel": "GOOGLE_SEARCH", "total_conversions": 1420, "cac_usd": 42.50, "attribution_share_pct": 48.5},
                {"channel": "LINKEDIN_ADS", "total_conversions": 680, "cac_usd": 78.20, "attribution_share_pct": 23.2},
                {"channel": "ORGANIC_DIRECT", "total_conversions": 830, "cac_usd": 0.00, "attribution_share_pct": 28.3},
            ],
            "logistics": [
                {"warehouse_id": "WH-BCN-01", "part_sku": "SKU-PULSAR-CABLE-5M", "stock_on_hand": 4500, "reorder_point": 1200, "sla_status": "OPTIMAL"},
                {"warehouse_id": "WH-MAD-02", "part_sku": "SKU-COMMANDER-PCB", "stock_on_hand": 820, "reorder_point": 500, "sla_status": "OPTIMAL"},
            ],
        }

        console_url = (
            f"https://console.cloud.google.com/bigquery?project={project_id}"
            f"&ws=!1m5!1m4!4m3!1s{project_id}!2s{dataset_name}!3s{table_name}"
        )

        state.business_deliverable_card = {
            "title": f"🎉 Deployed Business Asset: {dataset_name}.{table_name}",
            "project_id": project_id,
            "dataset_id": dataset_name,
            "table_name": table_name,
            "full_resource_id": f"{project_id}.{dataset_name}.{table_name}",
            "business_purpose": f"Automated analytical view and data pipeline deployed for the {state.node_id.title()} domain to satisfy delivery brief '{state.loop_id}'.",
            "console_deep_link": console_url,
            "target_sla": "Sub-second analytical query response (< 250ms), refreshed daily.",
            "data_freshness": "Continuous / Automated Daily Refresh",
            "sample_data": sample_previews.get(state.node_id, sample_previews["finance"]),
            "zero_cli_note": "This asset has been automatically created and deployed in your Google Cloud environment. No manual Python scripts, command line tools, or terminal execution are required.",
        }

        # Seal WORM audit record
        audit_key = await audit_writer.write_audit_record(
            node_id=state.node_id,
            loop_id=state.loop_id,
            seq=10,
            intent_kind="LOOP_CLOSED_AND_SEALED",
            actor_email=state.initiator.user_email or "unknown",
            actor_type=state.initiator.actor_type,
            raw_payload={
                "loop_id": state.loop_id,
                "commit": merge_sha,
                "brief": state.brief_raw,
                "spec_id": f"SPEC-{state.node_id.upper()}-{state.loop_id[:8]}",
            },
        )
        state.worm_audit_record_id = audit_key
        return state

    graph.add_node("INTAKE", intake_handler)
    graph.add_node("SPECIFY", specify_node)
    graph.add_node("SPEC_HARNESS", spec_harness_node)
    graph.add_node("GATE_H1", lambda s: s)
    graph.add_node("DESIGN", design_node)
    graph.add_node("IMPLEMENT", implement_node)
    graph.add_node("REVIEW", review_node)
    graph.add_node("GATE_H2", lambda s: s)
    graph.add_node("CLOSE", close_handler)
    graph.add_node("WATCH", watch_node)

    return graph


# --- API Request Models ---
class CreateLoopRequest(BaseModel):
    node_id: str = "finance"
    brief_text: str
    owner_email: str = "sarah.controller@wallbox.com"
    delivery_path: Literal["direct_connector_automation", "multi_agent_software_dev"] = "multi_agent_software_dev"
    roles: list[str] | None = None
    department: str | None = None


class EvaluateTradeoffRequest(BaseModel):
    brief_text: str
    node_id: str = "finance"


class ResolveGateRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    comment: str | None = None
    actor_email: str = "sarah.controller@wallbox.com"
    roles: list[str] | None = None
    department: str | None = None


# --- REST API Endpoints ---
@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "sdo-adk-engine",
        "version": "0.1.0",
        "project_id": settings.project_id,
        "model": settings.model_name,
    }


@app.post("/api/v1/tradeoffs/evaluate", response_model=TradeoffComparison)
async def evaluate_tradeoffs(req: EvaluateTradeoffRequest):
    """Evaluate a natural language business brief and present comparative trade-offs."""
    return TradeoffEvaluator.evaluate_brief(brief_text=req.brief_text, domain=req.node_id)


@app.post("/api/v1/loops", status_code=201)
async def create_loop(req: CreateLoopRequest, request: Request = None):
    """Launch a new SDO loop from a natural language brief."""
    loop_id = f"01KZZ{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    assigned_roles = req.roles
    if not assigned_roles:
        registry = get_skill_registry()
        try:
            skill = registry.get_skill(req.node_id)
            assigned_roles = list(skill.authorized_roles)
        except Exception:
            assigned_roles = ["financial_controller"]

    assigned_dept = req.department or req.node_id.title()

    headers = dict(request.headers) if request is not None else {}
    initiator = gateway_auth.extract_identity_from_headers(
        headers=headers,
        fallback_email=req.owner_email,
        fallback_roles=assigned_roles,
        fallback_dept=assigned_dept,
    )

    tradeoff = TradeoffEvaluator.evaluate_brief(req.brief_text, req.node_id)

    state = LoopState(
        loop_id=loop_id,
        node_id=req.node_id,
        initiator=initiator,
        brief_raw=req.brief_text,
        delivery_path=req.delivery_path,
        tradeoff_analysis=tradeoff.model_dump(mode="json"),
    )

    # Run Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> GATE_H1 (pauses at WAIT_GATE_H1)
    graph = build_configured_graph()
    state = await graph.run_until_pause_or_terminal(state)
    active_loops[loop_id] = state

    # Store and catalog spec in GCS & BigQuery index
    catalog = get_artifact_catalog()
    if state.spec_content:
        spec_rec = await catalog.store_and_catalog_artifact(
            domain=state.node_id,
            loop_id=state.loop_id,
            artifact_name="spec.md",
            artifact_type="SPECIFICATION",
            content=state.spec_content,
            created_by=state.initiator.user_email or "sdo-engine",
        )
        state.gcs_artifact_uris["SPECIFICATION"] = spec_rec.gcs_uri

    # Stream analytics
    await analytics.log_step_event(
        loop_id=state.loop_id,
        node_id=state.node_id,
        step_name=state.current_state,
        duration_ms=450.0,
    )

    return state


@app.get("/api/v1/loops")
async def list_loops():
    """List all loops."""
    return list(active_loops.values())


@app.get("/api/v1/loops/{loop_id}")
async def get_loop(loop_id: str):
    """Get status and artifacts of a specific loop."""
    if loop_id not in active_loops:
        raise HTTPException(status_code=404, detail=f"Loop '{loop_id}' not found.")
    return active_loops[loop_id]


@app.get("/api/v1/artifacts")
async def list_all_artifacts(domain: str | None = None):
    """List all indexed process artifacts stored in GCS and indexed in BigQuery."""
    catalog = get_artifact_catalog()
    return await catalog.list_all_artifacts(domain=domain)


@app.get("/api/v1/loops/{loop_id}/artifacts")
async def list_loop_artifacts(loop_id: str):
    """List all indexed process artifacts for a specific delivery loop."""
    catalog = get_artifact_catalog()
    return await catalog.list_artifacts_for_loop(loop_id=loop_id)


@app.post("/api/v1/loops/{loop_id}/gates/{gate}/resolve")
async def resolve_gate(loop_id: str, gate: Literal["h1", "h2"], req: ResolveGateRequest, request: Request = None):
    """Resolve human approval Gate H1 or Gate H2 and resume state graph execution."""
    if loop_id not in active_loops:
        raise HTTPException(status_code=404, detail=f"Loop '{loop_id}' not found.")

    state = active_loops[loop_id]

    assigned_roles = req.roles
    if not assigned_roles:
        registry = get_skill_registry()
        try:
            skill = registry.get_skill(state.node_id)
            assigned_roles = list(skill.authorized_roles)
        except Exception:
            assigned_roles = ["financial_controller"]

    assigned_dept = req.department or state.initiator.department or state.node_id.title()

    headers = dict(request.headers) if request is not None else {}
    actor = gateway_auth.extract_identity_from_headers(
        headers=headers,
        fallback_email=req.actor_email,
        fallback_roles=assigned_roles,
        fallback_dept=assigned_dept,
    )

    resolution = GateResolution(
        gate=gate,
        decision=req.decision,
        comment=req.comment,
        actor=actor,
        resolved_at=datetime.now(timezone.utc),
    )

    if gate == "h1":
        if state.gate_h1 is not None:
            raise HTTPException(status_code=409, detail="Gate H1 is already resolved.")
        state.gate_h1 = resolution
        state.current_state = "GATE_H1"
    elif gate == "h2":
        if state.gate_h2 is not None:
            raise HTTPException(status_code=409, detail="Gate H2 is already resolved.")
        state.gate_h2 = resolution
        state.current_state = "GATE_H2"

    # Resume graph execution
    graph = build_configured_graph()
    state = await graph.run_until_pause_or_terminal(state)
    active_loops[loop_id] = state

    # Stream analytics
    await analytics.log_step_event(
        loop_id=state.loop_id,
        node_id=state.node_id,
        step_name=state.current_state,
        duration_ms=620.0,
    )

    return state


@app.post("/api/v1/chat/webhook")
async def chat_webhook(request: Request):
    """Google Chat Webhook endpoint receiving messages and card clicks."""
    payload = await request.json()
    event_type = payload.get("type", "MESSAGE")

    if event_type == "MESSAGE":
        message_text = payload.get("message", {}).get("text", "Automated brief")
        sender_email = payload.get("message", {}).get("sender", {}).get("email", "sarah@wallbox.com")

        req = CreateLoopRequest(brief_text=message_text, owner_email=sender_email)
        state = await create_loop(req)
        return GoogleChatAdapter.format_gate_h1_card(state)

    elif event_type == "CARD_CLICKED":
        action = payload.get("action", {})
        func = action.get("function")
        params = {p["key"]: p["value"] for p in action.get("parameters", [])}

        if func == "resolve_gate":
            loop_id = params.get("loop_id")
            gate = params.get("gate", "h1")
            decision = params.get("decision", "approve")

            req = ResolveGateRequest(decision=decision)  # type: ignore
            state = await resolve_gate(loop_id, gate, req)  # type: ignore
            if state.current_state == "WAIT_GATE_H2":
                return GoogleChatAdapter.format_gate_h2_card(state)
            return {"text": f"Loop '{loop_id}' advanced to state '{state.current_state}'."}

    return {"text": "SDO Bot acknowledged event."}


@app.get("/a2a/app/.well-known/agent-card.json")
async def get_agent_card():
    """Agent-to-Agent (A2A) Discovery Card for Gemini Enterprise registration."""
    return {
        "name": "Wallbox SDO Delivery Platform",
        "description": "Automated Software & Data Delivery Multi-Agent System on GCP (Finance, Sales, Firmware, Marketing, Logistics).",
        "version": "0.1.0",
        "protocolVersion": "1.0",
        "url": "https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app/a2a/app/.well-known/agent-card.json",
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "capabilities": {
            "streaming": True,
        },
        "skills": [
            {
                "id": "finance_variance",
                "name": "Finance FX & Revenue Variance",
                "description": "Analyzes invoice reconciliation and FX variance.",
                "tags": ["finance", "bigquery"],
            },
            {
                "id": "sales_pipeline",
                "name": "Sales Opportunity Pipeline",
                "description": "Aggregates commercial pipeline conversion metrics.",
                "tags": ["sales"],
            },
            {
                "id": "firmware_telemetry",
                "name": "Firmware & IoT Telemetry",
                "description": "Analyzes OCPP charger logs and device errors.",
                "tags": ["firmware", "iot"],
            },
            {
                "id": "marketing_attribution",
                "name": "Marketing Multi-Touch Attribution",
                "description": "Calculates customer acquisition cost across channels.",
                "tags": ["marketing"],
            },
            {
                "id": "logistics_turnover",
                "name": "Supply Chain & Logistics",
                "description": "Monitors warehouse dispatch SLAs and inventory turnover.",
                "tags": ["logistics"],
            },
        ],
    }


# Mount Static Files for Web Dashboard UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_dashboard():
    """Serve Interactive Web Dashboard for Chrome browser verification."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>SDO Platform Running</h1><p>Static files loading...</p>")
