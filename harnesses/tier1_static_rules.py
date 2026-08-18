"""Tier 1 Deterministic Static Code and Specification Rules Validator."""

from __future__ import annotations

import ast
import re
from typing import Any
import yaml
from registry.skill_registry import get_skill_registry


class Tier1StaticValidator:
    """Static AST, schema, and regex parser for specifications and generated code."""

    REQUIRED_FRONTMATTER_FIELDS = {"id", "title", "node_id", "created_at", "target_repository"}
    GHERKIN_KEYWORDS = ["Feature:", "Scenario:", "Given", "When", "Then"]
    FORBIDDEN_CODE_PATTERNS = [
        "os.system",
        "subprocess.Popen",
        "eval(",
        "exec(",
        "__import__",
    ]

    @classmethod
    def validate_spec(cls, spec_content: str | None, node_id: str = "finance") -> list[str]:
        """Validate specification structure, YAML frontmatter, Gherkin syntax, and domain rules."""
        violations: list[str] = []

        if not spec_content or not spec_content.strip():
            return ["Specification content is empty."]

        # 1. Parse and validate YAML Frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", spec_content, re.DOTALL)
        if not frontmatter_match:
            violations.append("Missing YAML frontmatter block (enclosed in '---').")
        else:
            try:
                frontmatter = yaml.safe_load(frontmatter_match.group(1))
                if not isinstance(frontmatter, dict):
                    violations.append("YAML frontmatter is not a valid dictionary.")
                else:
                    for field in cls.REQUIRED_FRONTMATTER_FIELDS:
                        if field not in frontmatter:
                            violations.append(f"Missing required frontmatter field '{field}'.")
            except Exception as e:
                violations.append(f"Failed to parse YAML frontmatter: {e}")

        # 2. Validate Gherkin Acceptance Criteria Keywords
        for kw in cls.GHERKIN_KEYWORDS:
            if kw not in spec_content:
                violations.append(f"Missing mandatory Gherkin keyword '{kw}'.")

        # 3. Check for Business Metrics Block
        if "## Business Metrics" not in spec_content and "### Metrics" not in spec_content:
            violations.append("Missing mandatory 'Business Metrics' section in spec.md.")

        # 4. Enforce Domain-Specific Skill Rules from Skill Registry
        try:
            registry = get_skill_registry()
            domain_violations = registry.validate_spec_rules(node_id, spec_content)
            violations.extend(domain_violations)
        except Exception as e:
            violations.append(f"Error evaluating domain skill rules: {e}")

        return violations

    @classmethod
    def validate_python_code(cls, code_content: str) -> list[str]:
        """Parse Python code with AST to detect syntax errors and unsafe function calls."""
        violations: list[str] = []

        # 1. Parse AST to verify syntax
        try:
            tree = ast.parse(code_content)
        except SyntaxError as e:
            return [f"Python syntax error at line {e.lineno}: {e.msg}"]

        # 2. Check for forbidden security patterns
        for node in ast.walk(tree):
            # Check for forbidden function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "__import__"):
                    violations.append(f"Security violation: forbidden dynamic execution function '{node.func.id}()'")
                elif isinstance(node.func, ast.Attribute) and node.func.attr in ("system", "popen"):
                    violations.append(f"Security violation: forbidden OS execution call '{node.func.attr}()'")

        return violations
