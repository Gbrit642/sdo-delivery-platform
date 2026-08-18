# Level 300 Reference Architecture: Wallbox SDO Platform on GCP

## 1. System Overview & 3-Plane Governance Model

The Wallbox Software Delivery Optimization (SDO) Platform orchestrates specialized **Gemini 3.7 Flash** sub-agents within a deterministic **Google ADK 2.0 State Graph** to automate software and data delivery for business domain owners (Finance, Sales, Firmware, Marketing, Logistics).

```mermaid
flowchart TD
    subgraph Plane1 ["Plane 1: Ingress & Gateway (Google Workspace OIDC)"]
        User(["Business Domain Owner\n(Finance, Sales, Firmware, Marketing, Logistics)"])
        Chat["Google Chat Webhook\n(Adaptive Cards v2)"]
        WebUI["Interactive Web Dashboard\n(FastAPI / Chrome)"]
        GE["Gemini Enterprise Portal\n(A2A & Reasoning Engine)"]
        
        User --> Chat
        User --> WebUI
        User --> GE
        
        Chat --> AGW["Agent Gateway\n(Dual-Identity & Domain RBAC)"]
        WebUI --> AGW
        GE --> AGW
    end

    subgraph Plane2 ["Plane 2: Execution & ADK State Graph (gemini-3.7-flash)"]
        AGW --> GraphEngine["ADK 2.0 State Graph Engine"]
        
        INTAKE["1. INTAKE\n(Validate Roles & Bind Skill)"] --> SPECIFY["2. SPECIFY\n(Documental: spec.md)"]
        SPECIFY --> HARNESS{"3. Two-Tier Spec Harness\n(AST + Policy Auditor Critic)"}
        HARNESS -- Pass --> GATE_H1{{"Gate H1: Human Spec Sign-Off\n(Scale-to-Zero Pause ⏸)"}}
        HARNESS -- Fail (Retries < 3) --> SPECIFY
        HARNESS -- Fail (Retries >= 3) --> ESCALATE["ESCALATED"]
        
        GATE_H1 -- Approve --> DESIGN["4. DESIGN\n(Arquitecto: design.md)"]
        GATE_H1 -- Request Changes --> SPECIFY
        GATE_H1 -- Reject --> CLOSED(["CLOSED"])
        
        DESIGN --> IMPLEMENT["5. IMPLEMENT\n(Implementer + Sandbox)"]
        IMPLEMENT --> REVIEW["6. REVIEW\n(Reviewer QA)"]
        REVIEW -- Pass --> GATE_H2{{"Gate H2: Merge Sign-Off\n(Scale-to-Zero Pause ⏸)"}}
        REVIEW -- Fix Code --> IMPLEMENT
        REVIEW -- Fix Design --> DESIGN
        REVIEW -- Fix Spec --> SPECIFY
        REVIEW -- Max Retries --> ESCALATE
        
        GATE_H2 -- Approve --> CLOSE["7. CLOSE\n(Squash-Merge PR & Tag v1.0.x)"]
        GATE_H2 -- Reject --> CLOSED
        
        CLOSE --> WATCH["8. WATCH\n(Watcher: Day 30 Health)"]
        WATCH --> DONE(["DONE (Terminal)"])
    end

    subgraph Plane3 ["Plane 3: Storage, Observability & WORM Audit"]
        IMPLEMENT <--> SANDBOX["Managed Agent Linux Sandbox\n(pytest, sqlfluff)"]
        SPECIFY <--> BQ_MCP["BigQuery Managed MCP\n(Schema & Safe SQL)"]
        CLOSE --> WORM["Cloud Storage Object Retention\n(Bucket Lock WORM Mode)"]
        GraphEngine --> BQ_ANALYTICS["BigQuery Agent Analytics\n(sdo_analytics.session_traces)"]
        GraphEngine --> OTEL["Cloud Trace & Cloud Logging\n(OpenTelemetry)"]
    end
```

---

## 2. Core Architectural Components

### 2.1 Core Reasoning Engine (`gemini-3.7-flash`)
- **Context Window:** 2,000,000 tokens (eliminating legacy AWS token truncation).
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
- Dynamic domain manifests (`finance.yaml`, `sales.yaml`, `firmware.yaml`, `marketing.yaml`, `logistics.yaml`) governing 3 lifecycle touchpoints:
  1. *Intake Guidance:* Brief prompting and required parameters.
  2. *Spec Validation Policies:* Table allowlists, mandatory metrics, and prohibited SQL operations.
  3. *Post-Implementation Acceptance:* Deterministic assertions (100% test pass rate, query budget, mandatory test types).

### 2.4 Ephemeral Managed Sandboxes (`tools/managed_sandbox.py`)
- Executes generated code and `pytest` test suites in an isolated temporary container, preventing unconstrained host access.

### 2.5 Plane 3 WORM Audit (`storage/worm_audit.py`)
- Immutable audit records written to Cloud Storage Object Retention (`audit/{node}/{loop}/{seq:08d}/{event_id}.json`) with SHA-256 integrity digests.

---

## 3. Data Flow & Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Owner as Domain Owner (sarah.controller@wallbox.com)
    participant UI as Web Dashboard / Gemini Enterprise
    participant GW as Agent Gateway (RBAC)
    participant Engine as ADK 2.0 State Graph
    participant Agent as Gemini 3.7 Flash Sub-Agents
    participant Harness as Two-Tier Quality Harness
    participant Sandbox as Ephemeral Linux Sandbox
    participant GCS as Cloud Storage WORM

    Owner->>UI: Submit Delivery Brief (Finance FX Variance)
    UI->>GW: Authenticate Google Workspace OIDC
    GW->>Engine: Initialize Loop (01KZZ...)
    
    rect rgb(240, 248, 255)
        Note over Engine,Agent: Leg 1: Intake & Specification
        Engine->>Agent: Documental Agent (Introspect BigQuery Schemas)
        Agent-->>Engine: Generate spec.md with Gherkin
        Engine->>Harness: Validate AST Syntax & Policy Compliance
        Harness-->>Engine: Validation Passed (100%)
        Engine->>UI: Pause at Gate H1 (Scale-to-Zero)
    end
    
    Owner->>UI: Approve Gate H1 Sign-Off
    UI->>Engine: Resume State Machine (resolve Gate H1)
    
    rect rgb(245, 255, 250)
        Note over Engine,Sandbox: Leg 2: Design & Ephemeral Implementation
        Engine->>Agent: Arquitecto Agent (design.md)
        Engine->>Agent: Implementer Agent (BigQuery SQL + Python)
        Engine->>Sandbox: Execute Isolated pytest & sqlfluff
        Sandbox-->>Engine: 100% Test Pass Rate
        Engine->>Agent: Reviewer Agent (Audit against finance.yaml)
        Engine->>UI: Pause at Gate H2 (Scale-to-Zero)
    end
    
    Owner->>UI: Approve Gate H2 Sign-Off
    UI->>Engine: Resume State Machine (resolve Gate H2)
    
    rect rgb(255, 250, 245)
        Note over Engine,GCS: Leg 3: Release, WORM Seal & Day 30 Watch
        Engine->>Engine: Squash-Merge GitHub PR & Tag v1.0.0
        Engine->>GCS: Store SHA-256 Immutable Audit Snapshot
        Engine->>Agent: Watcher Agent (Day 30 Health Telemetry)
        Engine-->>UI: Transition to DONE
    end
```
