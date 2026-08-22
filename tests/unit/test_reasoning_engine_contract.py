"""Unit tests for Vertex AI Reasoning Engine Gemini Enterprise Protocol Contract.

Validates:
  1. register_operations() declares streaming_agent_run_with_events and stream_query.
  2. streaming_agent_run_with_events handles raw JSON string and dictionary inputs.
  3. Streamed output conforms strictly to Discovery Engine schema:
     - event_type == "event"
     - content.role == "model"
     - content.parts is a list of [{"text": ...}]
  4. Session management methods (create_session, get_session, list_sessions, delete_session).
  5. Local cloudpickle roundtrip serialization and execution turns.
  6. Zero terminal CLI commands in business output.
  7. Pre-flight serialization gate execution.
"""

from __future__ import annotations

import json
import pytest
import cloudpickle
from scripts.deploy_reasoning_engine import (
    SDOAgentRuntimeEngine,
    run_preflight_serialization_check,
    ensure_py312_environment,
)


@pytest.fixture
def engine() -> SDOAgentRuntimeEngine:
    """Fixture providing initialized SDOAgentRuntimeEngine instance."""
    eng = SDOAgentRuntimeEngine(
        project_id="managed-agent-504409",
        project_number="316329647160",
        location="us-central1",
        model="gemini-3.7-flash",
    )
    eng.set_up()
    return eng


def test_register_operations_contract(engine: SDOAgentRuntimeEngine):
    """Assert register_operations() declares required streaming operations."""
    ops = engine.register_operations()
    assert isinstance(ops, dict)
    assert "stream" in ops
    assert "streaming_agent_run_with_events" in ops["stream"]
    assert "stream_query" in ops["stream"]
    assert "async_stream" in ops
    assert "async_streaming_agent_run_with_events" in ops["async_stream"]
    assert "async_stream_query" in ops["async_stream"]


def test_streaming_agent_run_with_events_raw_json_string(engine: SDOAgentRuntimeEngine):
    """Test streaming execution with raw JSON string input as sent by Gemini Enterprise."""
    raw_payload = json.dumps({
        "message": "Please generate weekly revenue variance report for Finance.",
        "user_id": "sarah.controller@wallbox.com",
        "session_id": "sess-discovery-001",
    })

    events = list(engine.streaming_agent_run_with_events(raw_payload))
    assert len(events) >= 1

    event = events[0]
    assert event["event_type"] == "event"
    assert "content" in event
    assert event["content"]["role"] == "model"
    assert isinstance(event["content"]["parts"], list)
    assert len(event["content"]["parts"]) > 0
    assert "text" in event["content"]["parts"][0]
    assert event["session_id"] == "sess-discovery-001"

    text = event["content"]["parts"][0]["text"]
    assert "Finance Domain" in text
    assert "Direct Connector Automation" in text
    # Invariant: Zero CLI commands in output
    for prohibited in ["gcloud ", "kubectl ", "docker run", "bash -c", "sudo "]:
        assert prohibited not in text


def test_streaming_agent_run_with_events_dict_input(engine: SDOAgentRuntimeEngine):
    """Test streaming execution with Python dict input."""
    dict_payload = {
        "message": "Analyze sales opportunity pipeline conversion rates.",
        "user_id": "sales.lead@wallbox.com",
    }
    events = list(engine.streaming_agent_run_with_events(dict_payload))
    assert len(events) >= 1
    event = events[0]
    assert event["event_type"] == "event"
    assert event["content"]["role"] == "model"
    assert "Sales Domain" in event["content"]["parts"][0]["text"]


def test_streaming_agent_run_with_events_deploy_intent(engine: SDOAgentRuntimeEngine):
    """Test streaming execution with deploy intent generating deliverable cards."""
    dict_payload = {
        "message": "Deploy Cloud Run hello world demo web app",
        "user_id": "sarah.controller@wallbox.com",
    }
    events = list(engine.streaming_agent_run_with_events(dict_payload))
    assert len(events) >= 1
    text = events[0]["content"]["parts"][0]["text"]
    assert "Live Web Application Deployed & Verified" in text
    assert "https://sdo-hello-world-demo-316329647160.us-central1.run.app" in text


@pytest.mark.parametrize("domain_term,expected_domain", [
    ("invoice variance reconciliation", "Finance"),
    ("sales CRM pipeline forecast", "Sales"),
    ("charger firmware telemetry logs", "Firmware"),
    ("marketing CAC campaign attribution", "Marketing"),
    ("warehouse logistics inventory turnover", "Logistics"),
])
def test_streaming_all_domains(engine: SDOAgentRuntimeEngine, domain_term: str, expected_domain: str):
    """Test streaming turn across all 5 Wallbox business domains."""
    events = list(engine.streaming_agent_run_with_events(json.dumps({"message": domain_term})))
    assert len(events) >= 1
    assert expected_domain in events[0]["content"]["parts"][0]["text"]


