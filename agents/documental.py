"""Documental Agent (Specification & Acceptance Criteria Authoring via Gemini 3.7 Flash)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from graphs.state import LoopState
from registry.skill_registry import get_skill_registry
from tools.bq_mcp_client import BigQueryMCPClient

logger = logging.getLogger(__name__)


class DocumentalAgent:
    """Agent responsible for translating business briefs into formal Gherkin specifications."""

    SYSTEM_PROMPT = """You are Documental, the specialized Specification Authoring Agent for Wallbox SDO Platform.
Your task is to transform a business brief into a rigorous, complete specification document (spec.md).

Strict Formatting Requirements:
1. YAML Frontmatter (enclosed between --- lines):
   - id: Unique spec ID (e.g. SPEC-FINANCE-001)
   - title: Human-readable specification title
   - node_id: The target domain node (e.g. finance, sales, firmware, marketing)
   - created_at: ISO8601 timestamp
   - target_repository: Target git repository
2. Feature Title and Background.
3. Multiple Acceptance Scenarios formatted in unambiguous Gherkin syntax:
   - Scenario: <title>
   - Given <preconditions>
   - When <action or event>
   - Then <expected measurable outcome>
4. Business Metrics section:
   - Must include target_sla_seconds, baseline_error_rate, and domain-specific metric thresholds.

You must output ONLY valid Markdown text with the YAML frontmatter."""

    def __init__(self, model_client: Any = None, bq_client: BigQueryMCPClient | None = None) -> None:
        self.model_client = model_client
        self.bq_client = bq_client or BigQueryMCPClient()

    async def generate_spec(self, state: LoopState) -> str:
        """Query BigQuery schema context and generate specification."""
        logger.info("Documental generating specification for loop '%s'", state.loop_id)

        # 1. Discover table schemas from BigQuery MCP for the specific domain
        dataset_name = f"sdo_{state.node_id}_demo"
        available_tables = await self.bq_client.list_tables(dataset_name)
        if not available_tables:
            available_tables = await self.bq_client.list_tables()
        table_context = []
        for t in available_tables[:3]:
            meta = await self.bq_client.get_table_schema(t, dataset_name)
            cols = [f"{c.name} ({c.data_type})" for c in meta.columns]
            table_context.append(f"Table '{t}': {', '.join(cols)}")

        # 2. Get Domain Skill Guidelines and Mandatory Metrics
        registry = get_skill_registry()
        domain_guidance = registry.get_intake_guidance(state.node_id)
        skill = registry.get_skill(state.node_id)
        mandatory_metrics = skill.spec_validation_rules.get(
            "mandatory_metrics",
            ["target_sla_seconds", "baseline_error_rate"]
        )

        if not self.model_client:
            # Deterministic template generation for offline execution and tests
            now_iso = datetime.now(timezone.utc).isoformat()
            metrics_lines = []
            for m in mandatory_metrics:
                if "tolerance" in m or "pct" in m or "variance" in m:
                    metrics_lines.append(f"- {m}: 0.05")
                elif "seconds" in m or "delay" in m:
                    metrics_lines.append(f"- {m}: 5.0")
                elif "adherence" in m or "ratio" in m:
                    metrics_lines.append(f"- {m}: 0.95")
                else:
                    metrics_lines.append(f"- {m}: 0.001")
            metrics_block = "\n".join(metrics_lines)

            return f"""---
id: "SPEC-{state.node_id.upper()}-{state.loop_id[:8]}"
title: "Specification for {state.brief_raw[:40]}"
node_id: "{state.node_id}"
created_at: "{now_iso}"
target_repository: "wallbox/{state.node_id}-delivery"
---

# Feature: {state.brief_raw}

## Background
Automated software/data deliverable generated for Wallbox {state.node_id.title()} domain.
Domain guidance: {domain_guidance}

## Available Schemas
{chr(10).join("- " + tc for tc in table_context)}

## Scenario: Execute Primary Business Transformation
  Given input data is loaded in "{state.node_id}" BigQuery tables
  When the automated transformation executes
  Then data reconciliation matches baseline with 0.00% variance
  And all acceptance test cases pass

## Scenario: Boundary and Null Value Handling
  Given input records containing edge-case null amounts
  When default imputation rules are applied
  Then records are flagged with zero data corruption

## Business Metrics
{metrics_block}
"""

        # Live Gemini 3.7 Flash Call
        prompt = f"""Business Brief: {state.brief_raw}
Domain: {state.node_id}
Available Tables: {table_context}
Domain Guidance: {domain_guidance}"""

        response = await self.model_client.generate_content_async(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            system_instruction={"parts": [{"text": self.SYSTEM_PROMPT}]},
            generation_config={"temperature": 0.2, "max_output_tokens": 4096},
        )
        return response.text


async def specify_node(state: LoopState, model_client: Any = None) -> LoopState:
    """Graph node handler for SPECIFY state."""
    agent = DocumentalAgent(model_client=model_client)
    state.spec_content = await agent.generate_spec(state)
    return state
