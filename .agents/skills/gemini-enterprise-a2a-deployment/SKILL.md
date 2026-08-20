---
name: gemini-enterprise-a2a-deployment
description: >-
  Authoritative guide for building, wrapping, deploying, and troubleshooting
  custom agents connected to Gemini Enterprise via the Agent-to-Agent (A2A) protocol.
  Covers Server-Sent Events (SSE) streaming wire protocol, strict Google A2A v1.0
  Pydantic schema (role="agent", parts, messageId, typed artifacts list), content negotiation,
  agent discovery cards, IAM/IAP authentication, Cloud Run deployment, and debugging.
---

# Gemini Enterprise A2A (Agent-to-Agent) Deployment Guide

This skill provides the mandatory design patterns, wire protocol requirements, and troubleshooting solutions for building and deploying custom backend agents to **Gemini Enterprise** via the **Agent-to-Agent (A2A)** protocol.

---

## 1. How Gemini Enterprise A2A Works

Gemini Enterprise acts as a client that orchestrates conversations with external agents over HTTP:

```
+-----------------------------------------------------------------------------------------------+
| GEMINI ENTERPRISE CLIENT                                                                      |
+-----------------------------------------------------------------------------------------------+
       |                                              |
       | 1. Discovery (GET)                           | 2. Execution (POST Streaming)
       v                                              v
+-----------------------------------------------------------------------------------------------+
| A2A AGENT SERVICE (Cloud Run / GKE / FastAPI)                                                 |
| • GET  /.well-known/agent-card.json  --> Returns Agent Card JSON (Capabilities & Skills)       |
| • POST /.well-known/agent-card.json  --> Accepts JSON-RPC 2.0 request                         |
|                                          Streams SSE chunks (Content-Type: text/event-stream)   |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. The Golden Rules & Invariants of Gemini Enterprise A2A

Failure to adhere to these exact wire-level specifications will cause runtime HTTP 400, 405, or Pydantic validation errors in Gemini Enterprise:

### Invariant 1: Server-Sent Events (SSE) is Mandatory
- When invoking an agent, Gemini Enterprise sends `Accept: text/event-stream` and expects `Content-Type: text/event-stream; charset=utf-8`.
- Returning `application/json` causes:
  `HTTP Error 400: Invalid SSE response or protocol error: Expected response header Content-Type to contain 'text/event-stream'`

### Invariant 2: Strict Google A2A v1.0 Typed Schema
Gemini Enterprise validates every streamed SSE JSON chunk against internal Pydantic models (`SendStreamingMessageResponse`). The payload inside `result` **must strictly follow**:

| Field | Type | Requirement | Notes |
|---|---|---|---|
| **`role`** | `Enum` | **Must be `'agent'` or `'user'`** | ⚠️ **NEVER use `'assistant'`!** This is the #1 cause of 15-field Pydantic validation failures. |
| **`parts`** | `List[Dict]` | **Must be `[{"text": "..."}]`** | Never send a plain top-level string `content: "..."` without `parts`. |
| **`messageId`** | `String` | **Required** | Unique ID per message, e.g. `f"msg-{uuid.uuid4().hex[:12]}"`. |
| **`artifacts`** | `List[Dict]` | **Must be a typed List** | `[{"name": "...", "uri": "..."}]`. ⚠️ **Never use a dictionary** `{"key": "value"}`. |
| **`contextId`** | `String` | Recommended | Unique session or loop identifier, e.g. `f"ctx-{session_id}"`. |
| **`taskId`** | `String` | Recommended | Task tracking identifier. |

---

## 3. Reference FastAPI Implementation Template

Use this standard FastAPI implementation for any A2A agent:

```python
import json
import uuid
from typing import Any, Dict, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Gemini Enterprise A2A Agent")

# 1. Agent Discovery Card
AGENT_CARD = {
    "name": "Custom Enterprise Agent",
    "description": "Enterprise agent integrated with Gemini Enterprise via A2A.",
    "url": "https://your-cloud-run-service.run.app",
    "version": "1.0.0",
    "capabilities": {
        "streaming": True,
        "state_management": True,
    },
    "skills": [
        {
            "id": "analyze_data",
            "name": "Analyze Enterprise Data",
            "description": "Performs data extraction and synthesis.",
        }
    ],
}

