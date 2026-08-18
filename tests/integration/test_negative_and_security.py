"""Comprehensive Negative Testing & Failure Recovery Integration Suite (NEG-01 to NEG-07).

Defined in validation_matrix.md:
- NEG-01: Domain Access Control (RBAC) - unauthorized role blocked at INTAKE -> CLOSED
- NEG-02: Prohibited SQL Injection - DROP TABLE caught by Tier 1 static validator
- NEG-03: Missing Mandatory Metrics - missing metrics section rejected by Tier 1 and retries SPECIFY
- NEG-04: Sandbox Test Failure & Auto-Fix - test assertion error caught by Reviewer -> fail_fix -> IMPLEMENT
- NEG-05: Max Retry Budget Escalation - 3 failed attempts halt cyclic loop -> ESCALATED
- NEG-06: Gate H1 Request Changes - human changes request increments retry and routes back to SPECIFY
- NEG-07: Gate H2 Rejection - human rejection at Gate H2 transitions to CLOSED without merge or tag
"""

import pytest
from gateway.auth import AgentGatewayAuth
from gateway.policy_interceptor import PolicyInterceptor
from graphs.state import ActorIdentity, GateResolution, HarnessEvaluation, LoopState
from graphs.router import route_gate_h1, route_gate_h2, route_review, route_spec_harness
from graphs.workflow import SDOStateGraph
from harnesses.tier1_static_rules import Tier1StaticValidator
from harnesses.harness_node import spec_harness_node
from agents.documental import specify_node
from agents.implementer import implement_node
from agents.reviewer import review_node
from tools.managed_sandbox import ManagedAgentSandbox
from tools.github_client import GitHubClient


@pytest.mark.asyncio
async def test_neg01_domain_access_control_rbac():
    """NEG-01: Unauthorized user blocked at INTAKE and loop transitions to CLOSED."""
    auth = AgentGatewayAuth(auth_mode="local")
    # Sales user with only sales role trying to access Finance
    sales_actor = auth.authenticate_token({
        "email": "unauthorized.sales@wallbox.com",
        "roles": ["sales_lead"],
        "department": "Sales",
    })

    assert not PolicyInterceptor.verify_node_access(sales_actor, "finance")

    state = LoopState(
        loop_id="01KZZNEG01RBAC00000001",
        node_id="finance",
        initiator=sales_actor,
        brief_raw="Attempting unauthorized access to finance data.",
    )

    graph = SDOStateGraph()

    async def intake_with_rbac(s: LoopState) -> LoopState:
        if not PolicyInterceptor.verify_node_access(s.initiator, s.node_id):
            s.escalation_reason = f"Access denied: User '{s.initiator.user_email}' not authorized for domain '{s.node_id}'"
            s.current_state = "CLOSED"
        return s

    graph.add_node("INTAKE", intake_with_rbac)

    state = await graph.step(state)
    assert state.current_state == "CLOSED"
    assert "Access denied" in state.escalation_reason


def test_neg02_prohibited_sql_injection():
    """NEG-02: Spec with destructive SQL operation (DROP TABLE) is rejected before Gate H1."""
    malicious_spec = """---
id: "SPEC-FINANCE-MALICIOUS"
title: "Malicious Query"
node_id: "finance"
created_at: "2026-08-18T12:00:00Z"
target_repository: "wallbox/finance-pipelines"
---

# Feature: Data Cleanup

## Scenario: Delete Tables
  Given target table exists
  When DROP TABLE sdo_finance_demo.invoices; is executed
  Then all tables are removed

## Business Metrics
- target_sla_seconds: 5.0
- baseline_error_rate: 0.001
- reconciliation_variance_tolerance_pct: 0.05
"""
    violations = Tier1StaticValidator.validate_spec(malicious_spec, node_id="finance")
    assert len(violations) > 0
    assert any("DROP TABLE" in v for v in violations)


@pytest.mark.asyncio
async def test_neg03_missing_mandatory_metrics():
    """NEG-03: Spec missing mandatory metrics is rejected by Tier 1 and triggers deterministic retry to SPECIFY."""
    spec_missing_metrics = """---
id: "SPEC-FINANCE-NO-METRICS"
title: "Spec Without Metrics Section"
node_id: "finance"
created_at: "2026-08-18T12:00:00Z"
target_repository: "wallbox/finance-pipelines"
---

# Feature: Currency Conversion

## Scenario: Convert EUR to USD
  Given currency is EUR
  When converted to USD
  Then amount matches rate
"""
    violations = Tier1StaticValidator.validate_spec(spec_missing_metrics, node_id="finance")
    assert any("Business Metrics" in v for v in violations)

    state = LoopState(
        loop_id="01KZZNEG03METRICS00001",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah@wallbox.com"),
        brief_raw="Create currency view.",
        spec_content=spec_missing_metrics,
    )

    state = await spec_harness_node(state)
    assert state.spec_harness.passed is False
    assert state.spec_harness.tier1_violations

    # Router should route back to SPECIFY and charge 1 retry
    next_node = route_spec_harness(state)
    assert next_node == "SPECIFY"
    assert state.retry_counts["SPECIFY"] == 1


