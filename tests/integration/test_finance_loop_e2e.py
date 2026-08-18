"""End-to-End Integration Test simulating complete 4-Leg Finance Delivery Lifecycle."""

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
from storage.crypto_shredding import CryptoShredder
from tools.github_client import GitHubClient
from eval.evaluator import SDOAgentEvaluator


@pytest.mark.asyncio
async def test_full_finance_delivery_lifecycle_e2e():
    """Simulate a complete end-to-end run from initial brief to WORM seal and evaluation."""
    settings = get_settings()
    auth = AgentGatewayAuth(auth_mode="local")
    github_client = GitHubClient(use_mock=True)
    audit_writer = WormAuditWriter(bucket_name=settings.gcs_worm_bucket, use_mock=True)
    crypto_shredder = CryptoShredder(project_id=settings.project_id, use_mock=True)

    # 1. Initiator identity and raw brief
    initiator = auth.authenticate_token({
        "email": "sarah.controller@wallbox.com",
        "sub": "auth0|wallbox_sarah_123",
        "roles": ["financial_controller"],
        "department": "Finance",
    })

    state = LoopState(
        loop_id="01KZZFINANCE000000000001",
        node_id="finance",
        initiator=initiator,
        brief_raw="Create a weekly currency variance analysis view in BigQuery comparing EUR invoices with USD receipts.",
    )

    # 2. Build ADK State Graph
    graph = SDOStateGraph()

    async def close_handler(s: LoopState) -> LoopState:
        # Create branch and PR
        branch = f"feature/{s.loop_id}"
        await github_client.create_branch(branch)
        commit_sha = await github_client.commit_files(branch, s.code_artifacts, "feat(finance): add weekly FX variance view")
        pr = await github_client.create_pull_request(branch, "[FINANCE] FX Variance View", "Automated delivery PR")
        merge_sha = await github_client.merge_pull_request(pr.pr_number, "Squash and merge")
        tag = await github_client.create_release_tag("v1.0.0", merge_sha, "Release v1.0.0")

        s.close_commit_hash = merge_sha
        s.pull_request_url = pr.html_url

        # WORM Seal with envelope crypto-shredding
        encrypted_str = crypto_shredder.encrypt_user_payload(s.initiator.subject_id or "anon", {"brief": s.brief_raw})
        audit_key = await audit_writer.write_audit_record(
            node_id=s.node_id,
            loop_id=s.loop_id,
            seq=10,
            intent_kind="LOOP_CLOSED_AND_SEALED",
            actor_email=s.initiator.user_email or "unknown",
            actor_type=s.initiator.actor_type,
            raw_payload={"loop_id": s.loop_id, "commit": merge_sha},
            encrypted_payload_str=encrypted_str,
        )
        s.worm_audit_record_id = audit_key
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

    executed_steps: list[str] = []

    # --- LEG 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pauses at GATE_H1 ---
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])

    assert state.current_state == "WAIT_GATE_H1"
    assert state.spec_content is not None
    assert "Feature:" in state.spec_content
    assert state.spec_harness is not None
    assert state.spec_harness.passed is True

    # --- LEG 2: Resolve Gate H1 -> Advances to DESIGN -> IMPLEMENT -> REVIEW -> Pauses at GATE_H2 ---
    state.gate_h1 = GateResolution(
        gate="h1",
        decision="approve",
        actor=state.initiator,
    )
    state.current_state = "GATE_H1"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])

    assert state.current_state == "WAIT_GATE_H2"
    assert state.design_content is not None
    assert "transform.py" in state.code_artifacts
    assert "query.sql" in state.code_artifacts
    assert state.test_results["passed"] is True
    assert state.test_results["pass_rate"] == 100.0
    assert state.code_artifacts["review_outcome"] == "pass"

    # --- LEG 3: Resolve Gate H2 -> Advances to CLOSE -> WATCH -> Terminal DONE ---
    state.gate_h2 = GateResolution(
        gate="h2",
        decision="approve",
        actor=state.initiator,
    )
    state.current_state = "GATE_H2"
    state = await graph.run_until_pause_or_terminal(state)
    executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

    assert state.current_state == "DONE"
    assert state.close_commit_hash is not None
    assert state.pull_request_url is not None
    assert state.worm_audit_record_id is not None
    assert state.watch_telemetry_results["status"] == "HEALTHY"

    # --- EVALUATION QUALITY CHECK ---
    score_card = SDOAgentEvaluator.evaluate_loop_state(state, executed_steps)
    assert score_card.passed is True
    assert score_card.aggregate_score >= 0.85
    assert score_card.gherkin_contract_score == 1.0
    assert score_card.sandbox_reliability_score == 1.0

    # --- GDPR CRYPTO-SHREDDING VERIFICATION ---
    # Decryption works before shredding
    decrypted = crypto_shredder.decrypt_user_payload(
        state.initiator.subject_id,
        crypto_shredder.encrypt_user_payload(state.initiator.subject_id, {"data": "confidential"}),
    )
    assert decrypted["data"] == "confidential"

    # Shred user keys
    shred_success = crypto_shredder.shred_user_data(state.initiator.subject_id)
    assert shred_success is True

    # Decryption MUST fail after shredding
    with pytest.raises(KeyError, match="Key for subject .* has been permanently destroyed"):
        crypto_shredder.decrypt_user_payload(state.initiator.subject_id, "mock_payload")
