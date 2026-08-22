# Architectural Design & Test Plan: Credential Injection for Managed Agents with Secured OAuth MCPs

**Document:** `managed-agent-test-credential.md`  
**Purpose:** Architecture Specification & End-to-End Simulation Plan for Credential-Injected Managed Agents using Secured MCP Servers (Cloud Run MCP & BigQuery MCP).  
**Target GCP Project:** `managed-agent-504409` (Project Number: `316329647160`, Region: `us-central1` / `europe-west1`)  
**Core Model:** Vertex AI `gemini-3.7-flash` (Structured JSON Mode, 2M Token Context Window)  
**Status:** Approved for Simulation & Technical Handover  

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Core Architectural Challenge
Google Cloud's **Managed Agent API (GEAP)** provides server-managed, isolated Ubuntu Linux sandboxes at `/workspace`. However, by design, **Managed Agent sandboxes have NO ambient credentials**:
- `metadata.google.internal` does not resolve inside the sandbox.
- No Application Default Credentials (ADC) exist on disk.
- Autonomous agent code cannot make authenticated calls to Google Cloud APIs or third-party OAuth MCP servers (e.g., *Databricks, Salesforce, NetSuite, Cloud Run Admin API*) directly from inside the sandbox.

### 1.2 The Target Solution: Agent Gateway Credential Mediation
This architecture validates that the **Agent Gateway with Dual-Identity Protocol** acts as a secure, authenticated MCP reverse proxy and credential broker. The Gateway:
1. Intercepts incoming user requests from **Google Workspace OIDC / IAP** (`X-Goog-Authenticated-User-Email`).
2. Enforces multi-tenant domain **RBAC and Table Allowlists** (`registry/skills/finance.yaml`).
3. Bridges the Managed Agent to secured, OAuth-authenticated MCP servers (**Cloud Run Admin MCP** and **BigQuery Managed MCP**) without exposing raw credentials or tokens to the LLM weights or sandbox filesystem.

```
+-------------------------------------------------------------------------------------------------------------------+
| CLIENT PLANE (Google Chat / Web Dashboard / Gemini Enterprise)                                                    |
| User: sarah.controller@wallbox.com (Google Workspace OIDC JWT / IAP)                                               |
+-------------------------------------------------------------------------------------------------------------------+
                                                      |
                                                      v
+-------------------------------------------------------------------------------------------------------------------+
| AGENT GATEWAY (Dual-Identity & Credential Injection Mediation Plane)                                              |
| • Authenticates Human Identity (Sarah - Finance Lead) & Enforces RBAC Policy                                       |
| • Mediates OAuth 2.0 / IAM Credentials at the Gateway Boundary                                                     |
+-------------------------------------------------------------------------------------------------------------------+
       |                                                                            |
       | (Option A: Cloud Run A2A Bridge)                                           | (Option B: ADK Agent Runtime Engine)
       v                                                                            v
+-------------------------------------------------------------------------------------------------------------------+
| MANAGED AGENT SANDBOX (/workspace)                                                                                |
| • Synthesizes Web Application (FastAPI + HTML)                                                                    |
| • Ephemeral Isolated Pytest & Linting (100% Pass Guarantee)                                                       |
+-------------------------------------------------------------------------------------------------------------------+
       |                                                                            |
       | 1. Query Data (IAM Authenticated)                                          | 2. Deploy Web App (OAuth Authenticated)
       v                                                                            v
+----------------------------------------------------+      +-------------------------------------------------------+
| BigQuery Managed MCP Server                        |      | Cloud Run Admin MCP Server                            |
| • Table: managed-agent-504409.sdo_finance_demo...  |      | • Creates Service: sdo-hello-world-demo               |
| • Fetches: Invoices, Totals, Customer Counts       |      | • Exposes: Live Webpage with Embedded BQ Data         |
+----------------------------------------------------+      +-------------------------------------------------------+
                                                                                    |
                                                                                    v
                                                            +-------------------------------------------------------+
                                                            | Live Cloud Run Service: sdo-hello-world-demo          |
                                                            | "Hello World + Live BigQuery Financial Analytics"     |
                                                            +-------------------------------------------------------+
```

---

## 2. Dual-Agent Simulation Architecture

The simulation validates **both deployment options** available in the enterprise agent fleet:

| Dimension | Option A: Cloud Run A2A Agent | Option B: Vertex AI Agent Runtime Engine |
|---|---|---|
| **Hosting Target** | Google Cloud Run (`sdo-adk-cloudrun-a2a`) | Vertex AI Agent Runtime (`sdo-adk-agent-runtime`) |
| **Ingress Protocol** | Google A2A v1.0 SSE Streaming (`/.well-known/agent-card.json`) | Vertex AI Reasoning Engine Client API (`client.query()`) |
| **Reasoning Engine** | Vertex AI `gemini-3.7-flash` | Vertex AI `gemini-3.7-flash` |
| **Governance Gates** | Interactive Chrome Dashboard & Google Chat Cards (`cardsV2`) | Programmatic & REST Human Gate Handlers |
| **Credential Flow** | Gateway-mediated OAuth injection for MCP calls | Native Workload Identity + Gateway-mediated OAuth injection |

---

## 3. End-to-End User Journey Simulation: 10-Step Lifecycle

### Step 1: User Request Intake
The business user (Sarah, Finance Lead) submits a natural-language brief:
> *"Deploy a new live web application on Cloud Run saying 'Hello World' that also queries recent customer invoices from BigQuery and displays total billing revenue and active customer counts."*

---

### Step 2: Ingress & Dual-Identity Interception
1. The **Agent Gateway** (`gateway/auth.py`) extracts:
   - **Human Identity:** `sarah.controller@wallbox.com`
   - **Role:** `finance_lead`
   - **Service Identity:** `sa-sdo-finance@managed-agent-504409.iam.gserviceaccount.com`
