"""End-to-End Integration Tests for All 5 Domain Scenarios (SC-01 to SC-05).

Defined in validation_matrix.md:
- SC-01: Finance (Financial Controller - Currency variance analysis view)
- SC-02: Sales (Commercial Operations - Pipeline conversion view & PII masking)
- SC-03: Firmware (Embedded Lead - OCPP protocol validation & charger telemetry)
- SC-04: Marketing (Growth Manager - Multi-touch attribution & GDPR filtering)
- SC-05: Logistics (Supply Chain Lead - Warehouse dispatch SLA & inventory turnover)
"""

import pytest
from config.settings import get_settings
from gateway.auth import AgentGatewayAuth
from graphs.state import ActorIdentity, GateResolution, LoopState
from graphs.workflow import SDOStateGraph
from agents.documental import specify_node
from agents.arquitecto import design_node
from agents.implementer import implement_node
from agents.reviewer import review_node
from agents.watcher import watch_node
from harnesses.harness_node import spec_harness_node
from storage.worm_audit import WormAuditWriter
from tools.github_client import GitHubClient
from eval.evaluator import SDOAgentEvaluator


def build_test_graph(github_client: GitHubClient, audit_writer: WormAuditWriter) -> SDOStateGraph:
    """Construct full SDOStateGraph wired with test mocks."""
    graph = SDOStateGraph()

    async def close_handler(s: LoopState) -> LoopState:
        branch = f"feature/{s.loop_id}"
        await github_client.create_branch(branch)
        commit_sha = await github_client.commit_files(
            branch, s.code_artifacts, f"feat({s.node_id}): Automated deliverable for {s.loop_id}"
        )
        pr = await github_client.create_pull_request(
            branch, f"[{s.node_id.upper()}] Deliverable {s.loop_id}", "Automated PR"
        )
        merge_sha = await github_client.merge_pull_request(pr.pr_number, "Squash and merge")
        tag = await github_client.create_release_tag(f"v1.0.{s.loop_id[:6]}", merge_sha, "Release deliverable")

        s.close_commit_hash = merge_sha
        s.pull_request_url = pr.html_url
        s.worm_audit_record_id = await audit_writer.write_audit_record(
            node_id=s.node_id,
            loop_id=s.loop_id,
            seq=10,
            intent_kind="LOOP_CLOSED_AND_SEALED",
            actor_email=s.initiator.user_email or "unknown",
            actor_type=s.initiator.actor_type,
            raw_payload={
                "loop_id": s.loop_id,
                "commit": merge_sha,
                "brief": s.brief_raw,
                "spec_id": f"SPEC-{s.node_id.upper()}-{s.loop_id[:8]}",
            },
        )
        return s

    graph.add_node("INTAKE", lambda s: s)
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


@pytest.mark.asyncio
async def test_sc01_finance_domain_e2e():
    """SC-01: Finance Scenario - Weekly FX currency variance view."""
    settings = get_settings()
    auth = AgentGatewayAuth(auth_mode="local")
    github_client = GitHubClient(use_mock=True)
    audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)

    initiator = auth.authenticate_token({
        "email": "sarah.controller@wallbox.com",
        "sub": "auth0|sarah_fin_101",
        "roles": ["financial_controller"],
        "department": "Finance",
    })

    state = LoopState(
        loop_id="01KZZSC01FIN00000000001",
        node_id="finance",
        initiator=initiator,
        brief_raw="Create a weekly currency variance analysis view in BigQuery comparing EUR invoices with USD receipts.",
    )

    graph = build_test_graph(github_client, audit_writer)
    executed_steps: list[str] = []

    # Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pause at GATE_H1
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])
    assert state.current_state == "WAIT_GATE_H1"
    assert state.spec_harness.passed is True
    assert "reconciliation_variance_tolerance_pct" in state.spec_content

    # Leg 2: Gate H1 Approve -> DESIGN -> IMPLEMENT -> REVIEW -> Pause at GATE_H2
    state.gate_h1 = GateResolution(gate="h1", decision="approve", actor=initiator)
    state.current_state = "GATE_H1"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])
    assert state.current_state == "WAIT_GATE_H2"
    assert state.test_results["pass_rate"] == 100.0
    assert state.code_artifacts["review_outcome"] == "pass"

    # Leg 3: Gate H2 Approve -> CLOSE -> WATCH -> DONE
    state.gate_h2 = GateResolution(gate="h2", decision="approve", actor=initiator)
    state.current_state = "GATE_H2"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

    assert state.current_state == "DONE"
    assert state.close_commit_hash is not None
    assert state.worm_audit_record_id is not None
    assert state.watch_telemetry_results["status"] == "HEALTHY"

    score_card = SDOAgentEvaluator.evaluate_loop_state(state, executed_steps)
    assert score_card.passed is True
    assert score_card.aggregate_score >= 0.85


