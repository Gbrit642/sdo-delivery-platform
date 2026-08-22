"""Unit tests for Cloud Run Google A2A v1.0 Protocol Contract.

Validates:
  1. Discovery Card endpoints (/a2a/app/.well-known/agent-card.json, /.well-known/agent-card.json).
  2. Strict Google A2A v1.0 schema invariants:
     - role == "agent" (NEVER "assistant")
     - parts is a List[Dict] with "text" key
     - messageId is non-empty string
     - contextId is non-empty string
     - artifacts is a typed List[Dict] (NEVER a dict)
  3. JSON-RPC 2.0 wrapper compliance (jsonrpc="2.0", matching id, result object).
  4. Server-Sent Events (SSE) streaming wire protocol (Content-Type: text/event-stream).
  5. Direct JSON fallback when Accept: application/json is sent without streaming.
  6. All 5 Wallbox domains and deployment deliverable cards.
  7. Zero terminal CLI commands in generated outputs.
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from web.app import app
from scripts.run_canary_checks import parse_sse_events


@pytest.fixture
def client() -> TestClient:
    """Fixture providing FastAPI TestClient."""
    return TestClient(app)


def test_agent_card_discovery_endpoints(client: TestClient):
    """Assert Agent Discovery Card is accessible across standard discovery paths."""
    discovery_routes = [
        "/a2a/app/.well-known/agent-card.json",
        "/.well-known/agent-card.json",
        "/a2a/app",
        "/a2a",
    ]
    for route in discovery_routes:
        resp = client.get(route)
        assert resp.status_code == 200, f"Discovery route {route} failed with HTTP {resp.status_code}"
        card = resp.json()
        assert card["name"] == "Wallbox SDO Delivery Platform"
        assert card["protocolVersion"] == "1.0"
        assert card["capabilities"]["streaming"] is True
        assert "skills" in card
        assert len(card["skills"]) >= 5
        skill_ids = [s["id"] for s in card["skills"]]
        assert "finance_variance" in skill_ids
        assert "sales_pipeline" in skill_ids
        assert "firmware_telemetry" in skill_ids
        assert "marketing_attribution" in skill_ids
        assert "logistics_turnover" in skill_ids


def test_a2a_jsonrpc_sse_streaming_execution_schema(client: TestClient):
    """Assert POST /a2a/app returns strict Google A2A v1.0 SSE stream."""
    req_id = "test-rpc-001"
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "sendMessage",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"text": "Generate weekly finance variance analytical view."}],
            }
        },
    }

    resp = client.post(
        "/a2a/app",
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
        json=payload,
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    raw_text = resp.text
    assert raw_text.startswith("event: message\ndata: ")

    events = parse_sse_events(raw_text)
    assert len(events) == 1

    event_payload = events[0]
    assert event_payload.get("jsonrpc") == "2.0"
    assert event_payload.get("id") == req_id
    assert "result" in event_payload

    result = event_payload["result"]

    # Invariant 1: role MUST be 'agent' (NEVER 'assistant')
    assert result["role"] == "agent"
    assert result["role"] != "assistant"

    # Invariant 2: parts MUST be a list of dicts with 'text'
    assert isinstance(result["parts"], list)
    assert len(result["parts"]) > 0
    assert "text" in result["parts"][0]
    assert len(result["parts"][0]["text"]) > 20

    # Invariant 3: messageId & contextId MUST be strings
    assert isinstance(result["messageId"], str)
    assert result["messageId"].startswith("msg-")
    assert isinstance(result["contextId"], str)
    assert result["contextId"].startswith("ctx-")

    # Invariant 4: artifacts MUST be a typed List[Dict] (NEVER a dict)
    assert isinstance(result["artifacts"], list)
    assert not isinstance(result["artifacts"], dict)
    if result["artifacts"]:
        assert "name" in result["artifacts"][0]
        assert "uri" in result["artifacts"][0]

    # Invariant 5: status / current_state present
    assert result["status"] == "WAIT_GATE_H1"
    assert result["current_state"] == "WAIT_GATE_H1"

    # Invariant 6: Zero CLI commands leaked
    text = result["parts"][0]["text"]
    for prohibited in ["gcloud ", "kubectl ", "docker run", "bash -c", "sudo "]:
        assert prohibited not in text


def test_a2a_direct_json_negotiation(client: TestClient):
    """Assert POST /a2a/app returns application/json when explicitly requested without streaming."""
    req_id = "test-rpc-json-002"
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "sendMessage",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"text": "Analyze sales CRM pipeline conversion."}],
            }
        },
    }

    resp = client.post(
        "/a2a/app",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
    )
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")

    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == req_id
    assert data["result"]["role"] == "agent"
    text = data["result"]["parts"][0]["text"]
    assert "sales" in text.lower() or "SALES" in text


def test_a2a_deploy_intent_deliverable_card(client: TestClient):
    """Assert deploy intent produces live web application deliverable card via A2A."""
    payload = {
        "jsonrpc": "2.0",
        "id": "deploy-turn-001",
        "method": "sendMessage",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"text": "Deploy hello world web app to Cloud Run"}],
            }
        },
    }

    resp = client.post("/a2a/app", json=payload)
    assert resp.status_code == 200
    events = parse_sse_events(resp.text)
    assert len(events) == 1
    text = events[0]["result"]["parts"][0]["text"]
    assert "Live Web Application" in text or "Live Web Application Deployed & Verified" in text
    assert "https://sdo-hello-world-demo-316329647160.us-central1.run.app" in text


@pytest.mark.parametrize("domain_query,expected_domain", [
    ("reconcile currency invoice EUR USD", "FINANCE"),
    ("sales CRM pipeline opportunities", "SALES"),
    ("charger firmware OCPP telemetry error", "FIRMWARE"),
    ("marketing CAC organic conversion", "MARKETING"),
    ("warehouse dispatch logistics stock turnover", "LOGISTICS"),
])
def test_a2a_all_domains_routing(client: TestClient, domain_query: str, expected_domain: str):
    """Assert A2A endpoint correctly routes and formats briefs for all 5 domains."""
    payload = {
        "jsonrpc": "2.0",
        "id": f"test-domain-{expected_domain.lower()}",
        "method": "sendMessage",
        "params": {"input": domain_query},
    }
    resp = client.post("/a2a/app", json=payload)
    assert resp.status_code == 200
    events = parse_sse_events(resp.text)
    assert len(events) == 1
    assert expected_domain in events[0]["result"]["parts"][0]["text"]


def test_a2a_payload_formats_flexibility(client: TestClient):
    """Assert A2A endpoint accepts various input payload shapes: query, input, text, dict."""
    # 1. Plain top-level 'input'
    resp1 = client.post("/a2a/app", json={"input": "Check finance invoices"})
    assert resp1.status_code == 200

    # 2. Plain top-level 'query'
    resp2 = client.post("/a2a/app", json={"query": "Check sales pipeline"})
    assert resp2.status_code == 200

    # 3. Plain top-level 'text'
    resp3 = client.post("/a2a/app", json={"text": "Check charger firmware"})
    assert resp3.status_code == 200

    # 4. Message dict with 'content'
    resp4 = client.post("/a2a/app", json={"message": {"content": "Check marketing campaigns"}})
    assert resp4.status_code == 200

    # 5. Message string
    resp5 = client.post("/a2a/app", json={"message": "Check logistics inventory"})
    assert resp5.status_code == 200