@pytest.mark.asyncio
async def test_neg04_sandbox_test_failure_and_autofix():
    """NEG-04: Reviewer detects failing sandbox test suite and routes back to IMPLEMENT."""
    sandbox = ManagedAgentSandbox()

    # Broken code with assertion failure
    broken_code = {
        "transform.py": """
def convert_currency(amount: float, rate: float) -> float:
    return amount * rate + 999.99  # Deliberate bug
"""
    }
    test_files = {
        "test_transform.py": """
from transform import convert_currency

def test_currency_conversion():
    assert convert_currency(100.0, 1.0) == 100.0
"""
    }

    result = await sandbox.execute_code_tests(broken_code, test_files, ["unit"])
    assert result.passed is False
    assert result.pass_rate == 0.0

    state = LoopState(
        loop_id="01KZZNEG04TESTFAIL001",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah@wallbox.com"),
        brief_raw="Test auto-fix routing.",
        test_results={
            "passed": result.passed,
            "pass_rate": result.pass_rate,
            "executed_test_types": result.executed_test_types,
            "stderr": result.stderr,
        },
    )

    state = await review_node(state)
    assert state.code_artifacts["review_outcome"] == "fail_fix"
    assert "Sandbox unit tests failed" in state.code_artifacts["review_summary"]

    next_node = route_review(state)
    assert next_node == "IMPLEMENT"
    assert state.retry_counts["IMPLEMENT"] == 1


def test_neg05_max_retry_budget_escalation():
    """NEG-05: Exceeding max retry budget (3) halts cyclic loop and transitions directly to ESCALATED."""
    state = LoopState(
        loop_id="01KZZNEG05MAXRETRY001",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah@wallbox.com"),
        brief_raw="Test escalation.",
        retry_counts={"SPECIFY": 3, "DESIGN": 0, "IMPLEMENT": 0},
        max_retries=3,
        spec_harness=HarnessEvaluation(passed=False, tier1_violations=["Persistent invalid schema"]),
    )

    next_node = route_spec_harness(state)
    assert next_node == "ESCALATED"
    assert "failed after 3 retries" in state.escalation_reason

    # Review retry exhaustion
    state.retry_counts["IMPLEMENT"] = 3
    state.code_artifacts["review_outcome"] = "fail_fix"
    next_node_review = route_review(state)
    assert next_node_review == "ESCALATED"
    assert "retry limit (3) for node 'IMPLEMENT' was reached" in state.escalation_reason


def test_neg06_gate_h1_request_changes():
    """NEG-06: Human reviewer requests modifications at Gate H1 -> routes back to SPECIFY with feedback."""
    state = LoopState(
        loop_id="01KZZNEG06GATEH1CHG01",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah.controller@wallbox.com"),
        brief_raw="Create currency variance analysis view.",
    )

    state.gate_h1 = GateResolution(
        gate="h1",
        decision="request_changes",
        comment="Please include GBP/EUR conversion rate scenario.",
        actor=state.initiator,
    )

    next_node = route_gate_h1(state)
    assert next_node == "SPECIFY"
    assert state.retry_counts["SPECIFY"] == 1


@pytest.mark.asyncio
async def test_neg07_gate_h2_rejection():
    """NEG-07: Human reviewer rejects release at Gate H2 -> CLOSED, PR unmerged, zero tag created."""
    github_client = GitHubClient(use_mock=True)

    state = LoopState(
        loop_id="01KZZNEG07GATEH2REJ01",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah.controller@wallbox.com"),
        brief_raw="Create currency variance view.",
    )

    # Open PR
    branch = f"feature/{state.loop_id}"
    await github_client.create_branch(branch)
    pr = await github_client.create_pull_request(branch, "Feature PR", "Deliverables")
    state.pull_request_url = pr.html_url

    # Reject at Gate H2
    state.gate_h2 = GateResolution(
        gate="h2",
        decision="reject",
        comment="Release failed manual business verification. Rejected.",
        actor=state.initiator,
    )

    next_node = route_gate_h2(state)
    assert next_node == "CLOSED"
    assert "Gate H2 rejected by human reviewer" in state.escalation_reason

    # Confirm PR remains open/unmerged and no commit close hash was sealed
    assert pr.merged is False
    assert state.close_commit_hash is None