@pytest.mark.asyncio
async def test_sc02_sales_domain_e2e():
    """SC-02: Sales Scenario - Sales pipeline conversion view with PII masking."""
    settings = get_settings()
    auth = AgentGatewayAuth(auth_mode="local")
    github_client = GitHubClient(use_mock=True)
    audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)

    initiator = auth.authenticate_token({
        "email": "sales.lead@wallbox.com",
        "sub": "auth0|sales_lead_202",
        "roles": ["sales_lead", "commercial_ops"],
        "department": "Sales",
    })

    state = LoopState(
        loop_id="01KZZSC02SALES000000001",
        node_id="sales",
        initiator=initiator,
        brief_raw="Create an automated sales pipeline conversion view aggregating monthly opportunities by stage.",
    )

    graph = build_test_graph(github_client, audit_writer)
    executed_steps: list[str] = []

    # Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pause at GATE_H1
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])
    assert state.current_state == "WAIT_GATE_H1"
    assert state.spec_harness.passed is True
    assert "conversion_variance_pct" in state.spec_content

    # Leg 2: Gate H1 Approve -> DESIGN -> IMPLEMENT -> REVIEW -> Pause at GATE_H2
    state.gate_h1 = GateResolution(gate="h1", decision="approve", actor=initiator)
    state.current_state = "GATE_H1"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])
    assert state.current_state == "WAIT_GATE_H2"
    assert state.test_results["pass_rate"] == 100.0
    assert "pii_masking_check" in state.test_results["executed_test_types"]
    assert state.code_artifacts["review_outcome"] == "pass"

    # Leg 3: Gate H2 Approve -> CLOSE -> WATCH -> DONE
    state.gate_h2 = GateResolution(gate="h2", decision="approve", actor=initiator)
    state.current_state = "GATE_H2"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

    assert state.current_state == "DONE"
    assert state.close_commit_hash is not None
    assert state.worm_audit_record_id is not None
    assert state.watch_telemetry_results["status"] == "HEALTHY"

    score_card = SDOAgentEvaluator.evaluate_loop_state(state, executed_steps)
    assert score_card.passed is True
    assert score_card.aggregate_score >= 0.85


@pytest.mark.asyncio
async def test_sc03_firmware_domain_e2e():
    """SC-03: Firmware Scenario - Charger error logs and OCPP telemetry metrics."""
    settings = get_settings()
    auth = AgentGatewayAuth(auth_mode="local")
    github_client = GitHubClient(use_mock=True)
    audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)

    initiator = auth.authenticate_token({
        "email": "firmware.eng@wallbox.com",
        "sub": "auth0|fw_eng_303",
        "roles": ["firmware_engineer", "embedded_lead"],
        "department": "Firmware",
    })

    state = LoopState(
        loop_id="01KZZSC03FW000000000001",
        node_id="firmware",
        initiator=initiator,
        brief_raw="Aggregate hourly charger error logs and telemetry metrics across Pulsar Plus devices.",
    )

    graph = build_test_graph(github_client, audit_writer)
    executed_steps: list[str] = []

    # Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pause at GATE_H1
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])
    assert state.current_state == "WAIT_GATE_H1"
    assert state.spec_harness.passed is True
    assert "telemetry_ingestion_delay_ms" in state.spec_content

    # Leg 2: Gate H1 Approve -> DESIGN -> IMPLEMENT -> REVIEW -> Pause at GATE_H2
    state.gate_h1 = GateResolution(gate="h1", decision="approve", actor=initiator)
    state.current_state = "GATE_H1"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])
    assert state.current_state == "WAIT_GATE_H2"
    assert state.test_results["pass_rate"] == 100.0
    assert "ocpp_compliance_check" in state.test_results["executed_test_types"]
    assert state.code_artifacts["review_outcome"] == "pass"

    # Leg 3: Gate H2 Approve -> CLOSE -> WATCH -> DONE
    state.gate_h2 = GateResolution(gate="h2", decision="approve", actor=initiator)
    state.current_state = "GATE_H2"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

    assert state.current_state == "DONE"
    assert state.close_commit_hash is not None
    assert state.worm_audit_record_id is not None
    assert state.watch_telemetry_results["status"] == "HEALTHY"

    score_card = SDOAgentEvaluator.evaluate_loop_state(state, executed_steps)
    assert score_card.passed is True
    assert score_card.aggregate_score >= 0.85


