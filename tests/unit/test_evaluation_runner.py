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
    """Run full benchmark suite and assert all benchmarks pass with aggregate_score >= 0.85 for Option B and Option A."""
    benchmarks_path = Path(__file__).resolve().parent.parent.parent / "eval" / "benchmarks" / "finance_benchmarks.json"
    assert benchmarks_path.exists(), f"Benchmark file not found at {benchmarks_path}"

    # 1. Test Option B: ADK StateGraph deep trajectory evaluation
    score_cards_b = await SDOAgentEvaluator.run_benchmark_suite(benchmarks_path, mode="option_b_stategraph")
    assert len(score_cards_b) >= 5

    for card in score_cards_b:
        assert card.passed is True, f"Option B Benchmark {card.loop_id} failed: {card.summary}"
        assert card.aggregate_score >= 0.85, f"Benchmark {card.loop_id} aggregate score {card.aggregate_score} < 0.85"
        assert card.gherkin_contract_score >= 0.90
        assert card.graph_conformance_score >= 0.90
        assert card.skill_compliance_score >= 0.90
        assert card.sandbox_reliability_score == 1.0

    # 2. Test Option A: A2A protocol & deliverable evaluation
    score_cards_a = await SDOAgentEvaluator.run_benchmark_suite(benchmarks_path, mode="option_a_a2a")
    assert len(score_cards_a) >= 5

    for card in score_cards_a:
        assert card.passed is True, f"Option A Benchmark {card.loop_id} failed: {card.summary}"
        assert card.aggregate_score >= 0.85, f"Option A Benchmark {card.loop_id} aggregate score {card.aggregate_score} < 0.85"


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


def test_cloud_run_evaluation_quality_flywheel():
    """Test the 5-stage Evaluation Quality Flywheel across historical session traces."""
    from eval.flywheel_evaluator import EvaluationQualityFlywheel

    benchmarks_path = Path(__file__).resolve().parent.parent.parent / "eval" / "benchmarks" / "finance_benchmarks.json"
    reports = EvaluationQualityFlywheel.run_flywheel_evaluation(benchmarks_path)
    assert len(reports) == 5

    for report in reports:
        assert report.passed is True
        assert report.aggregate_score >= 0.85
        assert report.multi_turn_task_success == 1.0
        assert report.multi_turn_trajectory_quality == 1.0
        assert report.multi_turn_tool_use_quality == 1.0
        assert report.instruction_following == 1.0
        assert report.loss_cluster is None

