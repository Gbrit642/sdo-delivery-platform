"""Custom Evaluation Metrics for Gemini Enterprise Agent Platform Evaluation."""

from __future__ import annotations

from typing import Any
from harnesses.tier1_static_rules import Tier1StaticValidator
from registry.skill_registry import get_skill_registry


def score_gherkin_contract(spec_content: str | None) -> float:
    """Evaluate specification contract adherence (returns score between 0.0 and 1.0)."""
    if not spec_content:
        return 0.0

    violations = Tier1StaticValidator.validate_spec(spec_content)
    if not violations:
        return 1.0

    # Penalize based on number of syntax/schema violations
    penalty = min(len(violations) * 0.25, 1.0)
    return round(1.0 - penalty, 2)


def score_graph_conformance(executed_steps: list[str]) -> float:
    """Verify that execution followed the strict deterministic state transition sequence."""
    if not executed_steps:
        return 0.0

    expected_sequence = ["INTAKE", "SPECIFY", "SPEC_HARNESS", "GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW", "GATE_H2", "CLOSE", "WATCH", "DONE"]
    matches = 0
    seq_idx = 0

    for step in executed_steps:
        if step in expected_sequence[seq_idx:]:
            matches += 1
            seq_idx = expected_sequence.index(step) + 1

    return round(matches / max(len(executed_steps), 1), 2)


def score_skill_compliance(node_id: str, spec_content: str | None) -> float:
    """Evaluate compliance with multi-domain skill rules from the Skill Registry."""
    if not spec_content:
        return 0.0

    try:
        registry = get_skill_registry()
        violations = registry.validate_spec_rules(node_id, spec_content)
        if not violations:
            return 1.0
        return max(round(1.0 - (len(violations) * 0.3), 2), 0.0)
    except Exception:
        return 0.5


def score_sandbox_reliability(test_results: dict[str, Any]) -> float:
    """Score the sandbox test pass rate and execution outcome."""
    if not test_results:
        return 0.0

    pass_rate = test_results.get("pass_rate", 0.0)
    exit_code = test_results.get("exit_code", 1)

    if exit_code == 0 and pass_rate == 100.0:
        return 1.0
    return round(pass_rate / 100.0 * 0.8, 2)
