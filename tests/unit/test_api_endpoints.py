"""FastAPI REST API & Webhook Ingress Unit Tests."""

import pytest
from fastapi.testclient import TestClient
from web.app import app


@pytest.fixture
def client() -> TestClient:
    """Fixture providing FastAPI TestClient."""
    return TestClient(app)


def test_healthz_endpoint(client: TestClient):
    """GET /healthz returns 200 OK with GCP metadata."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["project_id"] == "managed-agent-504409"
    assert data["model"] == "gemini-3.7-flash"


def test_create_and_resolve_loop_api_flow(client: TestClient):
    """Test full loop creation and dual-gate resolution via REST API."""
    # 1. Create Loop
    create_resp = client.post(
        "/api/v1/loops",
        json={
            "node_id": "finance",
            "brief_text": "Create currency variance analysis view.",
            "owner_email": "sarah.controller@wallbox.com",
            "roles": ["financial_controller"],
            "department": "Finance",
        },
    )
    assert create_resp.status_code == 201
    loop_data = create_resp.json()
    loop_id = loop_data["loop_id"]
    assert loop_data["current_state"] == "WAIT_GATE_H1"
    assert loop_data["spec_content"] is not None

    # 2. Get Loop
    get_resp = client.get(f"/api/v1/loops/{loop_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["loop_id"] == loop_id

    # 3. Resolve Gate H1
    h1_resp = client.post(
        f"/api/v1/loops/{loop_id}/gates/h1/resolve",
        json={
            "decision": "approve",
            "comment": "Spec looks great.",
            "actor_email": "sarah.controller@wallbox.com",
        },
    )
    assert h1_resp.status_code == 200
    h1_data = h1_resp.json()
    assert h1_data["current_state"] == "WAIT_GATE_H2"
    assert "transform.py" in h1_data["code_artifacts"]

    # 4. Resolve Gate H2
    h2_resp = client.post(
        f"/api/v1/loops/{loop_id}/gates/h2/resolve",
        json={
            "decision": "approve",
            "comment": "Sandbox tests passed 100%. Approved for merge.",
            "actor_email": "sarah.controller@wallbox.com",
        },
    )
    assert h2_resp.status_code == 200
    h2_data = h2_resp.json()
    assert h2_data["current_state"] == "DONE"
    assert h2_data["close_commit_hash"] is not None


def test_dashboard_endpoint(client: TestClient):
    """GET / returns 200 OK with HTML dashboard."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SDO" in resp.text


@pytest.mark.parametrize("domain,email", [
    ("finance", "sarah.controller@wallbox.com"),
    ("sales", "sales.lead@wallbox.com"),
    ("firmware", "firmware.eng@wallbox.com"),
    ("marketing", "growth.lead@wallbox.com"),
    ("logistics", "supply.lead@wallbox.com"),
])
def test_create_and_resolve_all_domains_api_flow(client: TestClient, domain: str, email: str):
    """Test full loop creation and dual-gate resolution for all 5 domains via REST API without manual role passing."""
    # 1. Create Loop without explicit roles
    create_resp = client.post(
        "/api/v1/loops",
        json={
            "node_id": domain,
            "brief_text": f"Automated test deliverable brief for {domain}.",
            "owner_email": email,
        },
    )
    assert create_resp.status_code == 201
    loop_data = create_resp.json()
    loop_id = loop_data["loop_id"]
    assert loop_data["current_state"] == "WAIT_GATE_H1"
    assert loop_data["spec_content"] is not None

    # 2. Resolve Gate H1
    h1_resp = client.post(
        f"/api/v1/loops/{loop_id}/gates/h1/resolve",
        json={
            "decision": "approve",
            "comment": f"Spec approved for {domain}.",
            "actor_email": email,
        },
    )
    assert h1_resp.status_code == 200
    h1_data = h1_resp.json()
    assert h1_data["current_state"] == "WAIT_GATE_H2"

    # 3. Resolve Gate H2
    h2_resp = client.post(
        f"/api/v1/loops/{loop_id}/gates/h2/resolve",
        json={
            "decision": "approve",
            "comment": f"Merge approved for {domain}.",
            "actor_email": email,
        },
    )
    assert h2_resp.status_code == 200
    h2_data = h2_resp.json()
    assert h2_data["current_state"] == "DONE"
    assert h2_data["close_commit_hash"] is not None
    assert h2_data["worm_audit_record_id"] is not None


def test_chat_webhook_flow(client: TestClient):
    """Test Google Chat Webhook message reception and card click response."""
    msg_resp = client.post(
        "/api/v1/chat/webhook",
        json={
            "type": "MESSAGE",
            "message": {
                "text": "Automated billing brief for finance.",
                "sender": {"email": "sarah.controller@wallbox.com"},
            },
        },
    )
    assert msg_resp.status_code == 200
    card_data = msg_resp.json()
    assert "cardsV2" in card_data


def test_a2a_discovery_and_message_flow(client: TestClient):
    """Test A2A Agent Card GET, JSON-RPC message execution POST, and SSE streaming from Gemini Enterprise."""
    # 1. Test Agent Card GET
    card_resp = client.get("/a2a/app/.well-known/agent-card.json")
    assert card_resp.status_code == 200
    card = card_resp.json()
    assert "name" in card
    assert "skills" in card
    assert card["capabilities"]["streaming"] is True

    # 2. Test A2A Non-Streaming JSON POST (Accept: application/json)
    rpc_resp = client.post(
        "/a2a/app/.well-known/agent-card.json",
        headers={"Accept": "application/json"},
        json={
            "jsonrpc": "2.0",
            "id": "gemini-ent-msg-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "content": "Create a financial revenue variance view in BigQuery.",
                }
            },
        },
    )
    assert rpc_resp.status_code == 200
    assert "application/json" in rpc_resp.headers["content-type"]
    rpc_data = rpc_resp.json()
    assert "result" in rpc_data
    assert rpc_data["result"]["role"] == "assistant"
    assert "Autonomous SDO Platform" in rpc_data["result"]["content"]
    assert "WAIT_GATE_H1" in rpc_data["result"]["content"]

    # 3. Test A2A SSE Streaming POST (Accept: text/event-stream)
    sse_resp = client.post(
        "/a2a/app/.well-known/agent-card.json",
        headers={"Accept": "text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": "gemini-ent-msg-stream-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "content": "Create a financial revenue variance view in BigQuery.",
                }
            },
        },
    )
    assert sse_resp.status_code == 200
    assert "text/event-stream" in sse_resp.headers["content-type"]
    sse_text = sse_resp.text
    assert "event: message" in sse_text
    assert "data: {" in sse_text
    assert "Autonomous SDO Platform" in sse_text
    assert "WAIT_GATE_H1" in sse_text

    # 4. Test Root POST endpoint (A2A forward on /)
    root_post_resp = client.post(
        "/",
        headers={"Accept": "text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": "root-post-msg-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "content": "Build marketing multi-touch attribution pipeline.",
                }
            },
        },
    )
    assert root_post_resp.status_code == 200
    assert "text/event-stream" in root_post_resp.headers["content-type"]
    assert "MARKETING" in root_post_resp.text
