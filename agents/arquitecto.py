"""Arquitecto Agent (Technical Blueprint & Test Plan Authoring via Gemini 3.7 Flash)."""

from __future__ import annotations

import logging
from typing import Any
from graphs.state import LoopState

logger = logging.getLogger(__name__)


class ArquitectoAgent:
    """Agent responsible for producing technical designs, SQL transformations, and sandbox test plans."""

    SYSTEM_PROMPT = """You are Arquitecto, the Technical Architecture and Design Agent for Wallbox SDO Platform.
Your task is to take an approved specification (spec.md) and business brief, and produce a comprehensive technical design (design.md).

Requirements for design.md:
1. Architectural Blueprint: Component topology, execution sequence, and data flow.
2. Data Models & SQL DDL/Queries: BigQuery transformations, partition/cluster strategies, and view definitions.
3. Sandbox Test Plan: Explicitly enumerate unit test functions, expected inputs/outputs, and edge-case boundary conditions to be executed inside the Linux sandbox.

Output must be well-structured Markdown."""

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client

    async def generate_design(self, state: LoopState) -> str:
        """Produce design.md based on spec.md."""
        logger.info("Arquitecto generating technical design for loop '%s'", state.loop_id)

        if not self.model_client:
            # Deterministic template for offline execution
            return f"""# Technical Design Document: {state.brief_raw[:50]}

## 1. Component Architecture
- Ingress: BigQuery Scheduled Query / View
- Execution Engine: Serverless Python transformation script
- Output Destination: `sdo_{state.node_id}_demo.weekly_revenue_variance`

## 2. BigQuery SQL Transformation
```sql
CREATE OR REPLACE VIEW `sdo_{state.node_id}_demo.weekly_revenue_variance` AS
SELECT
    i.invoice_id,
    i.account_id,
    i.amount AS amount_original,
    i.currency AS currency_original,
    COALESCE(e.rate, 1.0) AS exchange_rate,
    ROUND(i.amount * COALESCE(e.rate, 1.0), 2) AS amount_usd,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_{state.node_id}_demo.invoices` AS i
LEFT JOIN `sdo_{state.node_id}_demo.exchange_rates` AS e
    ON i.currency = e.target_currency AND e.base_currency = 'EUR'
WHERE i.status = 'PAID';
```

## 3. Ephemeral Sandbox Test Plan
- `test_currency_conversion_precision`: Validates rounding and exchange rate multiplication.
- `test_null_exchange_rate_fallback`: Validates 1.0 multiplier fallback when rate is missing.
- `test_sql_syntax_conformance`: Runs SQL syntax linter on generated view DDL.
"""

        prompt = f"""Business Brief: {state.brief_raw}
Domain: {state.node_id}
Approved Specification:
{state.spec_content}"""

        response = await self.model_client.generate_content_async(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            system_instruction={"parts": [{"text": self.SYSTEM_PROMPT}]},
            generation_config={"temperature": 0.2, "max_output_tokens": 4096},
        )
        return response.text


async def design_node(state: LoopState, model_client: Any = None) -> LoopState:
    """Graph node handler for DESIGN state."""
    agent = ArquitectoAgent(model_client=model_client)
    state.design_content = await agent.generate_design(state)
    return state
