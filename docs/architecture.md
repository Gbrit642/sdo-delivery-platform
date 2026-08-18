# Level 300 Reference Architecture: Wallbox SDO Platform on GCP

## 1. System Overview & 3-Plane Governance Model

The Wallbox Software Delivery Optimization (SDO) Platform orchestrates specialized Gemini 3.7 Flash sub-agents within a deterministic Google ADK 2.0 State Graph to automate software and data delivery for business domain owners (Finance, Sales, Firmware, Marketing, Logistics).

```mermaid
flowchart TD
    subgraph Plane1 ["Plane 1: Ingress & Gateway (Google Workspace OIDC)"]
        User(["Business Domain Owner"]) --> Chat["Google Chat Webhook (Adaptive Cards)"]
        User --> WebUI["Interactive Web Dashboard (FastAPI / Chrome)"]
        Chat --> AGW["Agent Gateway (Dual-Identity & Domain RBAC)"]
        WebUI --> AGW
    end

    subgraph Plane2 ["Plane 2: Execution & ADK State Graph (gemini-3.7-flash)"]
        AGW --> GraphEngine["ADK 2.0 State Graph Engine"]
        
        INTAKE["1. INTAKE"] --> SPECIFY["2. SPECIFY (Documental)"]
        SPECIFY --> HARNESS["3. Two-Tier Spec Harness (AST + Critic)"]
        HARNESS --> GATE_H1{{"Gate H1 (Human Spec Sign-Off)"}}
        GATE_H1 --> DESIGN["4. DESIGN (Arquitecto)"]
        DESIGN --> IMPLEMENT["5. IMPLEMENT (Implementer + Sandbox)"]
        IMPLEMENT --> REVIEW["6. REVIEW (Reviewer QA)"]
        REVIEW --> GATE_H2{{"Gate H2 (Final Merge Sign-Off)"}}
        GATE_H2 --> CLOSE["7. CLOSE (GitHub Squash-Merge & Release)"]
        CLOSE --> WATCH["8. WATCH (Day 30 Health Telemetry)"]
        WATCH --> DONE(["DONE (Terminal)"])
    end

    subgraph Plane3 ["Plane 3: Storage & WORM Audit Compliance"]
        CLOSE --> WORM["Cloud Storage Object Retention (Bucket Lock)"]
        GraphEngine --> BQ_ANALYTICS["BigQuery Agent Analytics (adk.dev)"]
        GraphEngine --> OTEL["Cloud Trace & Cloud Logging (OpenTelemetry)"]
    end
```

---

## 2. Core Architectural Components

### 2.1 Core Reasoning Engine (`gemini-3.7-flash`)
- **Context Window:** 2,000,000 tokens (eliminating legacy AWS 8K truncation).
- **Sub-Agent Personas:**
  - `documental`: Gherkin `spec.md` synthesis with BigQuery schema context.
  - `arquitecto`: Technical blueprints (`design.md`) and sandbox test plans.
  - `implementer`: Code/SQL synthesis and ephemeral sandbox runner.
  - `reviewer`: Code auditing, negative testing, and acceptance criteria verification.
  - `watcher`: Day 30 post-deployment query latency and SLA evaluation.
  - `PolicyAuditorAgent`: SOC 2, GDPR data isolation, and scope compliance critic.

### 2.2 Deterministic State Graph Engine (`graphs/workflow.py`)
- **100% Python Routing:** State graph edges and cyclic retries are strictly calculated in Python. No LLM decides state machine transitions.
- **Scale-to-Zero Persistence:** During human approval pauses at Gate H1 and Gate H2, session state freezes in persistent storage with $0 compute cost.

### 2.3 Multi-Domain Skill Registry (`registry/skills/`)
- Dynamic domain manifests (`finance.yaml`, `sales.yaml`, `firmware.yaml`, `marketing.yaml`) governing 3 lifecycle touchpoints:
  1. *Intake Guidance:* Brief prompting and required parameters.
  2. *Spec Validation Policies:* Table allowlists, mandatory metrics, and prohibited SQL operations.
  3. *Post-Implementation Acceptance:* Deterministic assertions (100% test pass rate, query budget, mandatory test types).

### 2.4 Ephemeral Managed Sandboxes (`tools/managed_sandbox.py`)
- Executes generated code and `pytest` test suites in an isolated temporary container, preventing unconstrained host access.

### 2.5 Plane 3 WORM Audit (`storage/`)
- Immutable audit records written to Cloud Storage Object Retention (`audit/{node}/{loop}/{seq:08d}/{intent_id}.json`).
