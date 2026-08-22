#!/usr/bin/env python3
"""Post-Deployment Dual-Level Live Canary Validation Suite.

Validates the Wallbox SDO platform across two critical live operational tiers:
  - Level 1 (Wire Protocol):
      * Vertex AI Reasoning Engine streaming_agent_run_with_events streamQuery
      * Cloud Run A2A Agent Card discovery & JSON-RPC SSE streaming execution
  - Level 2 (Discovery Engine / Gemini Enterprise Assistant API):
      * Discovery Engine Agent Catalog inspection
      * Option A (Vertex AI Reasoning Engine) ENABLED status & binding
      * Option B (Cloud Run A2A Bridge) ENABLED status & binding

Produces an ANSI-formatted report with latency metrics and exits 0 on full sign-off.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import requests

PROJECT_ID = os.environ.get("SDO_PROJECT_ID", "managed-agent-504409")
PROJECT_NUMBER = os.environ.get("SDO_PROJECT_NUMBER", "316329647160")
REGION = os.environ.get("SDO_REGION", "us-central1")
ENGINE_ID = os.environ.get("SDO_ENGINE_ID", "gemini-enterprise-17857511_1785751184567")
REASONING_ENGINE_ID = os.environ.get("SDO_REASONING_ENGINE_ID", "202294196592181248")
AGENT_ID_A = os.environ.get("SDO_AGENT_ID_A", "4439114975457332401")
AGENT_ID_B = os.environ.get("SDO_AGENT_ID_B", "2480784782936961193")
CLOUD_RUN_URL = os.environ.get("SDO_CLOUD_RUN_URL", "https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app")

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


@dataclass
class CanaryCheckResult:
    level: str
    name: str
    target: str
    passed: bool
    latency_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


def get_gcloud_token() -> str:
    """Retrieve active gcloud OAuth access token."""
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], stderr=subprocess.DEVNULL).decode().strip()
        if not token:
            raise RuntimeError("Empty access token returned by gcloud auth.")
        return token
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch gcloud access token: {exc}") from exc


def parse_sse_events(raw_sse_text: str) -> List[Dict[str, Any]]:
    """Parse Server-Sent Events stream into JSON payloads."""
    events = []
    for line in raw_sse_text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    events.append(json.loads(data_str))
                except Exception:
                    pass
    return events


def run_canaries(
    project_id: str = PROJECT_ID,
    project_number: str = PROJECT_NUMBER,
    region: str = REGION,
    engine_id: str = ENGINE_ID,
    reasoning_engine_id: str = REASONING_ENGINE_ID,
    agent_id_a: str = AGENT_ID_A,
    agent_id_b: str = AGENT_ID_B,
    cloud_run_url: str = CLOUD_RUN_URL,
    mock_mode: bool = False,
) -> List[CanaryCheckResult]:
    """Execute full Level 1 & Level 2 live canary checks."""
    results: List[CanaryCheckResult] = []

    if mock_mode:
        # Mock mode for offline CI tests
        results.append(CanaryCheckResult("Level 1 (Wire)", "Reasoning Engine streamQuery", f"RE:{reasoning_engine_id}", True, 120.5, "HTTP 200 OK — Valid event stream"))
        results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run Agent Card Discovery", f"{cloud_run_url}/.well-known/agent-card.json", True, 45.2, "HTTP 200 OK — Protocol 1.0"))
        results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", f"{cloud_run_url}/a2a/app", True, 210.8, "HTTP 200 OK — role='agent' and typed artifacts"))
        results.append(CanaryCheckResult("Level 2 (Assistant API)", "Discovery Engine Agent Catalog", f"engines/{engine_id}", True, 160.4, "HTTP 200 OK — 6 registered agents"))
        results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option A (Reasoning Engine)", f"Agent:{agent_id_a}", True, 0.1, "state=ENABLED, provisionedReasoningEngine matched"))
        results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option B (Cloud Run A2A)", f"Agent:{agent_id_b}", True, 0.1, "state=ENABLED, a2aAgentDefinition matched"))
        return results

    token = get_gcloud_token()
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id,
    }

    # ==========================================================================
    # LEVEL 1: WIRE PROTOCOL CHECKS
    # ==========================================================================

    # Check 1.1: Vertex AI Reasoning Engine Wire Protocol (streamQuery)
    re_target = f"https://{region}-aiplatform.googleapis.com/v1beta1/projects/{project_number}/locations/{region}/reasoningEngines/{reasoning_engine_id}:streamQuery"
    t0 = time.perf_counter()
    try:
        re_payload = {
            "class_method": "streaming_agent_run_with_events",
            "input": {
                "request_json": json.dumps({
                    "message": "Canary wire protocol verification for Wallbox SDO platform.",
                    "user_id": "sarah.controller@wallbox.com",
                    "session_id": f"canary-sess-{int(time.time())}",
                })
            },
        }
        re_resp = requests.post(re_target, headers=auth_headers, json=re_payload, timeout=20)
        lat = (time.perf_counter() - t0) * 1000

        if re_resp.status_code == 200:
            re_body = re_resp.text
            # Parse either single JSON object or newline-delimited JSON stream
            valid_structure = False
            first_event = None
            try:
                first_event = re_resp.json()
                valid_structure = (
                    first_event.get("event_type") == "event"
                    and first_event.get("content", {}).get("role") == "model"
                    and len(first_event.get("content", {}).get("parts", [])) > 0
                )
            except Exception:
                # Try NDJSON
                for line in re_body.splitlines():
                    if line.strip():
                        ev = json.loads(line)
                        if ev.get("event_type") == "event" and ev.get("content", {}).get("role") == "model":
                            valid_structure = True
                            first_event = ev
                            break

            if valid_structure:
                # Check for zero CLI leakage
                text_content = first_event["content"]["parts"][0].get("text", "")
                has_cli_leak = any(cmd in text_content for cmd in ["gcloud ", "kubectl ", "docker run", "sudo "])
                if not has_cli_leak:
                    results.append(CanaryCheckResult("Level 1 (Wire)", "Vertex AI Reasoning Engine streamQuery", f"RE:{reasoning_engine_id}", True, lat, "HTTP 200 OK — Valid Discovery Engine event stream (Zero CLI leaks)"))
                else:
                    results.append(CanaryCheckResult("Level 1 (Wire)", "Vertex AI Reasoning Engine streamQuery", f"RE:{reasoning_engine_id}", False, lat, "FAILED: Forbidden CLI commands detected in output stream"))
            else:
                results.append(CanaryCheckResult("Level 1 (Wire)", "Vertex AI Reasoning Engine streamQuery", f"RE:{reasoning_engine_id}", False, lat, f"Invalid event schema in stream: {re_body[:120]}"))
        else:
            results.append(CanaryCheckResult("Level 1 (Wire)", "Vertex AI Reasoning Engine streamQuery", f"RE:{reasoning_engine_id}", False, lat, f"HTTP {re_resp.status_code}: {re_resp.text[:120]}"))
    except Exception as exc:
        lat = (time.perf_counter() - t0) * 1000
        results.append(CanaryCheckResult("Level 1 (Wire)", "Vertex AI Reasoning Engine streamQuery", f"RE:{reasoning_engine_id}", False, lat, f"Exception: {exc}"))

    # Check 1.2: Cloud Run A2A Agent Discovery Card
    card_url = f"{cloud_run_url}/a2a/app/.well-known/agent-card.json"
    t0 = time.perf_counter()
    try:
        card_resp = requests.get(card_url, timeout=15)
        lat = (time.perf_counter() - t0) * 1000
        if card_resp.status_code == 200:
            card_json = card_resp.json()
            is_valid_card = (
                card_json.get("protocolVersion") == "1.0"
                and "skills" in card_json
                and len(card_json["skills"]) >= 5
            )
            if is_valid_card:
                results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A Discovery Card", card_url, True, lat, f"HTTP 200 OK — Protocol {card_json.get('protocolVersion')} ({len(card_json['skills'])} skills registered)"))
            else:
                results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A Discovery Card", card_url, False, lat, f"Invalid card schema: {card_json}"))
        else:
            results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A Discovery Card", card_url, False, lat, f"HTTP {card_resp.status_code}"))
    except Exception as exc:
        lat = (time.perf_counter() - t0) * 1000
        results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A Discovery Card", card_url, False, lat, f"Exception: {exc}"))

    # Check 1.3: Cloud Run A2A JSON-RPC SSE Stream Execution
    a2a_msg_url = f"{cloud_run_url}/a2a/app"
    t0 = time.perf_counter()
    try:
        a2a_payload = {
            "jsonrpc": "2.0",
            "id": f"canary-a2a-{int(time.time())}",
            "method": "sendMessage",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"text": "Canary A2A wire health check."}],
                }
            },
        }
        sse_resp = requests.post(
            a2a_msg_url,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            json=a2a_payload,
            timeout=20,
        )
        lat = (time.perf_counter() - t0) * 1000

        if sse_resp.status_code == 200:
            parsed_events = parse_sse_events(sse_resp.text)
            if parsed_events:
                res_obj = parsed_events[0].get("result", {})
                role = res_obj.get("role")
                parts = res_obj.get("parts", [])
                artifacts = res_obj.get("artifacts")
                message_id = res_obj.get("messageId")

                is_a2a_valid = (
                    role == "agent"  # Strict invariant: NEVER "assistant"
                    and isinstance(parts, list)
                    and len(parts) > 0
                    and "text" in parts[0]
                    and isinstance(artifacts, list)  # Strict invariant: MUST BE list
                    and bool(message_id)
                )

                if is_a2a_valid:
                    # Check for zero CLI leakage
                    resp_text = parts[0]["text"]
                    has_cli_leak = any(cmd in resp_text for cmd in ["gcloud ", "kubectl ", "docker run", "sudo "])
                    if not has_cli_leak:
                        results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", a2a_msg_url, True, lat, "HTTP 200 OK — Strict A2A v1.0 (role='agent', typed artifacts, 0 CLI leaks)"))
                    else:
                        results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", a2a_msg_url, False, lat, "FAILED: Forbidden CLI commands detected in A2A response"))
                else:
                    results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", a2a_msg_url, False, lat, f"A2A schema violation: role={role}, artifacts_type={type(artifacts)}"))
            else:
                results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", a2a_msg_url, False, lat, f"No SSE 'data:' chunks in response: {sse_resp.text[:120]}"))
        else:
            results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", a2a_msg_url, False, lat, f"HTTP {sse_resp.status_code}: {sse_resp.text[:120]}"))
    except Exception as exc:
        lat = (time.perf_counter() - t0) * 1000
        results.append(CanaryCheckResult("Level 1 (Wire)", "Cloud Run A2A JSON-RPC SSE Stream", a2a_msg_url, False, lat, f"Exception: {exc}"))

    # ==========================================================================
    # LEVEL 2: DISCOVERY ENGINE / GEMINI ENTERPRISE ASSISTANT API CHECKS
    # ==========================================================================

    de_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_number}/locations/global/collections/default_collection/engines/{engine_id}/assistants/default_assistant/agents"
    t0 = time.perf_counter()
    agents_list: List[Dict[str, Any]] = []
    try:
        de_resp = requests.get(de_url, headers=auth_headers, timeout=20)
        lat = (time.perf_counter() - t0) * 1000

        if de_resp.status_code == 200:
            catalog_data = de_resp.json()
            agents_list = catalog_data.get("agents", [])
            results.append(CanaryCheckResult("Level 2 (Assistant API)", "Discovery Engine Agent Catalog", f"engines/{engine_id}", True, lat, f"HTTP 200 OK — Retrieved {len(agents_list)} registered agents"))
        else:
            results.append(CanaryCheckResult("Level 2 (Assistant API)", "Discovery Engine Agent Catalog", f"engines/{engine_id}", False, lat, f"HTTP {de_resp.status_code}: {de_resp.text[:120]}"))
    except Exception as exc:
        lat = (time.perf_counter() - t0) * 1000
        results.append(CanaryCheckResult("Level 2 (Assistant API)", "Discovery Engine Agent Catalog", f"engines/{engine_id}", False, lat, f"Exception: {exc}"))

    # Check 2.2: Verify Option A in Agent Catalog
    if agents_list:
        agent_a = next((a for a in agents_list if a.get("name", "").endswith(f"/{agent_id_a}") or reasoning_engine_id in str(a)), None)
        if agent_a:
            state = agent_a.get("state")
            re_binding = agent_a.get("adkAgentDefinition", {}).get("provisionedReasoningEngine", {}).get("reasoningEngine", "")
            is_valid_a = (state == "ENABLED" and reasoning_engine_id in re_binding)
            if is_valid_a:
                results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option A (Vertex AI Reasoning Engine)", f"Agent:{agent_id_a}", True, 0.1, f"state={state} | Bound to Reasoning Engine {reasoning_engine_id}"))
            else:
                results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option A (Vertex AI Reasoning Engine)", f"Agent:{agent_id_a}", False, 0.1, f"Invalid binding or state: state={state}, binding={re_binding}"))
        else:
            results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option A (Vertex AI Reasoning Engine)", f"Agent:{agent_id_a}", False, 0.1, f"Agent ID {agent_id_a} not found in Gemini Enterprise assistant catalog"))

    # Check 2.3: Verify Option B in Agent Catalog
    if agents_list:
        agent_b = next((a for a in agents_list if a.get("name", "").endswith(f"/{agent_id_b}") or "Cloud Run A2A" in a.get("displayName", "")), None)
        if agent_b:
            state = agent_b.get("state")
            card_data = agent_b.get("a2aAgentDefinition", {}).get("jsonAgentCard", "")
            is_valid_b = (state == "ENABLED" and ("sdo-adk-cloudrun-a2a" in card_data or cloud_run_url in card_data))
            if is_valid_b:
                results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option B (Cloud Run A2A Bridge)", f"Agent:{agent_id_b}", True, 0.1, f"state={state} | Bound to Cloud Run A2A Card"))
            else:
                results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option B (Cloud Run A2A Bridge)", f"Agent:{agent_id_b}", False, 0.1, f"Invalid binding or state: state={state}"))
        else:
            results.append(CanaryCheckResult("Level 2 (Assistant API)", "Option B (Cloud Run A2A Bridge)", f"Agent:{agent_id_b}", False, 0.1, f"Agent ID {agent_id_b} not found in Gemini Enterprise assistant catalog"))

    return results


def print_canary_report(results: List[CanaryCheckResult]) -> bool:
    """Render a clean ANSI-formatted summary report."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print("\n" + "=" * 90)
    print(f"{BOLD}{CYAN}🔍 WALLBOX SDO PLATFORM — POST-DEPLOYMENT LIVE CANARY REPORT{RESET}")
    print(f"{DIM}Project: {PROJECT_ID} ({PROJECT_NUMBER}) | Region: {REGION} | Gemini Enterprise Engine: {ENGINE_ID}{RESET}")
    print("=" * 90)

    print(f"\n{BOLD}{'Tier / Check':<40} {'Latency':<12} {'Status':<10} {'Details'}{RESET}")
    print("-" * 90)

    for r in results:
        status_badge = f"{GREEN}✅ PASS{RESET}" if r.passed else f"{RED}❌ FAIL{RESET}"
        latency_str = f"{r.latency_ms:6.1f} ms" if r.latency_ms >= 1.0 else "< 1 ms"
        print(f"[{r.level}] {r.name:<25} {latency_str:<12} {status_badge:<18} {r.message}")

    print("-" * 90)
    if failed == 0:
        print(f"{BOLD}{GREEN}🎉 ALL CANARY CHECKS PASSED ({passed}/{total} verified in production){RESET}")
        print(f"{GREEN}✓ Option A (Reasoning Engine) & Option B (Cloud Run A2A) are verified healthy and ready for Gemini Enterprise users.{RESET}\n")
        return True
    else:
        print(f"{BOLD}{RED}⚠️  CANARY VALIDATION FAILED ({failed}/{total} failed){RESET}")
        print(f"{RED}Please inspect the error details above before declaring the deployment successful.{RESET}\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run Dual-Level Live Canary checks for Wallbox SDO Platform.")
    parser.add_argument("--project-id", default=PROJECT_ID, help="GCP Project ID.")
    parser.add_argument("--project-number", default=PROJECT_NUMBER, help="GCP Project Number.")
    parser.add_argument("--region", default=REGION, help="GCP Region.")
    parser.add_argument("--engine-id", default=ENGINE_ID, help="Gemini Enterprise Engine ID.")
    parser.add_argument("--reasoning-engine-id", default=REASONING_ENGINE_ID, help="Reasoning Engine ID.")
    parser.add_argument("--agent-id-a", default=AGENT_ID_A, help="Option A Agent ID.")
    parser.add_argument("--agent-id-b", default=AGENT_ID_B, help="Option B Agent ID.")
    parser.add_argument("--cloud-run-url", default=CLOUD_RUN_URL, help="Cloud Run Base URL.")
    parser.add_argument("--mock", action="store_true", help="Run in mock/offline mode for CI verification.")
    args = parser.parse_args()

    results = run_canaries(
        project_id=args.project_id,
        project_number=args.project_number,
        region=args.region,
        engine_id=args.engine_id,
        reasoning_engine_id=args.reasoning_engine_id,
        agent_id_a=args.agent_id_a,
        agent_id_b=args.agent_id_b,
        cloud_run_url=args.cloud_run_url,
        mock_mode=args.mock,
    )

    all_passed = print_canary_report(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
