"""Composite Two-Tier Compliance & Quality Harness Node."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from graphs.state import HarnessEvaluation, LoopState
from harnesses.tier1_static_rules import Tier1StaticValidator
from harnesses.tier2_policy_critic import PolicyAuditorAgent

logger = logging.getLogger(__name__)


async def spec_harness_node(state: LoopState, model_client: object = None) -> LoopState:
    """Execute Two-Tier Quality Harness before Gate H1."""
    logger.info("Running Two-Tier Spec Harness for loop '%s' (domain: '%s')", state.loop_id, state.node_id)

    # --- Tier 1: Deterministic Static AST & Regex Checks ---
    tier1_violations = Tier1StaticValidator.validate_spec(state.spec_content, state.node_id)

    if tier1_violations:
        logger.warning("Tier 1 static validation failed with %d violations", len(tier1_violations))
        state.spec_harness = HarnessEvaluation(
            passed=False,
            tier1_violations=tier1_violations,
            tier2_critique="Tier 1 static checks failed; Tier 2 LLM audit was skipped.",
            evaluated_at=datetime.now(timezone.utc),
        )
        return state

    # --- Tier 2: Policy Auditor Sub-Agent (Gemini 3.7 Flash Critic) ---
    auditor = PolicyAuditorAgent(model_client=model_client)
    audit_result = await auditor.evaluate_spec(
        raw_brief=state.brief_raw,
        spec_content=state.spec_content or "",
        node_id=state.node_id,
    )

    state.spec_harness = HarnessEvaluation(
        passed=audit_result.passed,
        tier1_violations=audit_result.violations,
        tier2_critique=audit_result.critique,
        evaluated_at=datetime.now(timezone.utc),
    )

    if state.spec_harness.passed:
        logger.info("Spec Harness PASSED for loop '%s'", state.loop_id)
    else:
        logger.warning("Spec Harness FAILED at Tier 2 for loop '%s': %s", state.loop_id, audit_result.critique)

    return state
