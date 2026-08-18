"""Unit tests for deterministic state graph routing and retry backstops."""

import pytest
from graphs.state import ActorIdentity, GateResolution, HarnessEvaluation, LoopState
from graphs.router import route_gate_h1, route_gate_h2, route_review, route_spec_harness
from graphs.workflow import SDOStateGraph


@pytest.fixture
def base_state() -> LoopState:
    """Fixture providing a fresh LoopState instance."""
    return LoopState(
        loop_id="01KZZTESTLOOP00000000000000",
        node_id="finance",
        initiator=ActorIdentity(
            actor_type="human",
            user_email="sarah.controller@wallbox.com",
            subject_id="auth0|12345",
            department="Finance",
            roles=["financial_controller"],
        ),
        brief_raw="Create a weekly currency variance analysis view in BigQuery.",
    )


def test_route_spec_harness_pass(base_state: LoopState):
    """Spec harness pass routes directly to GATE_H1."""
    base_state.spec_harness = HarnessEvaluation(passed=True)
    destination = route_spec_harness(base_state)
    assert destination == "GATE_H1"
    assert base_state.retry_counts["SPECIFY"] == 0


def test_route_spec_harness_fail_increments_retry(base_state: LoopState):
    """Spec harness failure under limit increments retry and returns to SPECIFY."""
    base_state.spec_harness = HarnessEvaluation(
        passed=False, tier1_violations=["Missing mandatory metrics block"]
    )
    destination = route_spec_harness(base_state)
    assert destination == "SPECIFY"
    assert base_state.retry_counts["SPECIFY"] == 1

    # Second failure
    destination = route_spec_harness(base_state)
    assert destination == "SPECIFY"
    assert base_state.retry_counts["SPECIFY"] == 2


def test_route_spec_harness_exceeds_max_retries_escalates(base_state: LoopState):
    """Spec harness reaching max retries forces transition to ESCALATED."""
    base_state.retry_counts["SPECIFY"] = 3
    base_state.spec_harness = HarnessEvaluation(
        passed=False, tier1_violations=["Invalid Gherkin syntax"]
    )
    destination = route_spec_harness(base_state)
    assert destination == "ESCALATED"
    assert "validation failed after 3 retries" in base_state.escalation_reason


def test_route_gate_h1_decisions(base_state: LoopState):
    """Gate H1 routes to DESIGN on approve, SPECIFY on request_changes, and CLOSED on reject."""
    # Waiting
    assert route_gate_h1(base_state) == "WAIT_GATE_H1"

    # Approve
    base_state.gate_h1 = GateResolution(
        gate="h1",
        decision="approve",
        actor=base_state.initiator,
    )
    assert route_gate_h1(base_state) == "DESIGN"

    # Request Changes
    base_state.gate_h1 = GateResolution(
        gate="h1",
        decision="request_changes",
        comment="Please add EUR/GBP conversion scenario.",
        actor=base_state.initiator,
    )
    assert route_gate_h1(base_state) == "SPECIFY"
    assert base_state.retry_counts["SPECIFY"] == 1

    # Reject
    base_state.gate_h1 = GateResolution(
        gate="h1",
        decision="reject",
        comment="No longer needed.",
        actor=base_state.initiator,
    )
    assert route_gate_h1(base_state) == "CLOSED"


def test_route_review_transitions(base_state: LoopState):
    """Review router correctly maps fail_fix -> IMPLEMENT, fail_design -> DESIGN, fail_def -> SPECIFY."""
    # Pass
    base_state.code_artifacts["review_outcome"] = "pass"
    assert route_review(base_state) == "GATE_H2"

    # fail_fix
    base_state.code_artifacts["review_outcome"] = "fail_fix"
    assert route_review(base_state) == "IMPLEMENT"
    assert base_state.retry_counts["IMPLEMENT"] == 1

    # fail_design
    base_state.code_artifacts["review_outcome"] = "fail_design"
    assert route_review(base_state) == "DESIGN"
    assert base_state.retry_counts["DESIGN"] == 1

    # fail_definition
    base_state.code_artifacts["review_outcome"] = "fail_definition"
    assert route_review(base_state) == "SPECIFY"
    assert base_state.retry_counts["SPECIFY"] == 1


def test_route_review_escalation(base_state: LoopState):
    """Review router escalates when target destination reaches max retries."""
    base_state.retry_counts["IMPLEMENT"] = 3
    base_state.code_artifacts["review_outcome"] = "fail_fix"
    assert route_review(base_state) == "ESCALATED"
    assert "retry limit (3) for node 'IMPLEMENT' was reached" in base_state.escalation_reason


def test_route_gate_h2_decisions(base_state: LoopState):
    """Gate H2 routes to CLOSE on approve, REVIEW on request_changes, and CLOSED on reject."""
    assert route_gate_h2(base_state) == "WAIT_GATE_H2"

    base_state.gate_h2 = GateResolution(
        gate="h2",
        decision="approve",
        actor=base_state.initiator,
    )
    assert route_gate_h2(base_state) == "CLOSE"


@pytest.mark.asyncio
async def test_state_graph_run_until_gate_h1_pause(base_state: LoopState):
    """State graph steps through INTAKE -> SPECIFY -> SPEC_HARNESS and pauses at WAIT_GATE_H1."""
    graph = SDOStateGraph()

    async def mock_intake(s: LoopState) -> LoopState:
        return s

    async def mock_specify(s: LoopState) -> LoopState:
        s.spec_content = "# Feature: Currency Variance"
        return s

    async def mock_spec_harness(s: LoopState) -> LoopState:
        s.spec_harness = HarnessEvaluation(passed=True)
        return s

    async def mock_gate_h1(s: LoopState) -> LoopState:
        # Gate H1 does nothing until human resolves
        return s

    graph.add_node("INTAKE", mock_intake)
    graph.add_node("SPECIFY", mock_specify)
    graph.add_node("SPEC_HARNESS", mock_spec_harness)
    graph.add_node("GATE_H1", mock_gate_h1)

    result = await graph.run_until_pause_or_terminal(base_state)
    assert result.current_state == "WAIT_GATE_H1"
    assert result.spec_content is not None
    assert result.spec_harness.passed is True