def test_session_lifecycle_methods(engine: SDOAgentRuntimeEngine):
    """Test session creation, retrieval, listing, and deletion."""
    user = "sarah.controller@wallbox.com"
    # 1. Create Session
    s1 = engine.create_session(user_id=user, session_id="s-custom-01")
    assert s1["id"] == "s-custom-01"
    assert s1["user_id"] == user

    # 2. Get Session
    s1_get = engine.get_session(user_id=user, session_id="s-custom-01")
    assert s1_get["id"] == "s-custom-01"

    # 3. List Sessions
    s_list = engine.list_sessions(user_id=user)
    assert len(s_list) >= 1
    assert any(s["id"] == "s-custom-01" for s in s_list)

    # 4. Delete Session
    del_res = engine.delete_session(user_id=user, session_id="s-custom-01")
    assert del_res["status"] == "deleted"
    assert del_res["session_id"] == "s-custom-01"


def test_query_and_stream_query_methods(engine: SDOAgentRuntimeEngine):
    """Test synchronous query and generator stream_query methods."""
    # Synchronous query
    q_res = engine.query("Check firmware telemetry")
    assert q_res["model_version"] == "gemini-3.7-flash"
    assert q_res["content"]["role"] == "model"
    assert "Firmware" in q_res["content"]["parts"][0]["text"]

    # Streaming query
    sq_events = list(engine.stream_query("Check marketing campaigns"))
    assert len(sq_events) >= 1
    assert sq_events[0]["content"]["role"] == "model"
    assert "Marketing" in sq_events[0]["content"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_async_streaming_methods(engine: SDOAgentRuntimeEngine):
    """Test async streaming operations."""
    async_events = []
    async for ev in engine.async_streaming_agent_run_with_events({"message": "Finance report"}):
        async_events.append(ev)
    assert len(async_events) >= 1
    assert async_events[0]["event_type"] == "event"

    sq_async_events = []
    async for ev in engine.async_stream_query("Finance report"):
        sq_async_events.append(ev)
    assert len(sq_async_events) >= 1
    assert sq_async_events[0]["content"]["role"] == "model"


def test_cloudpickle_roundtrip_serialization(engine: SDOAgentRuntimeEngine):
    """Test that SDOAgentRuntimeEngine pickles, unpickles, and runs turns without degradation."""
    # Serialize
    pickled_data = cloudpickle.dumps(engine)
    assert isinstance(pickled_data, bytes)
    assert len(pickled_data) > 0

    # Deserialize
    unpickled: SDOAgentRuntimeEngine = cloudpickle.loads(pickled_data)
    assert isinstance(unpickled, SDOAgentRuntimeEngine)
    assert unpickled.model == "gemini-3.7-flash"

    # Execute conversational turn on unpickled engine
    events = list(unpickled.streaming_agent_run_with_events(
        json.dumps({"message": "Reconcile currency variances", "user_id": "sarah.controller@wallbox.com"})
    ))
    assert len(events) >= 1
    assert events[0]["event_type"] == "event"
    assert "Finance Domain" in events[0]["content"]["parts"][0]["text"]


def test_preflight_serialization_check_gate_function():
    """Test that run_preflight_serialization_check() passes on valid engine."""
    result = run_preflight_serialization_check()
    assert result["status"] == "PASSED"
    assert result["serialized_bytes"] > 0
    assert result["test_turn_response_length"] > 0


def test_preflight_serialization_check_detects_bad_engine():
    """Test that run_preflight_serialization_check() raises RuntimeError on invalid engine."""
    class BrokenEngine:
        def register_operations(self):
            return {}

    with pytest.raises(RuntimeError, match="Pre-Flight Serialization Gate FAILED"):
        run_preflight_serialization_check(BrokenEngine())  # type: ignore


def test_edge_cases_inputs(engine: SDOAgentRuntimeEngine):
    """Test edge case inputs: empty JSON, malformed string, nested dict parts."""
    # Empty string
    e1 = list(engine.streaming_agent_run_with_events(""))
    assert len(e1) >= 1

    # Empty JSON object
    e2 = list(engine.streaming_agent_run_with_events("{}"))
    assert len(e2) >= 1

    # Malformed non-JSON string
    e3 = list(engine.streaming_agent_run_with_events("not a json string at all"))
    assert len(e3) >= 1

    # Nested parts structure
    e4 = list(engine.streaming_agent_run_with_events({
        "message": {"parts": [{"text": "logistics warehouse SLA"}]}
    }))
    assert len(e4) >= 1
    assert "Logistics" in e4[0]["content"]["parts"][0]["text"]
