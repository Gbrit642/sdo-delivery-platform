#!/usr/bin/env python3
"""Direct Gemini Enterprise Agent Registrar using active gcloud authorization."""

import json
import subprocess
import requests

PROJECT_ID = "managed-agent-504409"
PROJECT_NUMBER = "316329647160"
ENGINE_ID = "gemini-enterprise-17857511_1785751184567"
LOCATION = "global"
COLLECTION = "default_collection"

# 1. Fetch access token from gcloud
token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "X-Goog-User-Project": PROJECT_ID,
}

base_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_NUMBER}/locations/{LOCATION}/collections/{COLLECTION}/engines/{ENGINE_ID}/assistants/default_assistant/agents"

# ------------------------------------------------------------------------------
# 1. OPTION A: Register Cloud Run A2A Agent
# ------------------------------------------------------------------------------
print("\n==============================================================================")
print("📦 Registering OPTION A: Cloud Run A2A Agent with Gemini Enterprise")
print("==============================================================================")

agent_card_url = "https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app/a2a/app/.well-known/agent-card.json"
agent_card = {
    "name": "Wallbox SDO Delivery Platform",
    "description": "Automated Software & Data Delivery Multi-Agent System on GCP (Finance, Sales, Firmware, Marketing, Logistics).",
    "version": "0.1.0",
    "protocolVersion": "1.0",
    "url": agent_card_url,
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "capabilities": {
        "streaming": True,
    },
    "skills": [
        {
            "id": "finance_variance",
            "name": "Finance FX & Revenue Variance",
            "description": "Analyzes invoice reconciliation and FX variance.",
            "tags": ["finance", "bigquery"],
        },
        {
            "id": "sales_pipeline",
            "name": "Sales Opportunity Pipeline",
            "description": "Aggregates commercial pipeline conversion metrics.",
            "tags": ["sales"],
        },
        {
            "id": "firmware_telemetry",
            "name": "Firmware & IoT Telemetry",
            "description": "Analyzes OCPP charger logs and device errors.",
            "tags": ["firmware", "iot"],
        },
        {
            "id": "marketing_attribution",
            "name": "Marketing Multi-Touch Attribution",
            "description": "Calculates customer acquisition cost across channels.",
            "tags": ["marketing"],
        },
        {
            "id": "logistics_turnover",
            "name": "Supply Chain & Logistics",
            "description": "Monitors warehouse dispatch SLAs and inventory turnover.",
            "tags": ["logistics"],
        },
    ],
}

payload_a = {
    "displayName": "Wallbox SDO - Option A (Cloud Run A2A with Web Dashboard & Gates)",
    "description": "Autonomous delivery platform hosted on Cloud Run with full Chrome Web Dashboard and Gate H1/H2 sign-offs.",
    "icon": {
        "uri": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/smart_toy/default/24px.svg"
    },
    "a2aAgentDefinition": {
        "jsonAgentCard": json.dumps(agent_card)
    },
}

resp_a = requests.post(base_url, headers=headers, json=payload_a)
print(f"Option A Registration HTTP Status: {resp_a.status_code}")
if resp_a.status_code in [200, 201]:
    res_data_a = resp_a.json()
    print("✅ Option A Successfully Registered in Gemini Enterprise!")
    print(f"   Resource Name: {res_data_a.get('name')}")
else:
    print(resp_a.text)

# ------------------------------------------------------------------------------
# 2. OPTION B: Register Vertex AI Agent Runtime Engine
# ------------------------------------------------------------------------------
print("\n==============================================================================")
print("🧠 Registering OPTION B: Vertex AI Agent Runtime Engine with Gemini Enterprise")
print("==============================================================================")

# Use active Reasoning Engine in us-central1
agent_runtime_id = f"projects/{PROJECT_NUMBER}/locations/us-central1/reasoningEngines/202294196592181248"
payload_b = {
    "displayName": "Wallbox SDO - Option B (Vertex AI Agent Runtime Engine)",
    "description": "Serverless Vertex AI Reasoning Engine executing ADK State Graphs directly with Gemini 3.7 Flash.",
    "icon": {
        "uri": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/psychology/default/24px.svg"
    },
    "adkAgentDefinition": {
        "toolSettings": {
            "toolDescription": "Native Vertex AI Reasoning Engine executing multi-agent workflows with gemini-3.7-flash."
        },
        "provisionedReasoningEngine": {
            "reasoningEngine": agent_runtime_id
        },
    },
}

resp_b = requests.post(base_url, headers=headers, json=payload_b)
print(f"Option B Registration HTTP Status: {resp_b.status_code}")
if resp_b.status_code in [200, 201]:
    res_data_b = resp_b.json()
    print("✅ Option B Successfully Registered in Gemini Enterprise!")
    print(f"   Resource Name: {res_data_b.get('name')}")
else:
    print(resp_b.text)
