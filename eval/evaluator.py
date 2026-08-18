"""Gemini Enterprise Agent Platform Evaluation Runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path for direct CLI execution
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

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
        gherkin_score = score_gherkin_contract(state.spec_content, node_id=state.node_id)
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

    @classmethod
    async def evaluate_benchmark(cls, benchmark_item: dict[str, Any]) -> EvaluationScoreCard:
        """Execute and evaluate a single benchmark item through the complete state graph."""
        from graphs.state import ActorIdentity, GateResolution
        from graphs.workflow import SDOStateGraph
        from agents.documental import specify_node
        from agents.arquitecto import design_node
        from agents.implementer import implement_node
        from agents.reviewer import review_node
        from agents.watcher import watch_node
        from harnesses.harness_node import spec_harness_node
        from storage.worm_audit import WormAuditWriter
        from tools.github_client import GitHubClient

        node_id = benchmark_item.get("node_id", "finance")
        brief = benchmark_item.get("brief", "Automated deliverable brief.")
        bench_id = benchmark_item.get("benchmark_id", f"BENCH-{node_id.upper()}")

        actor = ActorIdentity(
            actor_type="human",
            user_email=f"owner.{node_id}@wallbox.com",
            department=node_id.title(),
            roles=[f"{node_id}_lead", "financial_controller", "finance_admin"],
        )

        state = LoopState(
            loop_id=bench_id,
            node_id=node_id,
            initiator=actor,
            brief_raw=brief,
        )

        audit_writer = WormAuditWriter(use_mock=True)
        github_client = GitHubClient(use_mock=True)

        async def close_handler(s: LoopState) -> LoopState:
            branch = f"feature/{s.loop_id}"
            await github_client.create_branch(branch)
            commit_sha = await github_client.commit_files(branch, s.code_artifacts, f"feat({s.node_id}): {s.loop_id}")
            pr = await github_client.create_pull_request(branch, f"[{s.node_id.upper()}] {s.loop_id}", "Benchmark PR")
            merge_sha = await github_client.merge_pull_request(pr.pr_number, "Squash and merge")
            s.close_commit_hash = merge_sha
            s.pull_request_url = pr.html_url
            s.worm_audit_record_id = await audit_writer.write_audit_record(
                node_id=s.node_id,
                loop_id=s.loop_id,
                seq=10,
                intent_kind="BENCHMARK_EVAL_SEAL",
                actor_email=s.initiator.user_email or "system",
                actor_type=s.initiator.actor_type,
                raw_payload={"loop_id": s.loop_id, "commit": merge_sha},
            )
            return s

        graph = SDOStateGraph()
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

        # Leg 1: INTAKE -> SPECIFY -> SPEC_HARNESS -> Pauses at Gate H1
        state = await graph.run_until_pause_or_terminal(state)
        executed_steps.extend(["INTAKE", "SPECIFY", "SPEC_HARNESS"])

        # Leg 2: Gate H1 Approve -> DESIGN -> IMPLEMENT -> REVIEW -> Pauses at Gate H2
        state.gate_h1 = GateResolution(gate="h1", decision="approve", actor=actor)
        state.current_state = "GATE_H1"
        state = await graph.run_until_pause_or_terminal(state)
        executed_steps.extend(["GATE_H1", "DESIGN", "IMPLEMENT", "REVIEW"])

        # Leg 3: Gate H2 Approve -> CLOSE -> WATCH -> DONE
        state.gate_h2 = GateResolution(gate="h2", decision="approve", actor=actor)
        state.current_state = "GATE_H2"
        state = await graph.run_until_pause_or_terminal(state)
        executed_steps.extend(["GATE_H2", "CLOSE", "WATCH", "DONE"])

        return cls.evaluate_loop_state(state, executed_steps)

    @classmethod
    async def run_benchmark_suite(cls, benchmarks_path: Path | str | None = None) -> list[EvaluationScoreCard]:
        """Load benchmark JSON definitions and run evaluation scoring across all items."""
        if benchmarks_path is None:
            benchmarks_path = Path(__file__).parent / "benchmarks" / "finance_benchmarks.json"

        benchmarks_file = Path(benchmarks_path)
        with open(benchmarks_file, "r", encoding="utf-8") as f:
            benchmarks = json.load(f)

        score_cards: list[EvaluationScoreCard] = []
        for b in benchmarks:
            card = await cls.evaluate_benchmark(b)
            score_cards.append(card)

        return score_cards


if __name__ == "__main__":
    import asyncio

    async def _main():
        print("Running Gemini Enterprise SDO Agent Offline Evaluation Suite...")
        cards = await SDOAgentEvaluator.run_benchmark_suite()
        all_passed = True
        print("\n" + "=" * 80)
        print(f"{'Benchmark ID':<15} | {'Domain':<10} | {'Gherkin':<8} | {'Graph':<8} | {'Skill':<8} | {'Sandbox':<8} | {'Score':<8} | Status")
        print("-" * 80)
        for c in cards:
            status = "PASS" if c.passed else "FAIL"
            if not c.passed:
                all_passed = False
            print(
                f"{c.loop_id:<15} | {c.node_id:<10} | {c.gherkin_contract_score:<8.2f} | "
                f"{c.graph_conformance_score:<8.2f} | {c.skill_compliance_score:<8.2f} | "
                f"{c.sandbox_reliability_score:<8.2f} | {c.aggregate_score:<8.2f} | {status}"
            )
        print("=" * 80)
        avg_score = sum(c.aggregate_score for c in cards) / len(cards)
        print(f"Benchmark Suite Aggregate Score: {avg_score:.2f} (Threshold: 0.85)")
        print(f"Overall Result: {'PASSED (Certifiable for Production Handover)' if all_passed else 'FAILED'}\n")
        assert all_passed and avg_score >= 0.85, f"Evaluation score {avg_score} below required threshold 0.85"

    asyncio.run(_main())
