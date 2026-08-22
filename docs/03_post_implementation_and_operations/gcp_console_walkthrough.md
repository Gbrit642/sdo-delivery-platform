# GCP Console Technical Inspection & Service Walkthrough Guide

> **Target Audience:** Technical Developers, Cloud Engineers, Solutions Architects, and DevOps Operators.  
> **Document Purpose:** A step-by-step technical walkthrough enabling you to navigate the **Google Cloud Console (`console.cloud.google.com`)**, inspect all deployed services, verify their configurations, run diagnostic queries, and understand how every component functions in production.

---

## 📌 Target GCP Deployment Environment

| Parameter | Production Value |
|---|---|
| **Google Cloud Project ID** | `managed-agent-504409` |
| **GCP Project Number** | `316329647160` |
| **Primary Deployment Region** | `us-central1` |
| **Core Reasoning Engine** | `gemini-3.7-flash` (Vertex AI) |
| **Active Cloud Run Service** | `https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app` |
| **Discovery Engine Collection** | `projects/316329647160/locations/global/collections/default_collection/engines/gemini-enterprise-17857511_1785751184567` |

---

## 🗺 Visual GCP Console Service Map

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                           GOOGLE CLOUD CONSOLE SERVICE MAP                                              |
+---------------------------------------------------------------------------------------------------------------------| [1. Ingress & Compute]           [2. AI Agent Catalog & Runtime]           [3. Data, Storage & Compliance]              |
| ├── Cloud Run                    ├── Gemini Enterprise Assistant           ├── BigQuery (Datasets & Views)             |
| │   └── sdo-adk-cloudrun-a2a     │   ├── Option A (Agent Runtime)          │   ├── sdo_finance_demo (Operational)      |
| ├── Cloud Load Balancing         │   └── Option B (Cloud Run A2A)          │   └── sdo_analytics (Telemetry Index)     |
| │   └── Serverless NEG (IAP)     └── Vertex AI Reasoning Engine            ├── Cloud Storage (GCS)                     |
| └── Identity-Aware Proxy (IAP)       └── ID: 202294196592181248            │   ├── sdo-worm-audit (Bucket Lock WORM)   |
|                                                                            │   └── sdo-artifacts (Process Hierarchy)   |
| [4. Observability & Tracing]     [5. Security & Governance]                │                                           |
| ├── Cloud Trace (OTel Spans)     ├── Cloud IAM & Service Accounts          │                                           |
| └── Cloud Logging (App Logs)     └── Multi-Domain Skill Registry           │                                           |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

## 🔍 Step-by-Step Console Walkthrough

---

### Step 1: Cloud Run (FastAPI Control Plane & Web Dashboard)

