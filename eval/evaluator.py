"""Gemini Enterprise Agent Platform Evaluation Runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from eval.custom_metrics import (
    score_gherkin_contract,
    score_graph_conformance,
    score_sandbox_reliability,
    score_skill_compliance,
)
from graphs.state import LoopState


class EvaluationScoreCard(BaseModel):
    """Aggregate evaluation report for SDO agent trajectories."""

    loop_id: str
    node_id: str
    gherkin_contract_score: float
    graph_conformance_score: float
    skill_compliance_score: float
    sandbox_reliability_score: float
    aggregate_score: float
    passed: bool
    summary: str


class SDOAgentEvaluator:
    """Evaluates completed loop trajectories against Gemini Enterprise evaluation standards."""

    @classmethod
    def evaluate_loop_state(cls, state: LoopState, executed_steps: list[str]) -> EvaluationScoreCard:
        """Score a completed loop state across all quality dimensions."""
        gherkin_score = score_gherkin_contract(state.spec_content)
        graph_score = score_graph_conformance(executed_steps)
        skill_score = score_skill_compliance(state.node_id, state.spec_content)
        sandbox_score = score_sandbox_reliability(state.test_results)

        # Weighted aggregate index
        aggregate = round(
            (gherkin_score * 0.3)
            + (graph_score * 0.25)
            + (skill_score * 0.25)
            + (sandbox_score * 0.2),
            2,
        )
        passed = aggregate >= 0.85

        summary = (
            f"Evaluation Quality Index: {aggregate * 100:.1f}% (Gherkin: {gherkin_score:.2f}, "
            f"Graph: {graph_score:.2f}, Skill: {skill_score:.2f}, Sandbox: {sandbox_score:.2f})"
        )

        return EvaluationScoreCard(
            loop_id=state.loop_id,
            node_id=state.node_id,
            gherkin_contract_score=gherkin_score,
            graph_conformance_score=graph_score,
            skill_compliance_score=skill_score,
            sandbox_reliability_score=sandbox_score,
            aggregate_score=aggregate,
            passed=passed,
            summary=summary,
        )
