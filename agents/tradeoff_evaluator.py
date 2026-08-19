"""Trade-Off & Path Evaluation Engine for Business Domain Owners."""

from __future__ import annotations

import logging
from typing import Any, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PathOption(BaseModel):
    """Business-oriented description of a delivery path."""

    path_id: Literal["direct_connector_automation", "multi_agent_software_dev"]
    title: str
    summary: str
    pros: list[str]
    cons: list[str]
    estimated_speed: str
    governance_model: str
    suitable_use_cases: list[str]


class TradeoffComparison(BaseModel):
    """Comparative Trade-Off Matrix presented to non-technical business users."""

    recommended_path: Literal["direct_connector_automation", "multi_agent_software_dev"]
    recommendation_rationale: str
    direct_connector_option: PathOption
    multi_agent_option: PathOption


class TradeoffEvaluator:
    """Evaluates business briefs to present clear, non-technical trade-offs."""

    @classmethod
    def evaluate_brief(cls, brief_text: str, domain: str = "finance") -> TradeoffComparison:
        """Analyze user brief and generate non-technical comparative trade-offs."""
        brief_lower = brief_text.lower()

        # Keywords indicating pure reporting / standard queries
        direct_keywords = [
            "report", "view", "query", "dashboard", "aggregate", "variance view",
            "select", "pull data", "extract", "salesforce", "netsuite", "notion"
        ]

        # Keywords indicating bespoke software / custom logic
        multi_agent_keywords = [
            "custom script", "api", "webhook", "microservice", "python",
            "algorithm", "library", "sdk", "complex workflow", "endpoint"
        ]

        direct_score = sum(1 for kw in direct_keywords if kw in brief_lower)
        agent_score = sum(1 for kw in multi_agent_keywords if kw in brief_lower)

        if direct_score >= agent_score and "python" not in brief_lower and "api" not in brief_lower:
            recommended = "direct_connector_automation"
            rationale = (
                f"Your request appears to be focused on analytical reporting and data aggregation in the {domain} domain. "
                "The Direct Connector Automation path is recommended because it runs natively on your data warehouse/connectors "
                "with sub-second speed, minimal cost, and zero server maintenance, while retaining full Gate H1 & H2 approvals."
            )
        else:
            recommended = "multi_agent_software_dev"
            rationale = (
                f"Your request involves custom business logic, data transformation pipelines, or multi-step logic. "
                "The Autonomous Multi-Agent Software Development path is recommended because it synthesizes custom Python code, "
                "creates architectural blueprints, and rigorously tests the code in an isolated Linux sandbox with 100% test pass verification."
            )

        direct_option = PathOption(
            path_id="direct_connector_automation",
            title="Direct Connector Automation (Tool-Native / MCP)",
            summary="Executes standard analytical queries and data transformations directly via Managed Connectors (BigQuery, Salesforce, NetSuite, etc.) without creating new custom software.",
            pros=[
                "Lightning Fast: Sub-second native database execution",
                "Cost Efficient: $0 extra server or sandbox compute",
                "Simple Maintenance: Uses existing managed cloud connectors directly",
                "Full Human Governance: Retains Gate H1 (Spec) and Gate H2 (Activation) approvals",
            ],
            cons=[
                "Best for standard analytical transformations and reports",
                "Does not build custom software applications or bespoke Python microservices",
            ],
            estimated_speed="< 5 seconds",
            governance_model="Two-Tier Spec Gate + Gate H1 + Gate H2 + WORM Audit Trail",
            suitable_use_cases=[
                "Currency variance analysis views",
                "Sales pipeline conversion metrics",
                "Weekly/monthly KPI aggregation reports",
                "Cross-table data joins from Salesforce or NetSuite",
            ],
        )

        multi_agent_option = PathOption(
            path_id="multi_agent_software_dev",
            title="Autonomous Multi-Agent Software Development (Full ADK Graph)",
            summary="Builds a bespoke software solution: generates Gherkin specifications, architectural blueprints, custom Python code, and runs tests in an isolated Linux sandbox.",
            pros=[
                "Full Custom Software: Generates complete Python modules, SQL views, and APIs",
                "Deep Architecture: Creates architectural blueprints and Gherkin scenarios",
                "Sandbox Verified: Executes automated unit tests in an isolated Linux container with 100% pass rate",
                "Automated Recovery: Detects failures and auto-fixes code autonomously up to 3 retries",
                "Day 30 Health Telemetry: Continuously monitors query latency and error rates after deployment",
            ],
            cons=[
                "Multi-stage synthesis takes slightly longer (~30-60s)",
                "Higher LLM token and sandbox container compute footprint",
            ],
            estimated_speed="30 - 60 seconds",
            governance_model="Two-Tier Quality Harness + Gate H1 + Gate H2 + Ephemeral Sandbox + WORM Audit Trail",
            suitable_use_cases=[
                "Bespoke data engineering algorithms with custom Python logic",
                "Firmware telemetry error pattern decoders (OCPP 1.6J/2.0.1)",
                "Multi-touch marketing attribution algorithms with complex cookie filtering",
                "New microservices or automated alerting integrations",
            ],
        )

        return TradeoffComparison(
            recommended_path=recommended,
            recommendation_rationale=rationale,
            direct_connector_option=direct_option,
            multi_agent_option=multi_agent_option,
        )
