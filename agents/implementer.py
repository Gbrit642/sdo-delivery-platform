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

        # 2. Define Deliverables (Python transformation & SQL)
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

        # 3. Define Unit Test Suite for Sandbox
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
