# Level 300 Reference Architecture: Wallbox SDO Platform on GCP

## 1. System Overview & 3-Plane Governance Model

The Wallbox Software Delivery Optimization (SDO) Platform orchestrates specialized **Gemini 3.7 Flash** sub-agents within a deterministic **Google ADK 2.0 State Graph** to automate software and data delivery for business domain owners (Finance, Sales, Firmware, Marketing, Logistics).

```mermaid
flowchart TD
    subgraph Plane1 ["Plane 1: Ingress & Agent Gateway (Google Workspace / IAP)"]
        User(["Business Domain Owner\n(Finance, Sales, Firmware, Marketing, Logistics)"])
        Chat["Google Chat Webhook\n(Adaptive Cards v2)"]
        WebUI["Interactive Web Dashboard\n(FastAPI / Chrome)"]
        GE["Gemini Enterprise Agent Registry\n(A2A & Reasoning Engine)"]
        
        User --> Chat
        User --> WebUI
        User --> GE
        
        Chat --> AGW["Agent Gateway\n(Dual-Identity & Domain RBAC)"]
        WebUI --> AGW
        GE --> AGW
    end

    subgraph SelectionLayer ["Intelligent Path Selection & Trade-Off Engine"]
        AGW --> EVALUATOR{"Path Evaluator\n(Direct Connector vs Multi-Agent)"}
        EVALUATOR -->|Non-Technical Trade-Off Card| UserChoice{"User Selects Path"}
    end

    subgraph Plane2 ["Plane 2: Execution & ADK 2.0 State Graph (gemini-3.7-flash)"]
        UserChoice --> INTAKE["1. INTAKE\n(Validate Roles & Bind Skill)"]
        INTAKE --> SPECIFY["2. SPECIFY\n(Documental: spec.md)"]
        SPECIFY --> HARNESS{"3. Two-Tier Spec Harness\n(AST + Policy Auditor Critic)"}
        HARNESS -- Pass --> GATE_H1{{"Gate H1: Human Spec Sign-Off\n(Scale-to-Zero Pause ⏸)"}}
        HARNESS -- Fail (Retries < 3) --> SPECIFY
        HARNESS -- Fail (Retries >= 3) --> ESCALATE["ESCALATED"]
        
        GATE_H1 -- Approve --> DESIGN["4. DESIGN\n(Arquitecto: design.md)"]
        GATE_H1 -- Request Changes --> SPECIFY
        GATE_H1 -- Reject --> CLOSED(["CLOSED"])
        
        DESIGN --> IMPLEMENT["5. IMPLEMENT\n(Implementer + Sandbox)"]
        IMPLEMENT --> REVIEW["6. REVIEW\n(Reviewer QA)"]
        REVIEW -- Pass --> GATE_H2{{"Gate H2: Activation Sign-Off\n(Scale-to-Zero Pause ⏸)"}}
        REVIEW -- Fix Code --> IMPLEMENT
        REVIEW -- Fix Design --> DESIGN
        REVIEW -- Fix Spec --> SPECIFY
        REVIEW -- Max Retries --> ESCALATE
        
        GATE_H2 -- Approve --> CLOSE["7. CLOSE\n(Deploy Asset & Seal Record)"]
        GATE_H2 -- Reject --> CLOSED
        
        CLOSE --> WATCH["8. WATCH\n(Watcher: Day 30 Health)"]
        WATCH --> DONE(["DONE (Terminal)"])
    end

    subgraph Plane3 ["Plane 3: Storage, Observability & WORM Audit"]
        IMPLEMENT <--> SANDBOX["Managed Agent Linux Sandbox\n(pytest, sqlfluff)"]
        SPECIFY <--> BQ_MCP["BigQuery Managed MCP\n(Schema & Safe SQL)"]
        CLOSE --> GCS_WORM["Cloud Storage Object Retention\n(Bucket Lock WORM Mode)"]
        CLOSE --> GCS_ART["Cloud Storage Artifact Storage\n(gs://bucket/processes/domain/loop_id/)"]
        GCS_ART --> BQ_CATALOG["BigQuery Artifact Catalog\n(sdo_analytics.process_artifacts)"]
        StateGraph --> BQ_ANALYTICS["BigQuery Agent Analytics\n(sdo_analytics.session_traces)"]
        StateGraph --> OTEL["Cloud Trace & Cloud Logging\n(OpenTelemetry)"]
    end
```

---

## 2. Core Architectural Subsystems

### 2.1 Agent Gateway & Dual-Identity Protocol (`gateway/`)
- **Google Workspace / IAP Validation:** Ingests user identity from OIDC tokens or `X-Goog-Authenticated-User-Email` header, completely avoiding public IP exposure.
- **Dual-Identity Classification:** Isolates **Human User Actions** from machine **Agent Service Accounts** (`sa-sdo-{node}@...`).
- **Domain RBAC & Allowlisting:** Matches initiator roles against the domain skill manifest before invoking any agent.

### 2.2 Agent Registry in Gemini Enterprise
- Central registry managing A2A discovery cards, ADK Reasoning Engines, and extensible MCP connector catalogs (BigQuery, Cloud Storage, Salesforce, NetSuite, Notion).

### 2.3 Multi-Domain Skill Registry (`registry/skills/`)
- 5 modular domain manifests (`finance.yaml`, `sales.yaml`, `firmware.yaml`, `marketing.yaml`, `logistics.yaml`) defining authorized roles, table allowlists, mandatory business metrics, and prohibited operations (`DROP TABLE`, `DELETE FROM`).

### 2.4 Intelligent Path Selection Engine (`agents/tradeoff_evaluator.py`)
- Evaluates business briefs at Intake and presents non-technical trade-off matrices:
  - **Path 1: Direct Connector Automation (Tool-Native / MCP):** Fast (<5s), $0 server compute, ideal for reports and queries pulling across tools.
  - **Path 2: Autonomous Multi-Agent Software Development (Full ADK Graph):** Synthesizes custom Python code, blueprints, and runs isolated Linux sandbox tests.
- Retains **Gate H1** and **Gate H2** across both paths.

### 2.5 Structured GCS Artifact Storage & BigQuery Catalog (`storage/artifact_catalog.py`)
- Partitioned storage hierarchy in Cloud Storage (`gs://<bucket>/processes/{domain}/{loop_id}/`).
- Synchronized metadata indexing in BigQuery (`sdo_analytics.process_artifacts`) for instant search, filtering, and audit monitoring.

### 2.6 Plane 3 WORM Cryptographic Audit (`storage/worm_audit.py`)
- Cloud Storage Object Retention (Bucket Lock in WORM mode) storing tamper-evident SHA-256 JSON snapshots for SOC 2 Type II compliance.
