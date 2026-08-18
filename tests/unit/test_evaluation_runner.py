"""Unit tests for Gemini Enterprise Evaluation Suite & Benchmarks."""

import pytest
from pathlib import Path
from eval.evaluator import SDOAgentEvaluator
from eval.custom_metrics import (
    score_gherkin_contract,
    score_graph_conformance,
    score_sandbox_reliability,
    score_skill_compliance,
)


@pytest.mark.asyncio
async def test_evaluation_benchmark_suite():
    """Run full benchmark suite and assert all benchmarks pass with aggregate_score >= 0.85."""
    benchmarks_path = Path(__file__).resolve().parent.parent.parent / "eval" / "benchmarks" / "finance_benchmarks.json"
    assert benchmarks_path.exists(), f"Benchmark file not found at {benchmarks_path}"

    score_cards = await SDOAgentEvaluator.run_benchmark_suite(benchmarks_path)
    assert len(score_cards) >= 5

    for card in score_cards:
        assert card.passed is True, f"Benchmark {card.loop_id} failed evaluation: {card.summary}"
        assert card.aggregate_score >= 0.85, f"Benchmark {card.loop_id} aggregate score {card.aggregate_score} < 0.85"
        assert card.gherkin_contract_score >= 0.90
        assert card.graph_conformance_score >= 0.90
        assert card.skill_compliance_score >= 0.90
        assert card.sandbox_reliability_score == 1.0


def test_custom_metrics_edge_cases():
    """Test boundary and edge cases in custom evaluation metrics."""
    # Empty inputs
    assert score_gherkin_contract(None) == 0.0
    assert score_gherkin_contract("") == 0.0
    assert score_graph_conformance([]) == 0.0
    assert score_skill_compliance("finance", None) == 0.0
    assert score_sandbox_reliability({}) == 0.0

    # Failed sandbox
    failed_results = {"passed": False, "pass_rate": 50.0, "exit_code": 1}
    assert score_sandbox_reliability(failed_results) == 0.40

    # Clean sandbox
    passed_results = {"passed": True, "pass_rate": 100.0, "exit_code": 0}
    assert score_sandbox_reliability(passed_results) == 1.0
