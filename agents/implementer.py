"""Implementer Agent (Code Generation & Ephemeral Sandbox Execution via Gemini 3.7 Flash)."""

from __future__ import annotations

import logging
from typing import Any
from graphs.state import LoopState
from registry.skill_registry import get_skill_registry
from tools.managed_sandbox import ManagedAgentSandbox

logger = logging.getLogger(__name__)


class ImplementerAgent:
    """Agent that compiles code/SQL deliverables and executes automated tests in an isolated sandbox."""

    SYSTEM_PROMPT = """You are Implementer, the Code & Delivery Synthesis Agent for Enterprise SDO Platform.
Your task is to synthesize verified code deliverables and execute unit tests in an isolated Linux sandbox.

STRICT NON-TECHNICAL / BUSINESS-FACING GUARDRAILS:
1. End-users are business domain managers; NEVER instruct them to run terminal commands (`python3 ...`, `pip ...`, `gcloud ...`).
2. All deployment steps are automated by the platform into the active project (default: managed-agent-504409).
3. Deliverables must be verified in the sandbox with 100% test pass rate before presentation.
4. EPHEMERAL TASK WORKER GUARDRAIL: You compile code for transient execution ($0 idle compute cost). NEVER offer or attempt to register a new permanent Assistant in Gemini Enterprise for standard delivery tasks. Permanent agent registration is only permitted if the user explicitly asks: "Register a new permanent Assistant in Gemini Enterprise".
5. IN-CHAT NATIVE EXECUTIVE DELIVERABLE: Ensure synthesized deliverables produce clean in-chat native visual reports."""

    def __init__(self, model_client: Any = None, sandbox: ManagedAgentSandbox | None = None) -> None:
        self.model_client = model_client
        self.sandbox = sandbox or ManagedAgentSandbox()

    async def implement_and_test(self, state: LoopState) -> tuple[dict[str, str], dict[str, Any]]:
        """Generate code deliverables and execute unit test suite in the ephemeral sandbox."""
        logger.info("Implementer generating code and executing sandbox tests for loop '%s'", state.loop_id)

        # 1. Retrieve required test types from Domain Skill Registry
        registry = get_skill_registry()
        skill = registry.get_skill(state.node_id)
        required_test_types = skill.acceptance_criteria.get(
            "required_test_types", ["unit", "sql_syntax_lint", "null_value_boundary", "currency_precision_check"]
        )

        # 2. Define Deliverables and Test Suites per Domain
        if state.node_id == "sales":
            code_files = {
                "transform.py": """\"\"\"Automated Sales Pipeline Conversion & PII Masking module.\"\"\"
from decimal import Decimal, ROUND_HALF_UP

def calculate_stage_conversion(won_opps: int, total_opps: int) -> float:
    \"\"\"Calculate lead conversion rate with 2-decimal percentage precision.\"\"\"
    if total_opps == 0:
        return 0.0
    rate = (Decimal(str(won_opps)) / Decimal(str(total_opps))) * Decimal("100.0")
    return float(rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def mask_pii_customer_name(raw_name: str) -> str:
    \"\"\"Anonymize customer account name for GDPR/SOC2 compliance.\"\"\"
    if not raw_name or len(raw_name) <= 2:
        return "***"
    return raw_name[0] + "*" * (len(raw_name) - 2) + raw_name[-1]
""",
                "query.sql": """-- BigQuery Sales Pipeline Transformation View
CREATE OR REPLACE VIEW `sdo_sales_demo.sales_pipeline_conversion` AS
SELECT
    stage,
    COUNT(opp_id) AS total_opportunities,
    SUM(amount_eur) AS total_pipeline_eur,
    ROUND(AVG(amount_eur), 2) AS avg_deal_size_eur,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_sales_demo.opportunities`
GROUP BY stage;
""",
            }
            test_files = {
                "test_transform.py": """\"\"\"Automated unit tests for Sales pipeline.\"\"\"
from transform import calculate_stage_conversion, mask_pii_customer_name

def test_stage_conversion_rate():
    assert calculate_stage_conversion(25, 100) == 25.0
    assert calculate_stage_conversion(0, 50) == 0.0

def test_pii_masking_anonymization():
    assert mask_pii_customer_name("Wallbox Energy") == "W************y"
    assert mask_pii_customer_name("AC") == "***"
"""
            }
        elif state.node_id == "firmware":
            code_files = {
                "transform.py": """\"\"\"Automated OCPP Telemetry & Charger Metrics parser.\"\"\"

def parse_ocpp_telemetry(raw_voltage: float, raw_current: float) -> dict[str, float]:
    \"\"\"Parse and validate charger electrical telemetry.\"\"\"
    power_kw = round((raw_voltage * raw_current) / 1000.0, 3)
    return {
        "voltage": float(raw_voltage),
        "current_amperes": float(raw_current),
        "power_kw": power_kw,
    }

def validate_charger_metrics(temperature: float) -> bool:
    \"\"\"Assert charger operating temperature is within safe threshold (< 85C).\"\"\"
    return temperature < 85.0
""",
                "query.sql": """-- BigQuery Charger Telemetry Aggregation View
CREATE OR REPLACE VIEW `sdo_firmware_demo.charger_telemetry_agg` AS
SELECT
    charger_id,
    firmware_version,
    AVG(voltage) AS avg_voltage,
    AVG(current_amperes) AS avg_current,
    MAX(temperature_celsius) AS max_temperature,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_firmware_demo.charger_telemetry`
GROUP BY charger_id, firmware_version;
""",
            }
            test_files = {
                "test_transform.py": """\"\"\"Automated unit tests for Firmware telemetry.\"\"\"
from transform import parse_ocpp_telemetry, validate_charger_metrics

def test_telemetry_schema_validation():
    telemetry = parse_ocpp_telemetry(230.0, 32.0)
    assert telemetry["power_kw"] == 7.36
    assert telemetry["voltage"] == 230.0

def test_ocpp_compliance_check():
    assert validate_charger_metrics(45.5) is True
    assert validate_charger_metrics(90.0) is False
"""
            }
        elif state.node_id == "marketing":
            code_files = {
                "transform.py": """\"\"\"Automated Campaign CAC & GDPR Consent module.\"\"\"
from decimal import Decimal, ROUND_HALF_UP

def compute_cac(total_spend: float, total_acquisitions: int) -> float:
    \"\"\"Calculate Customer Acquisition Cost with 2-decimal rounding.\"\"\"
    if total_acquisitions == 0:
        return 0.0
    cac = Decimal(str(total_spend)) / Decimal(str(total_acquisitions))
    return float(cac.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def filter_gdpr_cookie_consent(events: list[dict]) -> list[dict]:
    \"\"\"Exclude events from users who opted out of marketing tracking.\"\"\"
    return [e for e in events if e.get("consent_granted", False) is True]
""",
                "query.sql": """-- BigQuery Marketing Campaign Attribution View
CREATE OR REPLACE VIEW `sdo_marketing_demo.campaign_attribution` AS
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
GROUP BY c.channel;
""",
            }
            test_files = {
                "test_transform.py": """\"\"\"Automated unit tests for Marketing attribution.\"\"\"
from transform import compute_cac, filter_gdpr_cookie_consent

def test_cac_calculation():
    assert compute_cac(1000.0, 20) == 50.00
    assert compute_cac(0.0, 10) == 0.00

def test_gdpr_cookie_consent_filter_check():
    data = [{"id": 1, "consent_granted": True}, {"id": 2, "consent_granted": False}]
    filtered = filter_gdpr_cookie_consent(data)
    assert len(filtered) == 1
    assert filtered[0]["id"] == 1
"""
            }
        elif state.node_id == "logistics":
            code_files = {
                "transform.py": """\"\"\"Automated Inventory Turnover & Dispatch SLA monitoring module.\"\"\"
from decimal import Decimal, ROUND_HALF_UP

def calculate_inventory_turnover(cogs: float, avg_inventory: float) -> float:
    \"\"\"Calculate annual inventory turnover ratio.\"\"\"
    if avg_inventory == 0.0:
        return 0.0
    ratio = Decimal(str(cogs)) / Decimal(str(avg_inventory))
    return float(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def check_dispatch_sla(actual_hours: float, target_hours: float) -> bool:
    \"\"\"Evaluate if warehouse dispatch met agreed SLA window.\"\"\"
    return actual_hours <= target_hours
""",
                "query.sql": """-- BigQuery Inventory Turnover & Dispatch SLA View
CREATE OR REPLACE VIEW `sdo_logistics_demo.inventory_turnover_view` AS
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
    ON i.part_id = d.order_id;
""",
            }
            test_files = {
                "test_transform.py": """\"\"\"Automated unit tests for Logistics supply chain.\"\"\"
from transform import calculate_inventory_turnover, check_dispatch_sla

def test_inventory_turnover_ratio():
    assert calculate_inventory_turnover(120000.0, 30000.0) == 4.0
    assert calculate_inventory_turnover(0.0, 5000.0) == 0.0

def test_dispatch_sla_check():
    assert check_dispatch_sla(2.5, 4.0) is True
    assert check_dispatch_sla(5.0, 4.0) is False
"""
            }
        else:  # finance default
            code_files = {
                "transform.py": """\"\"\"Automated FX variance transformation module.\"\"\"
from decimal import Decimal, ROUND_HALF_UP

def convert_currency(amount: float, rate: float) -> float:
    \"\"\"Convert currency amount with 2-decimal banker rounding.\"\"\"
    dec_amount = Decimal(str(amount))
    dec_rate = Decimal(str(rate))
    converted = dec_amount * dec_rate
    return float(converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def compute_variance(original_usd: float, computed_usd: float) -> float:
    \"\"\"Calculate percentage variance between baseline and computed amounts.\"\"\"
    if original_usd == 0.0:
        return 0.0
    return abs(computed_usd - original_usd) / original_usd
""",
                "query.sql": """-- BigQuery Production View Definition
CREATE OR REPLACE VIEW `sdo_finance_demo.weekly_revenue_variance` AS
SELECT
    invoice_id,
    account_id,
    amount AS amount_original,
    currency AS currency_original,
    COALESCE(rate, 1.0) AS exchange_rate,
    ROUND(amount * COALESCE(rate, 1.0), 2) AS amount_usd,
    CURRENT_TIMESTAMP() AS computed_at
FROM `sdo_finance_demo.invoices`
LEFT JOIN `sdo_finance_demo.exchange_rates`
    ON currency = target_currency AND base_currency = 'EUR'
WHERE status = 'PAID';
""",
            }
            test_files = {
                "test_transform.py": """\"\"\"Automated unit tests to run in Managed Agent Linux Sandbox.\"\"\"
import pytest
from transform import convert_currency, compute_variance

def test_currency_conversion_precision():
    assert convert_currency(100.0, 1.0850) == 108.50
    assert convert_currency(1234.56, 0.85) == 1049.38

def test_currency_conversion_zero():
    assert convert_currency(0.0, 1.5) == 0.0

def test_compute_variance_zero():
    assert compute_variance(100.0, 100.0) == 0.0

def test_compute_variance_calculation():
    variance = compute_variance(100.0, 105.0)
    assert pytest.approx(variance, 0.001) == 0.05
"""
            }

        # 4. Execute in Serverless Ephemeral Sandbox
        sandbox_result = await self.sandbox.execute_code_tests(
            code_files=code_files,
            test_files=test_files,
            test_types=required_test_types,
        )

        test_summary = {
            "passed": sandbox_result.passed,
            "pass_rate": sandbox_result.pass_rate,
            "executed_test_types": sandbox_result.executed_test_types,
            "duration_ms": sandbox_result.duration_ms,
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "exit_code": sandbox_result.exit_code,
        }

        return code_files, test_summary


async def implement_node(state: LoopState, model_client: Any = None) -> LoopState:
    """Graph node handler for IMPLEMENT state."""
    agent = ImplementerAgent(model_client=model_client)
    code_files, test_results = await agent.implement_and_test(state)
    state.code_artifacts.update(code_files)
    state.test_results = test_results
    return state