# 2. Multi-Route A2A Handler (Handles both GET discovery and POST execution)
@app.api_route("/.well-known/agent-card.json", methods=["GET", "POST"])
@app.api_route("/a2a/app/.well-known/agent-card.json", methods=["GET", "POST"])
@app.api_route("/agent-card.json", methods=["GET", "POST"])
@app.api_route("/a2a/messages", methods=["POST"])
@app.api_route("/messages", methods=["POST"])
async def a2a_handler(request: Request):
    """Serve Agent Card on GET, or process and stream JSON-RPC execution on POST."""
    if request.method == "GET":
        return JSONResponse(content=AGENT_CARD)

    # Parse incoming request body
    try:
        body = await request.json()
    except Exception:
        body = {}

    req_id = body.get("id", str(uuid.uuid4()))
    params = body.get("params", {}) if isinstance(body.get("params"), dict) else {}
    
    # Extract user prompt
    user_text = ""
    if "message" in params and isinstance(params["message"], dict):
        msg = params["message"]
        if "parts" in msg and isinstance(msg["parts"], list) and msg["parts"]:
            user_text = msg["parts"][0].get("text", "")
        elif "content" in msg:
            user_text = msg["content"]
    elif "input" in body:
        user_text = body["input"]

    # Execute Agent Reasoning Logic
    session_id = uuid.uuid4().hex[:12]
    reply_text = f"Processed request: {user_text}"
    artifacts_list = [
        {"name": "output.md", "uri": "gs://my-bucket/processes/output.md"}
    ]

    # Build Strict Google A2A v1.0 Result Payload
    a2a_result = {
        "messageId": f"msg-{session_id}",
        "role": "agent",  # MUST BE 'agent', NOT 'assistant'
        "parts": [
            {
                "text": reply_text,
            }
        ],
        "contextId": f"ctx-{session_id}",
        "taskId": session_id,
        "id": session_id,
        "status": "COMPLETED",
        "artifacts": artifacts_list,  # MUST BE A LIST, NOT A DICT
        # Backward compatibility fields
        "content": reply_text,
        "text": reply_text,
        "messages": [
            {
                "role": "agent",
                "parts": [{"text": reply_text}],
                "content": reply_text,
            }
        ],
    }

    response_payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": a2a_result,
    }

    # Determine if client explicitly requests non-streaming JSON without SSE
    accept_header = request.headers.get("accept", "").lower()
    streaming_flag = (
        body.get("streaming") is True
        or body.get("stream") is True
        or params.get("streaming") is True
        or request.query_params.get("alt") == "sse"
    )
    explicit_json = (
        "application/json" in accept_header
        and "text/event-stream" not in accept_header
        and "*/*" not in accept_header
        and not streaming_flag
    )

    if explicit_json:
        return JSONResponse(content=response_payload)

    # Stream Server-Sent Events (SSE)
    async def sse_generator():
        data_str = json.dumps(response_payload)
        yield f"event: message\ndata: {data_str}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

---

## 4. Troubleshooting Reference Matrix

| Error Message in Gemini Enterprise | Root Cause | Solution |
|---|---|---|
| `HTTP Error 405: {"detail":"Method Not Allowed"}` | The discovery route only accepted `GET`. Gemini Enterprise sends `POST` directly to the card URI. | Add `POST` to `methods=["GET", "POST"]` on `/.well-known/agent-card.json`. |
| `HTTP Error 400: Invalid SSE response or protocol error: Expected response header Content-Type to contain 'text/event-stream', got 'application/json'` | Endpoint returned `JSONResponse` instead of SSE stream. | Wrap output in `StreamingResponse(..., media_type="text/event-stream")` yielding `event: message\ndata: {...}\n\n`. |
| `15 validation errors for SendStreamingMessageResponse` / `role: Input should be 'agent' or 'user'` | Response contained `"role": "assistant"`, missing `parts`, or dictionary `artifacts`. | Set `"role": "agent"`, `"parts": [{"text": ...}]`, `"messageId": ...`, and `"artifacts": [{"name": ..., "uri": ...}]`. |
| `HTTP 401 / 403 Forbidden` | Ingress IAM requires authenticated invoker credentials. | Ensure Cloud Run service account has `roles/run.invoker` or configure IAP Load Balancer with OIDC delegation headers. |

---

## 5. Verification Commands

### Test 1: Verify Discovery Card (GET)
```bash
curl -s -i "https://YOUR_SERVICE_URL/.well-known/agent-card.json"
```
*Expected: HTTP 200 with JSON card declaring `"capabilities": {"streaming": true}`.*

### Test 2: Verify Server-Sent Events (POST)
```bash
curl -i -X POST "https://YOUR_SERVICE_URL/.well-known/agent-card.json" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"jsonrpc":"2.0","id":"test-1","method":"message/send","params":{"message":{"role":"user","content":"Hello"}}}'
```
*Expected:*
- `HTTP/2 200`
- `Content-Type: text/event-stream; charset=utf-8`
- `event: message`
- `data: {"jsonrpc":"2.0","result":{"messageId":"...","role":"agent","parts":[{"text":"..."}]}}`