Cloud Run hosts the FastAPI application, serving the interactive Web Dashboard, human gate resolution endpoints, and the A2A Agent Card. It scales to zero instances when no loops are actively executing.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Serverless` $\to$ `Cloud Run`
- **Direct Console Deep Link:** [**Open Cloud Run in Google Cloud Console**](https://console.cloud.google.com/run?project=managed-agent-504409)
- **Service Name:** `sdo-adk-cloudrun-a2a`

#### What to Inspect in the Console:
1. **Revisions Tab:** Verify the active revision has `100%` traffic allocation with container image `gcr.io/managed-agent-504409/sdo-adk-cloudrun-a2a:latest`.
2. **Variables & Secrets Tab:** Check environment variables:
   - `MODEL_NAME`: `gemini-3.7-flash`
   - `GCS_WORM_BUCKET`: `sdo-worm-audit-managed-agent-504409`
   - `BIGQUERY_DATASET`: `sdo_analytics`
   - `AUTH_MODE`: `iap`
3. **Logs Tab:** View real-time application logs capturing state graph node executions (`INTAKE`, `SPECIFY`, `GATE_H1`, `DESIGN`, `IMPLEMENT`, `GATE_H2`, `CLOSE`).
4. **Live Verification via Browser:**
   - Live URL: [https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app](https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app)
   - A2A Agent Card: `https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app/a2a/app/.well-known/agent-card.json`

---

### Step 2: Gemini Enterprise Agent Catalog (Agent Registry)

Gemini Enterprise manages the corporate catalog where business users discover and interact with registered AI agents.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Vertex AI Search and Conversation` (or `Agent Builder`) $\to$ `Apps`
- **Direct Console Deep Link:** [**Open Agent Builder in Google Cloud Console**](https://console.cloud.google.com/gen-app-builder/engines?project=managed-agent-504409)
- **Engine Identifier:** `gemini-enterprise-17857511_1785751184567`

#### What to Inspect in the Console:
1. **Agents / Assistants List:** Confirm both registered agents show status `ENABLED`:
   - **Option A:** `Wallbox SDO - Option A (Vertex AI Agent Runtime Engine)` (Agent ID: `7628637833600983461`)
   - **Option B:** `Wallbox SDO - Option B (Cloud Run A2A with Web Dashboard & Gates)` (Agent ID: `11327987463052893149`)
2. **Agent Details & Tools:** Click on Option B to view the configured A2A Discovery endpoint pointing to Cloud Run.

---

### Step 3: Vertex AI Reasoning Engines (Agent Platform Runtime)

Reasoning Engines provide the managed, serverless execution runtime for Python-based ADK State Graphs.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Vertex AI` $\to$ `Reasoning Engines`
- **Direct Console Deep Link:** [**Open Vertex AI Reasoning Engines**](https://console.cloud.google.com/vertex-ai/reasoning-engines?project=managed-agent-504409)
- **Resource ID:** `projects/316329647160/locations/us-central1/reasoningEngines/202294196592181248`

#### What to Inspect in the Console:
1. **Engine Overview:** Confirm the display name `sdo-adk-reasoning-engine` and status `ACTIVE`.
2. **Package Specification:** Check the deployed Python dependencies including `google-adk>=2.5.0`, `google-genai>=1.0.0`, and `pydantic>=2.0.0`.
3. **Execution Endpoint:** Test streaming state graph queries directly through the Vertex AI test interface.

---

### Step 4: Google BigQuery (Data Warehouse, MCP & Analytics)

BigQuery serves a dual purpose: hosting operational domain tables introspected by agents via the BigQuery MCP, and streaming real-time execution analytics and artifact catalog indices.

- **Console Navigation Path:** `Navigation Menu` $\to$ `BigQuery` $\to$ `BigQuery Studio`
- **Direct Console Deep Link:** [**Open BigQuery Studio in Google Cloud Console**](https://console.cloud.google.com/bigquery?project=managed-agent-504409)

#### Datasets & Tables to Inspect:

#### 1. `sdo_finance_demo` (Operational Business Domain)
- `invoices`: Sample invoices across EUR, USD, GBP.
- `billing_events`: Operational ledger transactions.
- `exchange_rates`: Currency conversion reference rates.
- `revenue_summary`: Pre-aggregated daily revenue metrics.
- `weekly_revenue_variance`: Automatically deployed view synthesized upon Gate H2 sign-off.

#### 2. `sdo_analytics` (Platform Observability & Catalog Index)
- `session_traces`: Granular execution traces (node name, execution latency, token counts, initiator).
- `process_artifacts`: Master index of all deliverables stored in GCS with SHA-256 checksums and byte sizes.

#### Useful Diagnostic SQL Queries to Run in BigQuery Studio:

```sql
-- 1. View all cataloged process artifacts across domains
SELECT 
    artifact_id,
    domain,
    loop_id,
    artifact_name,
    artifact_type,
    gcs_uri,
    content_sha256,
    created_at
FROM `managed-agent-504409.sdo_analytics.process_artifacts`
ORDER BY created_at DESC
LIMIT 20;

-- 2. View recent agent execution traces and latencies
SELECT 
    session_id,
    node_id,
    step_name,
    duration_ms,
    total_tokens,
    status,
    timestamp
FROM `managed-agent-504409.sdo_analytics.session_traces`
ORDER BY timestamp DESC
LIMIT 20;

-- 3. Query the automatically deployed Finance currency variance view
SELECT * 
FROM `managed-agent-504409.sdo_finance_demo.weekly_revenue_variance`
LIMIT 10;
```

---

### Step 5: Google Cloud Storage (GCS) & WORM Bucket Lock

Cloud Storage enforces tamper-evident cryptographic compliance and structured artifact persistence across two dedicated buckets.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Cloud Storage` $\to` `Buckets`
- **Direct Console Deep Link:** [**Open Cloud Storage in Google Cloud Console**](https://console.cloud.google.com/storage/browser?project=managed-agent-504409)

#### Buckets to Inspect:

#### 1. `sdo-worm-audit-managed-agent-504409` (Immutable WORM Audit Trail)
- **Configuration Tab:** Inspect **Object Retention / Bucket Lock**. Confirm **WORM Mode** is active with a 365-day retention policy (SOC 2 Type II / GDPR compliance).
- **Objects Hierarchy:**
  ```
  audit/
  └── finance/
      └── 01KZZ20260818133726/
          └── 00000010/
              └── EVT-01KZZ202-0010.json
  ```
- **Integrity:** Every JSON object contains the SHA-256 state hash, human sign-off identity, and immutable execution trajectory.

#### 2. `sdo-artifacts-managed-agent-504409` (Process Deliverable Storage)
- **Objects Hierarchy:**
  ```
  processes/
  └── {domain}/
      └── {loop_id}/
          ├── spec.md               # Synthesized Gherkin specification
          ├── design.md             # Arquitecto technical blueprint
          ├── transform.py          # Python data transformation module
          ├── query.sql             # BigQuery SQL view DDL
          └── test_results.json     # Sandbox test execution report (100% pass)
  ```

---

### Step 6: Identity-Aware Proxy (IAP) & Cloud Load Balancing

Secures ingress behind Google Workspace identity, strictly complying with enterprise organization policy `constraints/run.managed.requireInvokerIam`.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Security` $\to$ `Identity-Aware Proxy`
- **Direct Console Deep Link:** [**Open Identity-Aware Proxy**](https://console.cloud.google.com/security/iap?project=managed-agent-504409)

#### What to Inspect in the Console:
1. **HTTPS Resources:** Check backend service `sdo-adk-backend` mapped to Serverless Network Endpoint Group (NEG) `sdo-adk-neg`.
2. **Access Policy:** Confirm only authenticated Google Workspace domain users (`domain:google.com`, `user:sarah.controller@...`) hold the `IAP-secured Web App User` role.
3. **Developer Proxy Alternative:** Developers can run `./scripts/start_iam_proxy.sh` locally to access the service via authenticated `gcloud run services proxy`.

---

### Step 7: Cloud Trace & Cloud Logging (Observability Substrate)

OpenTelemetry distributed traces propagate through all state graph nodes, giving end-to-end visibility into latency and model reasoning.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Operations` $\to$ `Trace` $\to$ `Trace Explorer`
- **Direct Console Deep Link:** [**Open Cloud Trace Explorer**](https://console.cloud.google.com/traces/list?project=managed-agent-504409)

#### What to Inspect in the Console:
1. **Trace Spans:** Filter by attribute `gen_ai.request.model = "gemini-3.7-flash"` or `sdo.loop_id`.
2. **Waterfall Analysis:** Inspect span durations across `INTAKE` $\to$ `SPECIFY` $\to$ `SPEC_HARNESS` $\to$ `DESIGN` $\to$ `IMPLEMENT` $\to$ `REVIEW` $\to$ `CLOSE`.
3. **Cloud Logging:** Navigate to `Operations` $\to$ `Logging` $\to$ `Logs Explorer` and run query:
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="sdo-adk-cloudrun-a2a"
   ```

---

### Step 8: Cloud IAM & Service Accounts (Least Privilege Governance)

- **Console Navigation Path:** `Navigation Menu` $\to$ `IAM & Admin` $\to$ `IAM`
- **Direct Console Deep Link:** [**Open IAM & Admin**](https://console.cloud.google.com/iam-admin/iam?project=managed-agent-504409)

#### Service Accounts & Roles to Verify:
1. `sa-sdo-engine@managed-agent-504409.iam.gserviceaccount.com`:
   - `roles/aiplatform.user` (Vertex AI & Gemini 3.7 Flash invocation)
   - `roles/bigquery.dataEditor` & `roles/bigquery.jobUser` (BigQuery MCP & Analytics)
   - `roles/storage.objectAdmin` (GCS Artifact & WORM writing)
   - `roles/cloudtrace.agent` (OpenTelemetry span telemetry)
2. `service-316329647160@gcp-sa-aiplatform-re.iam.gserviceaccount.com`:
   - Service agent for Vertex AI Reasoning Engines.

---

### Step 9: Enterprise Governance & Agent Gateway (Identity, RBAC, Table Allowlists & Policy Interceptor)

The **Agent Gateway** ([`gateway/`](file:///usr/local/google/home/papelamine/Documents/Google/Dev/wallbox/Wallbox%20Public%20Shared/sdo-adk-engine/gateway)) acts as the mission-critical security and policy boundary for the entire platform. 

> **Why the Agent Gateway is Critical:**  
> In current cloud architectures, managed AI agents cannot dynamically inject end-user credentials at runtime (this capability is on Google Cloud's product roadmap). Therefore, the **Agent Gateway acts as the authoritative security boundary**, validating caller credentials upfront, resolving their roles, enforcing table allowlists, and preventing unauthorized cross-domain data access before any LLM prompt is constructed.

- **Console Navigation Path:** `Navigation Menu` $\to$ `Operations` $\to$ `Logging` $\to$ `Logs Explorer`
- **Direct Console Deep Link:** [**Open Cloud Logging in Google Cloud Console**](https://console.cloud.google.com/logs/query?project=managed-agent-504409)

#### 1. Dual-Identity Protocol & Identity Delegation
- **Header Extraction ([`gateway/auth.py`](file:///usr/local/google/home/papelamine/Documents/Google/Dev/wallbox/Wallbox%20Public%20Shared/sdo-adk-engine/gateway/auth.py)):** Ingests user identity from Google Workspace OIDC tokens or IAP assertion headers (`X-Goog-Authenticated-User-Email`, `X-Goog-Iap-Jwt-Assertion`).
- **Actor Classification:** Strictly distinguishes **Human User Actions** (`actor_type: "human"`, email: `sarah.controller@enterprise.com`, roles: `["financial_controller"]`) from machine **Agent Service Accounts** (`actor_type: "agent"`, `sa-sdo-engine@managed-agent-504409.iam.gserviceaccount.com`).

#### 2. Domain Access Control & Table Allowlist Interception ([`gateway/policy_interceptor.py`](file:///usr/local/google/home/papelamine/Documents/Google/Dev/wallbox/Wallbox%20Public%20Shared/sdo-adk-engine/gateway/policy_interceptor.py))
- **Role Verification:** Intercepts requests at `INTAKE`. Matches caller email and roles against the target domain's Skill Manifest ([`registry/skills/*.yaml`](file:///usr/local/google/home/papelamine/Documents/Google/Dev/wallbox/Wallbox%20Public%20Shared/sdo-adk-engine/registry/skills)). Unauthorized users (e.g. Sales trying to launch Finance loops) are blocked immediately with `HTTP 403 / RBAC_ACCESS_DENIED`.
- **Table Allowlist Injection:** Injects only authorized domain tables (e.g. `sdo_finance_demo.invoices`, `billing_events`) into the agent context, strictly isolating other domain datasets (e.g. Sales, HR, Logistics).

#### 3. Prohibited Operation & Destructive SQL Defense
- **Static AST / Regex Interceptor ([`harnesses/tier1_static_rules.py`](file:///usr/local/google/home/papelamine/Documents/Google/Dev/wallbox/Wallbox%20Public%20Shared/sdo-adk-engine/harnesses/tier1_static_rules.py)):** Scans all generated specs, SQL queries, and Python files for destructive operations (`DROP TABLE`, `DELETE FROM`, `TRUNCATE`, `ALTER TABLE`, plain-text PII exports). If detected, execution halts before reaching human Gate H1.
- **Two-Tier Policy Critic ([`harnesses/tier2_policy_critic.py`](file:///usr/local/google/home/papelamine/Documents/Google/Dev/wallbox/Wallbox%20Public%20Shared/sdo-adk-engine/harnesses/tier2_policy_critic.py)):** Uses `PolicyAuditorAgent` (`gemini-3.7-flash`) to verify SOC 2, GDPR, and scope compliance.

#### 4. How to Inspect Governance Events in Google Cloud Logging:

Run the following query in **Cloud Logging Logs Explorer**:
```
resource.type="cloud_run_revision"
resource.labels.service_name="sdo-adk-cloudrun-a2a"
jsonPayload.message=~"(PolicyInterceptor|AgentGatewayAuth|INTAKE|RBAC)"
```

#### 5. Audit Human vs. Agent Invocations in BigQuery:

```sql
-- Audit all human gate sign-offs and automated agent steps
SELECT 
    session_id,
    node_id,
    step_name,
    status,
    timestamp
FROM `managed-agent-504409.sdo_analytics.session_traces`
ORDER BY timestamp DESC
LIMIT 50;
```

---

## 🎯 Verification Checklist for Developers

- [ ] **Cloud Run:** Active revision responding on HTTPS with 0 error rate.
- [ ] **Gemini Enterprise:** Option A and Option B listed as `ENABLED`.
- [ ] **Agent Gateway & RBAC:** Policy Interceptor actively verifying domain roles and table allowlists.
- [ ] **BigQuery:** Datasets `sdo_finance_demo` and `sdo_analytics` populated with tables.
- [ ] **Cloud Storage:** Bucket `sdo-worm-audit-managed-agent-504409` has Bucket Lock in WORM mode.
- [ ] **Cloud Trace:** OpenTelemetry spans visible with `gen_ai.request.model=gemini-3.7-flash`.
- [ ] **IAP & Org Policy:** Ingress secured without violating `constraints/run.managed.requireInvokerIam`.