@pytest.mark.asyncio
async def test_sc04_marketing_domain_e2e():
    """SC-04: Marketing Scenario - Multi-touch attribution view & CAC calculation."""
    settings = get_settings()
    auth = AgentGatewayAuth(auth_mode="local")
    github_client = GitHubClient(use_mock=True)
    audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)

    initiator = auth.authenticate_token({
        "email": "growth.lead@wallbox.com",
        "sub": "auth0|mkt_growth_404",
        "roles": ["marketing_manager", "growth_analyst"],
        "department": "Marketing",
    })

    state = LoopState(
        loop_id="01KZZSC04MKT00000000001",
        node_id="marketing",
        initiator=initiator,
        brief_raw="Build a multi-touch campaign attribution view calculating CAC across Search and Social channels.",
    )

    graph = build_test_graph(github_client, audit_writer)
    executed_steps: list[str] = []

    # Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pause at GATE_H1
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])
    assert state.current_state == "WAIT_GATE_H1"
    assert state.spec_harness.passed is True
    assert "cac_calculation_variance_pct" in state.spec_content

    # Leg 2: Gate H1 Approve -> DESIGN -> IMPLEMENT -> REVIEW -> Pause at GATE_H2
    state.gate_h1 = GateResolution(gate="h1", decision="approve", actor=initiator)
    state.current_state = "GATE_H1"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])
    assert state.current_state == "WAIT_GATE_H2"
    assert state.test_results["pass_rate"] == 100.0
    assert "gdpr_cookie_consent_filter_check" in state.test_results["executed_test_types"]
    assert state.code_artifacts["review_outcome"] == "pass"

    # Leg 3: Gate H2 Approve -> CLOSE -> WATCH -> DONE
    state.gate_h2 = GateResolution(gate="h2", decision="approve", actor=initiator)
    state.current_state = "GATE_H2"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

    assert state.current_state == "DONE"
    assert state.close_commit_hash is not None
    assert state.worm_audit_record_id is not None
    assert state.watch_telemetry_results["status"] == "HEALTHY"

    score_card = SDOAgentEvaluator.evaluate_loop_state(state, executed_steps)
    assert score_card.passed is True
    assert score_card.aggregate_score >= 0.85


@pytest.mark.asyncio
async def test_sc05_logistics_domain_e2e():
    """SC-05: Logistics Scenario - Warehouse dispatch SLA monitoring & inventory turnover."""
    settings = get_settings()
    auth = AgentGatewayAuth(auth_mode="local")
    github_client = GitHubClient(use_mock=True)
    audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)

    initiator = auth.authenticate_token({
        "email": "supply.lead@wallbox.com",
        "sub": "auth0|supply_lead_505",
        "roles": ["supply_chain_lead", "plant_manager"],
        "department": "Logistics",
    })

    state = LoopState(
        loop_id="01KZZSC05LOG00000000001",
        node_id="logistics",
        initiator=initiator,
        brief_raw="Create warehouse dispatch SLA monitoring view tracking parts inventory turnover.",
    )

    graph = build_test_graph(github_client, audit_writer)
    executed_steps: list[str] = []

    # Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pause at GATE_H1
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])
    assert state.current_state == "WAIT_GATE_H1"
    assert state.spec_harness.passed is True
    assert "dispatch_sla_adherence_pct" in state.spec_content

    # Leg 2: Gate H1 Approve -> DESIGN -> IMPLEMENT -> REVIEW -> Pause at GATE_H2
    state.gate_h1 = GateResolution(gate="h1", decision="approve", actor=initiator)
    state.current_state = "GATE_H1"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])
    assert state.current_state == "WAIT_GATE_H2"
    assert state.test_results["pass_rate"] == 100.0
    assert "dispatch_sla_check" in state.test_results["executed_test_types"]
    assert state.code_artifacts["review_outcome"] == "pass"

    # Leg 3: Gate H2 Approve -> CLOSE -> WATCH -> DONE
    state.gate_h2 = GateResolution(gate="h2", decision="approve", actor=initiator)
    state.current_state = "GATE_H2"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

    assert state.current_state == "DONE"
    assert state.close_commit_hash is not None
    assert state.worm_audit_record_id is not None
    assert state.watch_telemetry_results["status"] == "HEALTHY"

    score_card = SDOAgentEvaluator.evaluate_loop_state(state, executed_steps)
    assert score_card.passed is True
    assert score_card.aggregate_score >= 0.85
