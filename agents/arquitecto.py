"""Arquitecto Agent (Technical Blueprint & Test Plan Authoring via Gemini 3.7 Flash)."""

from __future__ import annotations

import logging
from typing import Any
from graphs.state import LoopState

logger = logging.getLogger(__name__)


class ArquitectoAgent:
    """Agent responsible for producing technical designs, SQL transformations, and sandbox test plans."""

    SYSTEM_PROMPT = """You are Arquitecto, the Technical Architecture and Design Agent for Enterprise SDO Platform.
Your task is to take an approved specification (spec.md) and business brief, and produce a comprehensive technical design (design.md).

STRICT NON-TECHNICAL / BUSINESS-FACING GUARDRAILS:
1. The target audience includes non-technical business stakeholders alongside cloud operators.
2. NEVER instruct the end-user to execute manual terminal or python commands (such as `python3 deploy_view.py ...`, `gcloud ...`, `pip ...`).
3. NEVER use project placeholders (like `<YOUR_PROJECT_ID>`). Deployments are executed automatically by the SDO Platform in the active project.
4. Provide direct Google Cloud Console deep links and executive summaries instead of manual command steps.

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
            # Deterministic template for offline execution tailored to the domain
            domain_view_map = {
                "finance": "sdo_finance_demo.weekly_revenue_variance",
                "sales": "sdo_sales_demo.sales_pipeline_conversion",
                "firmware": "sdo_firmware_demo.charger_telemetry_agg",
                "marketing": "sdo_marketing_demo.campaign_attribution",
                "logistics": "sdo_logistics_demo.inventory_turnover_view",
            }
            target_view = domain_view_map.get(state.node_id, f"sdo_{state.node_id}_demo.primary_view")

            if state.node_id == "sales":
                sql_snippet = f"""CREATE OR REPLACE VIEW `{target_view}` AS
SELECT
    stage,
    COUNT(opp_id) AS total_opportunities,
    SUM(amount_eur) AS total_pipeline_eur,
    ROUND(AVG(amount_eur), 2) AS avg_deal_size_eur,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_sales_demo.opportunities`
GROUP BY stage;"""
                test_plan = """- `test_stage_conversion_rate`: Validates stage-level deal aggregation.
- `test_pii_masking_anonymization`: Validates PII mask filters on customer account names.
- `test_sql_syntax_conformance`: Runs SQL syntax linter on view DDL."""
            elif state.node_id == "firmware":
                sql_snippet = f"""CREATE OR REPLACE VIEW `{target_view}` AS
SELECT
    charger_id,
    firmware_version,
    AVG(voltage) AS avg_voltage,
    AVG(current_amperes) AS avg_current,
    MAX(temperature_celsius) AS max_temperature,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_firmware_demo.charger_telemetry`
GROUP BY charger_id, firmware_version;"""
                test_plan = """- `test_telemetry_schema_validation`: Validates OCPP telemetry field structures.
- `test_ocpp_compliance_check`: Asserts OCPP 1.6J/2.0.1 protocol rule conformance.
- `test_telemetry_delay_metric`: Validates ingestion delay calculation."""
            elif state.node_id == "marketing":
                sql_snippet = f"""CREATE OR REPLACE VIEW `{target_view}` AS
SELECT
    c.channel,
    COUNT(DISTINCT c.user_id_hashed) AS unique_conversions,
    SUM(a.cac_usd) AS total_cac_usd,
    ROUND(AVG(a.cac_usd), 2) AS avg_cac_usd,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_marketing_demo.campaign_events` AS c
JOIN `sdo_marketing_demo.user_acquisitions` AS a
    ON c.campaign_id = a.campaign_id
WHERE c.event_type = 'Purchase'
GROUP BY c.channel;"""
                test_plan = """- `test_cac_calculation`: Validates CAC formula aggregation across channels.
- `test_gdpr_cookie_consent_filter_check`: Asserts unhashed PII exclusion and GDPR consent filtering.
- `test_attribution_window`: Validates multi-touch 30-day lookback window."""
            elif state.node_id == "logistics":
                sql_snippet = f"""CREATE OR REPLACE VIEW `{target_view}` AS
SELECT
    i.part_id,
    i.warehouse_id,
    i.quantity_on_hand,
    i.reorder_point,
    d.dispatch_time_hours,
    d.sla_target_hours,
    CASE WHEN d.dispatch_time_hours <= d.sla_target_hours THEN 1 ELSE 0 END AS on_time_flag,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_logistics_demo.inventory` AS i
LEFT JOIN `sdo_logistics_demo.warehouse_dispatch` AS d
    ON i.part_id = d.order_id;"""
                test_plan = """- `test_inventory_turnover_ratio`: Validates warehouse parts stock turnover calculation.
- `test_dispatch_sla_check`: Asserts dispatch duration against target SLA hours.
- `test_reorder_threshold`: Validates safety stock alert thresholding."""
            else:  # finance default
                sql_snippet = f"""CREATE OR REPLACE VIEW `{target_view}` AS
SELECT
    i.invoice_id,
    i.account_id,
    i.amount AS amount_original,
    i.currency AS currency_original,
    COALESCE(e.rate, 1.0) AS exchange_rate,
    ROUND(i.amount * COALESCE(e.rate, 1.0), 2) AS amount_usd,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_finance_demo.invoices` AS i
LEFT JOIN `sdo_finance_demo.exchange_rates` AS e
    ON i.currency = e.target_currency AND e.base_currency = 'EUR'
WHERE i.status = 'PAID';"""
                test_plan = """- `test_currency_conversion_precision`: Validates rounding and exchange rate multiplication.
- `test_null_exchange_rate_fallback`: Validates 1.0 multiplier fallback when rate is missing.
- `test_sql_syntax_conformance`: Runs SQL syntax linter on generated view DDL."""

            return f"""# Technical Design Document: {state.brief_raw[:50]}

## 1. Component Architecture
- Ingress: BigQuery Scheduled Query / View
- Execution Engine: Serverless Python transformation script
- Output Destination: `{target_view}`

## 2. BigQuery SQL Transformation
```sql
{sql_snippet}
```

## 3. Ephemeral Sandbox Test Plan
{test_plan}
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