2. Matches against `registry/skills/finance.yaml` to confirm permissions for `sdo_finance_demo.invoices` and Cloud Run service creation.

---

### Step 3: Gate H1 (Specification Sign-Off)
1. **Documental Agent** synthesizes `spec.md` with Given/When/Then Gherkin contracts:
   ```gherkin
   Feature: Cloud Run Hello World Web App with BigQuery Financial Analytics
     Scenario: Fetch invoices and render live web page
       Given BigQuery table "managed-agent-504409.sdo_finance_demo.invoices"
       When the web application starts on Cloud Run
       Then it renders "Hello World — Autonomous SDO Platform"
       And displays total invoice revenue in EUR and total distinct customer count
   ```
2. **Two-Tier Quality Harness** validates AST rules and SOC 2 / GDPR compliance.
3. User approves **Gate H1** in the Web Dashboard / Google Chat.

---

### Step 4: BigQuery MCP Introspection & Data Query
1. The Managed Agent calls the **BigQuery Managed MCP** through the Agent Gateway.
2. The Gateway attaches Google Cloud IAM credentials with read-only permissions on `sdo_finance_demo.invoices`.
3. Query results returned to the agent:
   ```json
   {
     "total_invoices": 142,
     "total_revenue_eur": 1240500.00,
     "distinct_customers": 42,
     "top_currency": "EUR"
   }
   ```

---

### Step 5: Web Application Code Synthesis
The **Implementer Agent** synthesizes a self-contained Python FastAPI web service (`main.py` + `index.html`):
- Displays the header *"Hello World — SDO Autonomous Delivery"*.
- Embeds live dynamic metrics fetched from BigQuery (`€1,240,500.00 Revenue`, `42 Active Customers`).
- Includes a health endpoint `/healthz` and responsive CSS styling.

---

### Step 6: Ephemeral Linux Sandbox Test Verification
1. The **Managed Agent Sandbox** (`tools/managed_sandbox.py`) provisions an isolated temporary environment.
2. Writes the web application files and automated test suites (`test_main.py`).
3. Executes `pytest` to assert:
   - HTTP 200 on `/` and `/healthz`.
   - HTML body contains "Hello World" and "1,240,500".
   - Zero SQL injection or hardcoded credentials.
4. Asserts **100% test pass rate** before proceeding.

---

### Step 7: Gate H2 (Activation Sign-Off)
1. The **Reviewer Agent** submits the verified deliverable package and sandbox pass report.
2. The human engineer approves **Gate H2 (Merge & Deploy)** in the Web Dashboard.

---

### Step 8: Cloud Run MCP Invocation & Deployment
1. The Managed Agent invokes the **Cloud Run MCP Server** through the Agent Gateway.
2. The Gateway injects authorized OAuth 2.0 credentials (`roles/run.admin` + `roles/iam.serviceAccountUser`).
3. The Cloud Run MCP provisions and deploys the service:
   - **Service Name:** `sdo-hello-world-demo`
   - **Region:** `us-central1`
   - **Platform:** Fully Managed Serverless (`min-instances: 0`, `max-instances: 3`)
   - **Ingress:** HTTPS Public URL / IAM Authenticated

---

### Step 9: Live Verification & Chrome Browser Confirmation
1. Automated curl test verifies live HTTP 200 response and HTML payload from the deployed Cloud Run service URL:
   `https://sdo-hello-world-demo-316329647160.us-central1.run.app`
2. In accordance with user rules, the live application is confirmed in **Google Chrome**.

---

### Step 10: Immutable WORM Audit & OpenTelemetry Trace
1. The state trajectory, SHA-256 deliverable hashes, and MCP execution logs are sealed in the Cloud Storage WORM Bucket (`sdo-worm-audit-managed-agent-504409`).
2. OpenTelemetry traces are exported to **Google Cloud Trace** and indexed in BigQuery (`sdo_analytics.session_traces`).

---

## 4. Security & Governance Invariants

| Guardrail | Enforcement Point | Technical Mechanism |
|---|---|---|
| **Zero Sandbox Credentials** | Sandbox Runtime | The Linux sandbox environment never stores OAuth tokens or GCP service account keys on disk. |
| **Gateway Credential Proxying** | Agent Gateway | All calls to BigQuery MCP and Cloud Run MCP pass through the Gateway, where short-lived tokens are injected per-request. |
| **Table & API Allowlists** | Policy Interceptor | `finance.yaml` strictly whitelists authorized BigQuery datasets (`sdo_finance_demo`) and Cloud Run operations, blocking unauthorized lateral movement. |
| **Human-in-the-Loop Gates** | Deterministic Router | Gate H1 (Spec) and Gate H2 (Deploy) are mandatory and mathematically non-bypassable in Python code. |
| **Immutable Audit Record** | Storage Plane | Cloud Storage Object Retention (Bucket Lock WORM) records SHA-256 digests for SOC 2 Type II compliance. |

---

## 5. Summary of Verification Deliverables

Upon executing this simulation, the following assets will be confirmed operational:
1. **Option A Live Run:** Verification via Google A2A v1.0 SSE streaming on Cloud Run.
2. **Option B Live Run:** Verification via Vertex AI Agent Runtime Reasoning Engine.
3. **Live Deployed Cloud Run Service:** `sdo-hello-world-demo` displaying "Hello World" with live BigQuery data.
4. **OpenTelemetry Cloud Trace:** Distributed trace capturing both BigQuery MCP and Cloud Run MCP spans.
5. **Quality Flywheel Score:** 1.00 / 1.00 score across all multi-turn evaluation metrics.
