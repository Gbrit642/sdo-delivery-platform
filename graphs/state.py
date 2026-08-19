"""Core state schema and data contracts for the SDO Platform State Graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


class ActorIdentity(BaseModel):
    """Dual-identity classification model distinguishing Human from Agent actors."""

    actor_type: Literal["human", "agent"]
    user_email: str | None = None
    subject_id: str | None = None
    department: str | None = None
    roles: list[str] = Field(default_factory=list)


class HarnessEvaluation(BaseModel):
    """Result of the Two-Tier Compliance & Quality Harness evaluation."""

    passed: bool
    tier1_violations: list[str] = Field(default_factory=list)
    tier2_critique: str | None = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GateResolution(BaseModel):
    """Record of a human sign-off decision at Gate H1 or Gate H2."""

    gate: Literal["h1", "h2"]
    decision: Literal["approve", "reject", "request_changes"]
    comment: str | None = None
    actor: ActorIdentity
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoopState(BaseModel):
    """Master state model hydrated and mutated across all ADK state graph nodes."""

    loop_id: str
    node_id: str = "finance"  # e.g., "finance", "sales", "firmware", "marketing", "logistics"
    initiator: ActorIdentity
    brief_raw: str

    # Delivery Path Selection (Direct Connector Automation vs Multi-Agent Software Development)
    delivery_path: Literal["direct_connector_automation", "multi_agent_software_dev"] = "multi_agent_software_dev"
    tradeoff_analysis: dict[str, Any] | None = None

    # Plane 2: Deliverables and Generated Artifacts
    spec_content: str | None = None
    design_content: str | None = None
    code_artifacts: dict[str, str] = Field(default_factory=dict)  # filename -> file content
    test_results: dict[str, Any] = Field(default_factory=dict)
    gcs_artifact_uris: dict[str, str] = Field(default_factory=dict)  # artifact_type -> gs://... URI

    # State Tracking & Deterministic Retries (charged per destination state)
    current_state: str = "INTAKE"
    retry_counts: dict[str, int] = Field(default_factory=lambda: {"SPECIFY": 0, "DESIGN": 0, "IMPLEMENT": 0})
    max_retries: int = 3

    # Quality Harness & Human Gating
    spec_harness: HarnessEvaluation | None = None
    code_harness: HarnessEvaluation | None = None
    gate_h1: GateResolution | None = None
    gate_h2: GateResolution | None = None

    # Asynchronous Day 30 Watcher Checkpoint
    watch_scheduled_at: datetime | None = None
    watch_telemetry_results: dict[str, Any] = Field(default_factory=dict)

    # Terminal Outcomes & Plane 3 Audit
    escalation_reason: str | None = None
    close_commit_hash: str | None = None
    pull_request_url: str | None = None
    worm_audit_record_id: str | None = None
    business_deliverable_card: dict[str, Any] | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_retries(self) -> int:
        """Total retry attempts across all nodes."""
        return sum(self.retry_counts.values())
