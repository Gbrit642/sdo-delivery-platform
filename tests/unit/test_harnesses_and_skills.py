"""Unit tests for Multi-Domain Skill Registry and Two-Tier Quality Harnesses."""

import pytest
from graphs.state import ActorIdentity, LoopState
from registry.skill_registry import SkillRegistry, get_skill_registry
from harnesses.tier1_static_rules import Tier1StaticValidator
from harnesses.tier2_policy_critic import PolicyAuditorAgent
from harnesses.harness_node import spec_harness_node


VALID_FINANCE_SPEC = """---
id: "SPEC-FINANCE-001"
title: "Weekly Currency Variance Reporting View"
node_id: "finance"
created_at: "2026-08-18T12:00:00Z"
target_repository: "wallbox/finance-pipelines"
---

# Feature: Weekly Currency Variance Analysis

## Background
Finance controllers require automated FX reconciliation between invoices in EUR and payment receipts in USD.

## Scenario: Calculate FX variance between EUR invoice and USD receipt
  Given an invoice issued in "EUR" with amount 1000.00
  When converted to "USD" using daily exchange rate 1.0850
  Then expected USD amount is 1085.00
  And variance is within reconciliation_variance_tolerance_pct of 0.01%

## Business Metrics
- target_sla_seconds: 5.0
- baseline_error_rate: 0.001
- reconciliation_variance_tolerance_pct: 0.05
"""


def test_skill_registry_loads_all_domains():
    """Verify all domain YAML files are parsed correctly into DomainSkill models."""
    registry = get_skill_registry()
    domains = registry.list_domains()
    assert "finance" in domains
    assert "sales" in domains
    assert "firmware" in domains
    assert "marketing" in domains

    finance_skill = registry.get_skill("finance")
    assert "sdo_finance_demo.invoices" in finance_skill.authorized_tables
    assert finance_skill.acceptance_criteria["min_unit_test_pass_rate"] == 100.0


def test_tier1_validates_valid_spec():
    """Valid finance spec passes Tier 1 static checks with zero violations."""
    violations = Tier1StaticValidator.validate_spec(VALID_FINANCE_SPEC, node_id="finance")
    assert violations == []


def test_tier1_detects_missing_frontmatter():
    """Missing frontmatter block triggers Tier 1 validation error."""
    spec_no_frontmatter = "# Feature: Currency\nScenario: Test\nGiven X\nWhen Y\nThen Z\n## Business Metrics\ntarget_sla_seconds: 1"
    violations = Tier1StaticValidator.validate_spec(spec_no_frontmatter, node_id="finance")
    assert any("Missing YAML frontmatter" in v for v in violations)


def test_tier1_detects_missing_gherkin():
    """Missing mandatory Gherkin keywords triggers Tier 1 validation error."""
    spec_no_gherkin = """---
id: "SPEC-001"
title: "Test"
node_id: "finance"
created_at: "2026-08-18T12:00:00Z"
target_repository: "wallbox/repo"
---
# Just a description without Gherkin
## Business Metrics
target_sla_seconds: 1
"""
    violations = Tier1StaticValidator.validate_spec(spec_no_gherkin, node_id="finance")
    assert any("Missing mandatory Gherkin keyword" in v for v in violations)


def test_tier1_detects_prohibited_sql_in_domain():
    """Spec with prohibited SQL (e.g. DROP TABLE) fails domain policy checks."""
    bad_sql_spec = VALID_FINANCE_SPEC + "\nDROP TABLE sdo_finance_demo.invoices;"
    violations = Tier1StaticValidator.validate_spec(bad_sql_spec, node_id="finance")
    assert any("prohibited SQL operation 'DROP TABLE'" in v for v in violations)


def test_tier1_python_ast_security_checks():
    """AST validator detects forbidden dynamic execution and syntax errors."""
    valid_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    assert Tier1StaticValidator.validate_python_code(valid_code) == []

    bad_syntax = "def add(a: int"
    assert any("Python syntax error" in v for v in Tier1StaticValidator.validate_python_code(bad_syntax))

    unsafe_code = "import os\nos.system('rm -rf /')"
    assert any("forbidden OS execution call" in v for v in Tier1StaticValidator.validate_python_code(unsafe_code))


@pytest.mark.asyncio
async def test_composite_spec_harness_node_success():
    """Two-tier spec harness passes valid spec and updates LoopState.spec_harness."""
    state = LoopState(
        loop_id="01KZZSPEC0000000000000000",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah@wallbox.com"),
        brief_raw="Create currency variance analysis view.",
        spec_content=VALID_FINANCE_SPEC,
    )

    state = await spec_harness_node(state)
    assert state.spec_harness is not None
    assert state.spec_harness.passed is True
    assert len(state.spec_harness.tier1_violations) == 0


@pytest.mark.asyncio
async def test_composite_spec_harness_node_failure():
    """Two-tier spec harness catches invalid spec and records violations."""
    state = LoopState(
        loop_id="01KZZSPEC0000000000000001",
        node_id="finance",
        initiator=ActorIdentity(actor_type="human", user_email="sarah@wallbox.com"),
        brief_raw="Create currency variance analysis view.",
        spec_content="Invalid spec without frontmatter or Gherkin",
    )

    state = await spec_harness_node(state)
    assert state.spec_harness is not None
    assert state.spec_harness.passed is False
    assert len(state.spec_harness.tier1_violations) > 0
