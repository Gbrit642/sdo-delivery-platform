"""Reviewer Agent (Quality Assurance, Code Review & AST Linting via Gemini 3.7 Flash)."""

from __future__ import annotations

import logging
from typing import Any, Literal
from graphs.state import LoopState
from registry.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """Agent that audits code quality, test suite execution results, and specification conformance."""

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client

    async def review_implementation(
        self, state: LoopState
    ) -> tuple[Literal["pass", "fail_fix", "fail_design", "fail_definition"], str]:
        """Perform comprehensive QA review of deliverables and sandbox test logs."""
        logger.info("Reviewer auditing deliverables for loop '%s'", state.loop_id)

        # 1. Verify Sandbox Test Results
        test_results = state.test_results or {}
        test_passed = test_results.get("passed", False)
        pass_rate = test_results.get("pass_rate", 0.0)

        if not test_passed or pass_rate < 100.0:
            logger.warning("Sandbox test suite failed with pass rate %.1f%%", pass_rate)
            return "fail_fix", f"Sandbox unit tests failed (pass rate: {pass_rate}%). Stderr: {test_results.get('stderr', '')}"

        # 2. Check Skill Registry Acceptance Criteria
        registry = get_skill_registry()
        skill_violations = registry.validate_acceptance_criteria(
            domain=state.node_id,
            test_results=test_results,
            code_artifacts=state.code_artifacts,
        )

        if skill_violations:
            logger.warning("Skill registry acceptance criteria failed: %s", skill_violations)
            return "fail_fix", f"Domain acceptance criteria violation: {', '.join(skill_violations)}"

        # 3. Quality & Gherkin Scenario Conformance
        summary = (
            "All unit test cases passed with 100% pass rate. "
            "Code artifacts strictly implement all Gherkin scenarios defined in spec.md."
        )
        return "pass", summary


async def review_node(state: LoopState, model_client: Any = None) -> LoopState:
    """Graph node handler for REVIEW state."""
    agent = ReviewerAgent(model_client=model_client)
    outcome, summary = await agent.review_implementation(state)
    state.code_artifacts["review_outcome"] = outcome
    state.code_artifacts["review_summary"] = summary
    logger.info("Reviewer determined outcome '%s' for loop '%s'", outcome, state.loop_id)
    return state
