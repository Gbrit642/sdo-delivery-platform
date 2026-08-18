"""Multi-domain Skill Registry loader and policy evaluation engine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field


class DomainSkill(BaseModel):
    """Strongly typed Domain Skill Manifest representation."""

    domain: str
    display_name: str
    description: str
    authorized_roles: list[str] = Field(default_factory=list)
    authorized_tables: list[str] = Field(default_factory=list)
    intake_guidelines: dict[str, Any] = Field(default_factory=dict)
    spec_validation_rules: dict[str, Any] = Field(default_factory=dict)
    acceptance_criteria: dict[str, Any] = Field(default_factory=dict)


class SkillRegistry:
    """Registry managing domain-specific skill manifests and policy enforcement."""

    def __init__(self, skills_dir: Path | str | None = None) -> None:
        if skills_dir is None:
            skills_dir = Path(__file__).parent / "skills"
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, DomainSkill] = {}
        self.load_skills()

    def load_skills(self) -> None:
        """Scan skills directory and parse all domain YAML files."""
        self._skills.clear()
        if not self.skills_dir.exists():
            return

        for filepath in self.skills_dir.glob("*.yaml"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "domain" in data:
                        skill = DomainSkill(**data)
                        self._skills[skill.domain] = skill
            except Exception as e:
                raise ValueError(f"Failed to parse skill manifest at {filepath}: {e}") from e

    def get_skill(self, domain: str) -> DomainSkill:
        """Retrieve a specific domain skill by identifier."""
        if domain not in self._skills:
            # Fallback to finance default if not found
            if "finance" in self._skills:
                return self._skills["finance"]
            raise KeyError(f"Domain skill '{domain}' not found in registry.")
        return self._skills[domain]

    def list_domains(self) -> list[str]:
        """List all loaded domain identifiers."""
        return list(self._skills.keys())

    def get_intake_guidance(self, domain: str) -> str:
        """Return system prompt guidance for tailoring the brief in the given domain."""
        skill = self.get_skill(domain)
        return skill.intake_guidelines.get("prompt_guidance", "").strip()

    def validate_spec_rules(self, domain: str, spec_text: str) -> list[str]:
        """Validate specification content against domain-specific policies."""
        violations: list[str] = []
        skill = self.get_skill(domain)
        rules = skill.spec_validation_rules

        # Check prohibited SQL patterns
        prohibited_sql = rules.get("prohibited_sql_patterns", [])
        for pattern in prohibited_sql:
            if pattern in spec_text.upper():
                violations.append(f"Domain policy violation: spec contains prohibited SQL operation '{pattern}'")

        # Check mandatory metrics
        mandatory_metrics = rules.get("mandatory_metrics", [])
        for metric in mandatory_metrics:
            if metric not in spec_text:
                violations.append(f"Domain policy violation: missing mandatory metric '{metric}'")

        return violations

    def validate_acceptance_criteria(
        self, domain: str, test_results: dict[str, Any], code_artifacts: dict[str, str]
    ) -> list[str]:
        """Validate delivered code and test execution against domain acceptance criteria."""
        violations: list[str] = []
        skill = self.get_skill(domain)
        ac = skill.acceptance_criteria

        # Check unit test pass rate
        min_pass_rate = ac.get("min_unit_test_pass_rate", 100.0)
        actual_pass_rate = test_results.get("pass_rate", 0.0)
        if actual_pass_rate < min_pass_rate:
            violations.append(
                f"Acceptance failure: unit test pass rate {actual_pass_rate}% below required {min_pass_rate}%"
            )

        # Check required test types
        required_test_types = ac.get("required_test_types", [])
        executed_test_types = test_results.get("executed_test_types", [])
        for req_test in required_test_types:
            if req_test not in executed_test_types:
                violations.append(f"Acceptance failure: mandatory test type '{req_test}' was not executed")

        return violations


# Singleton global instance
_global_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Retrieve the singleton SkillRegistry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
