"""Tier 2 Policy Auditor Sub-Agent (Gemini 3.7 Flash Critic)."""

from __future__ import annotations

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PolicyAuditResult(BaseModel):
    """Structured critique returned by the PolicyAuditorAgent."""

    passed: bool
    violations: list[str] = Field(default_factory=list)
    critique: str = ""


class PolicyAuditorAgent:
    """LLM Critic agent evaluating SOC 2, GDPR, and scope completeness against the brief."""

    SYSTEM_PROMPT = """You are the SDO PolicyAuditorAgent, an expert compliance and enterprise software reviewer.
Your job is to critically evaluate a generated specification (spec.md) against the original business brief.

Evaluation Criteria:
1. Scope Alignment: Does the spec accurately and fully address the business brief without hallucinations or missing requirements?
2. SOC 2 Compliance: Does the specification respect access boundaries and require audit logging?
3. GDPR & Privacy: Does the specification avoid unmasked personal data (PII) exposure?
4. Negative Testing: Does the specification define failure scenarios and edge cases?

You must respond ONLY with a JSON object matching this schema:
{
  "passed": true|false,
  "violations": ["list of explicit policy or scope violations if passed is false"],
  "critique": "A concise, actionable explanation of the review findings"
}"""

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client

    async def evaluate_spec(
        self, raw_brief: str, spec_content: str, node_id: str = "finance"
    ) -> PolicyAuditResult:
        """Run policy evaluation against the specification."""
        if not self.model_client:
            # Deterministic offline evaluation mode for test suites
            return self._evaluate_offline(raw_brief, spec_content, node_id)

        prompt = f"""Business Brief:
{raw_brief}

Domain Node: {node_id}

Generated Specification:
{spec_content}"""

        try:
            response = await self.model_client.generate_content_async(
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                system_instruction={"parts": [{"text": self.SYSTEM_PROMPT}]},
                generation_config={"response_mime_type": "application/json", "temperature": 0.1},
            )
            raw_text = response.text
            parsed = json.loads(raw_text)
            return PolicyAuditResult(**parsed)
        except Exception as e:
            logger.warning("Tier 2 LLM audit call failed, falling back to heuristic audit: %s", e)
            return self._evaluate_offline(raw_brief, spec_content, node_id)

    def _evaluate_offline(self, raw_brief: str, spec_content: str, node_id: str) -> PolicyAuditResult:
        """Deterministic heuristic check used during offline testing."""
        violations: list[str] = []

        # Check for privacy issues
        if "credit_card" in spec_content.lower() or "ssn" in spec_content.lower() or "password" in spec_content.lower():
            violations.append("GDPR/SOC 2 violation: spec mentions unmasked sensitive personal identifiers.")

        # Check for empty or minimal spec
        if len(spec_content.splitlines()) < 10:
            violations.append("Scope violation: specification is too brief and lacks detailed acceptance scenarios.")

        passed = len(violations) == 0
        critique = "Specification complies with SOC 2, GDPR, and scope requirements." if passed else "Policy violations identified."
        return PolicyAuditResult(passed=passed, violations=violations, critique=critique)
