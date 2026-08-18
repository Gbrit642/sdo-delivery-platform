"""Deterministic routing functions for the SDO Platform State Graph.

CRITICAL RULE:
State graph transitions and retry charging are 100% deterministic in Python code.
LLMs are never permitted to decide graph edges or bypass retry limits.
"""

from typing import Literal
from graphs.state import LoopState


def route_spec_harness(state: LoopState) -> Literal["GATE_H1", "SPECIFY", "ESCALATED"]:
    """Evaluate Spec Harness results and route to Gate H1 or cyclic retry."""
    if state.spec_harness and state.spec_harness.passed:
        return "GATE_H1"

    current_retries = state.retry_counts.get("SPECIFY", 0)
    if current_retries < state.max_retries:
        state.retry_counts["SPECIFY"] = current_retries + 1
        return "SPECIFY"

    violations = ", ".join(state.spec_harness.tier1_violations) if state.spec_harness else "Unknown violations"
    state.escalation_reason = (
        f"Spec harness validation failed after {state.max_retries} retries. Violations: {violations}"
    )
    return "ESCALATED"


def route_gate_h1(state: LoopState) -> Literal["DESIGN", "SPECIFY", "CLOSED", "WAIT_GATE_H1"]:
    """Route based on human sign-off at Gate H1."""
    if state.gate_h1 is None:
        return "WAIT_GATE_H1"

    if state.gate_h1.decision == "approve":
        return "DESIGN"
    elif state.gate_h1.decision == "request_changes":
        current_retries = state.retry_counts.get("SPECIFY", 0)
        state.retry_counts["SPECIFY"] = current_retries + 1
        return "SPECIFY"
    else:  # reject
        state.escalation_reason = f"Gate H1 rejected by human reviewer ({state.gate_h1.actor.user_email})."
        return "CLOSED"


def route_review(state: LoopState) -> Literal["GATE_H2", "IMPLEMENT", "DESIGN", "SPECIFY", "ESCALATED"]:
    """Evaluate code review outcome and route to Gate H2 or destination retry."""
    # Outcome reported by Reviewer agent or code harness
    outcome = state.code_artifacts.get("review_outcome", "pass")

    if outcome == "pass":
        return "GATE_H2"

    # Map failure outcomes to target retry states
    destination_map = {
        "fail_fix": "IMPLEMENT",
        "fail_design": "DESIGN",
        "fail_definition": "SPECIFY",
        "fail_spec": "SPECIFY",
    }
    target_node = destination_map.get(outcome, "IMPLEMENT")
    current_retries = state.retry_counts.get(target_node, 0)

    if current_retries < state.max_retries:
        state.retry_counts[target_node] = current_retries + 1
        return target_node  # type: ignore

    state.escalation_reason = (
        f"Reviewer returned '{outcome}' and retry limit ({state.max_retries}) for node '{target_node}' was reached."
    )
    return "ESCALATED"


def route_gate_h2(state: LoopState) -> Literal["CLOSE", "REVIEW", "CLOSED", "WAIT_GATE_H2"]:
    """Route based on human sign-off at Gate H2 (Never auto-approves)."""
    if state.gate_h2 is None:
        return "WAIT_GATE_H2"

    if state.gate_h2.decision == "approve":
        return "CLOSE"
    elif state.gate_h2.decision == "request_changes":
        current_retries = state.retry_counts.get("IMPLEMENT", 0)
        state.retry_counts["IMPLEMENT"] = current_retries + 1
        return "REVIEW"
    else:  # reject
        state.escalation_reason = f"Gate H2 rejected by human reviewer ({state.gate_h2.actor.user_email})."
        return "CLOSED"
