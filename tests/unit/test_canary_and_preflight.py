"""Unit tests for Pre-Flight Serialization Gate and Canary Validation Suite."""

from __future__ import annotations

import pytest
from scripts.deploy_reasoning_engine import (
    SDOAgentRuntimeEngine,
    run_preflight_serialization_check,
    ensure_py312_environment,
)
from scripts.run_canary_checks import (
    run_canaries,
    print_canary_report,
    parse_sse_events,
    CanaryCheckResult,
)


def test_ensure_py312_environment_execution():
    """Assert ensure_py312_environment runs without error and logs diagnostics."""
    res = ensure_py312_environment()
    assert isinstance(res, bool)


def test_run_preflight_serialization_check():
    """Assert pre-flight serialization roundtrip gate executes and returns success report."""
    engine = SDOAgentRuntimeEngine()
    report = run_preflight_serialization_check(engine)
    assert report["status"] == "PASSED"
    assert report["serialized_bytes"] > 0
    assert "stream" in report["operations"]


def test_canary_mock_mode_execution():
    """Assert run_canaries in mock mode executes all 6 tier checks and prints report."""
    results = run_canaries(mock_mode=True)
    assert len(results) == 6
    assert all(r.passed for r in results)

    # Check level distribution
    levels = [r.level for r in results]
    assert levels.count("Level 1 (Wire)") == 3
    assert levels.count("Level 2 (Assistant API)") == 3

    # Assert report printing returns True
    all_passed = print_canary_report(results)
    assert all_passed is True


def test_canary_print_report_with_failures():
    """Assert print_canary_report returns False when any check fails."""
    results = [
        CanaryCheckResult("Level 1 (Wire)", "Test Check 1", "target-1", True, 50.0, "OK"),
        CanaryCheckResult("Level 1 (Wire)", "Test Check 2", "target-2", False, 120.0, "Timeout"),
    ]
    all_passed = print_canary_report(results)
    assert all_passed is False


def test_parse_sse_events_parser():
    """Assert parse_sse_events extracts multiple data blocks correctly."""
    raw_sse = (
        "event: message\n"
        "data: {\"jsonrpc\": \"2.0\", \"id\": \"1\", \"result\": {\"role\": \"agent\"}}\n\n"
        "event: message\n"
        "data: {\"jsonrpc\": \"2.0\", \"id\": \"2\", \"result\": {\"role\": \"agent\"}}\n\n"
    )
    events = parse_sse_events(raw_sse)
    assert len(events) == 2
    assert events[0]["id"] == "1"
    assert events[1]["id"] == "2"


def test_get_gcloud_token_fallback(monkeypatch):
    """Assert get_gcloud_token uses ADC fallback if gcloud CLI fails."""
    import subprocess
    from scripts.run_canary_checks import get_gcloud_token

    def fake_subprocess_run(*a, **kw):
        raise FileNotFoundError("gcloud not found")

    monkeypatch.setattr(subprocess, "check_output", fake_subprocess_run)

    # Mock google.auth.default
    class FakeCreds:
        token = "mock-adc-token-123"
        def refresh(self, req):
            self.token = "refreshed-adc-token-456"

    import google.auth
    monkeypatch.setattr(google.auth, "default", lambda: (FakeCreds(), "test-project"))

    token = get_gcloud_token()
    assert token == "refreshed-adc-token-456"

