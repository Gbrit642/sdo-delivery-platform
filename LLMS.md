# LLM Architectural Guide & Context Blueprint: Autonomous SDO Platform

> **Target Audience:** LLMs, Autonomous AI Agents, and Software Engineers scanning, extending, or maintaining this codebase.  
> **Document Purpose:** Explains **WHAT** was built, **WHY** specific architectural choices were made, the **HISTORY & EVOLUTION** from the initial prototype, and the **CRITICAL INVARIANTS** that must never be broken.

---

## 1. Executive Mission & System Purpose

The **Autonomous Software Delivery Optimization (SDO) Platform** is an enterprise-grade multi-agent orchestration system built on **Google Cloud Platform (GCP)** using the **Google Agent Development Kit (ADK 2.0)**.

### The Problem It Solves:
In modern enterprises, non-technical business domain owners (across **Finance, Sales, Firmware, Marketing, and Logistics**) frequently need custom analytical reports, data views, and software workflows. Traditionally, this requires engineering ticketing, backlog delays, and manual development cycles.

### The Solution:
The SDO Platform allows business owners to submit natural-language briefs via **Google Chat** or an interactive **Web Dashboard**. Specialized sub-agents powered by **Gemini 3.7 Flash** collaborate through a **strictly deterministic cyclic state graph** to synthesize specifications, architecture blueprints, SQL views, and Python code, verify them in **isolated Linux sandboxes**, and automatically deploy them to Google Cloud while requiring human approval at two critical decision boundaries:
1. **Gate H1 (Human Specification Sign-Off):** Sign-off on Gherkin scenarios, business metrics, and scope before design begins.
2. **Gate H2 (Human Activation Sign-Off):** Final verification of verified deliverables, sandbox test reports (100% pass guarantee), and deployment approval.

---

## 2. Why We Built It: AWS Prototype Bottlenecks $\to$ GCP Target Architecture

The original proof-of-concept (`sdo-prototype-main`) on AWS revealed critical architectural flaws that required a complete re-platforming to Google Cloud:

| # | AWS Prototype Bottleneck | Failure Mode on AWS | Google Cloud Target Solution in this Repo |
|---|---|---|---|
| **1** | **Fragile State Engine & Token Limits** | Custom YAML state loader, fragile regex parsing, and Bedrock Claude 3.5 Sonnet's 8K token ceiling caused truncated designs and unparseable outputs. | **Google ADK 2.0 State Graphs** (`google.adk.graphs.StateGraph`) with typed Pydantic models + **`gemini-3.7-flash`** (2,000,000 token context window, structured JSON mode). |
| **2** | **Compute Inefficiency & SQS Timeouts** | Pinned EKS worker pods ran continuously. When human gates stayed open for days/weeks, SQS visibility expired (`ReceiptHandle has expired`), triggering duplicate execution and crash loops. | **Serverless Scale-to-Zero Sessions**: Persistent session hydration via Cloud Storage / Session Store. Gate approvals pause for weeks at **$0 active compute cost** with zero timeout crashes. |
| **3** | **Missing Data Tool Connectors** | Data tasks (Finance node) deterministically crashed at `SPECIFY` because no external database connectors existed. | **Google BigQuery Managed MCP & Extensible MCPs**: Native Model Context Protocol servers enabling governed schema introspection and query execution across BigQuery, Salesforce, NetSuite, and Notion. |
| **4** | **Identity Delegation Bypass** | Prototype ran under static auth bypass (`LOCAL_BYPASS_OIDC=true`), lacking end-to-end user identity delegation. | **Agent Gateway with Dual-Identity Protocol**: Validates Google Workspace OIDC / IAP headers (`X-Goog-Authenticated-User-Email`), strictly separating Human Actions from Agent Service Accounts, and enforcing domain RBAC. |
| **5** | **Unconstrained Code Execution** | No isolated sandbox existed to safely compile SQL or run Python unit tests before human review. | **Managed Agent Linux Sandboxes**: Serverless, ephemeral Ubuntu Linux containers with restricted egress for safe compilation, linting (`sqlfluff`), and testing (`pytest`). |

---

## 3. Key Architectural Decisions (ADRs)

### ADR-1: Compile-Time Deterministic ADK State Graphs (Zero LLM Graph Routing)
- **Decision:** State transitions, cyclic retries, and error escalation are governed **strictly by deterministic Python router functions** (`graphs/router.py`) and typed Pydantic state (`graphs/state.py`).
- **Rationale:** Enterprise governance requires mathematically predictable state execution. The LLM acts purely as a worker/synthesizer inside nodes; it is **strictly forbidden** from dynamically deciding the next state in the state graph.
- **Retry Budget:** Retries are charged per destination state ($N=3$). If a stage fails 3 times consecutively, it transitions directly to `ESCALATED` for human intervention.

### ADR-2: Gemini 3.7 Flash as the Mandatory Reasoning Engine
- **Decision:** All sub-agents (**Documental**, **Arquitecto**, **Implementer**, **Reviewer**, **Watcher**, and **PolicyAuditorAgent**) use `gemini-3.7-flash`.
- **Rationale:** Sub-second latency, structured JSON mode adherence, multimodal diagram understanding, and a 2M token context window.
- **Rule:** Under **NO circumstance** should Gemini 1.5 or 2.0 be used (they are deprecated in this deployment and will return 501 errors).

### ADR-3: Strict Non-Technical / Business-Facing Guardrails
- **Decision:** All agent system prompts and output handlers must enforce strict non-technical communication rules:
  1. **NEVER** instruct business users to execute terminal/shell commands (such as `python3 deploy_view.py <YOUR_PROJECT_ID>...`, `gcloud ...`, `pip ...`, `curl ...`).
  2. **NEVER** output project ID placeholders (such as `<YOUR_PROJECT_ID>`).
  3. All GCP resource deployments are executed **automatically by the platform** in the active GCP project (`settings.project_id`, default `managed-agent-504409`) upon Gate H2 sign-off.
  4. Output non-technical **Business Deliverable Cards** featuring 1-click BigQuery Studio console links and live sample data previews.

### ADR-4: Intelligent Delivery Path Selection (Direct Connector vs. Multi-Agent)
- **Decision:** At Intake, the system analyzes the brief and presents a business-friendly **Trade-Off Card** between:
  - **Path 1: Direct Connector Automation (Tool-Native / MCP):** Fast (<5s), $0 server compute, ideal for standard data aggregation and reports pulling from BigQuery, Salesforce, NetSuite, etc.
  - **Path 2: Autonomous Multi-Agent Software Development (Full ADK Graph):** Synthesizes bespoke Python modules, APIs, Gherkin specs, and runs tests in an isolated Linux sandbox.
- **Invariable Rule:** Both paths strictly retain **Gate H1 (Spec Sign-Off)** and **Gate H2 (Activation Sign-Off)**!

### ADR-5: 3-Plane Governance Model
```
+-------------------------------------------------------------------------------------------------------+
| PLANE 1: DEFINITIONS & CONTRACTS (Multi-Domain Skill Registry & Agent Gateway)                        |
| Domain Manifests (finance, sales, firmware, marketing, logistics), Pydantic Schemas, Agent Prompts    |
+-------------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-------------------------------------------------------------------------------------------------------+
| PLANE 2: DELIVERABLES & WORK PRODUCTS (GCS Process Artifacts & Ephemeral Sandboxes)                   |
| spec.md, design.md, SQL Views, Python Logic, Sandbox Test Suites, Pull Requests, Tags                |
+-------------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+-------------------------------------------------------------------------------------------------------+
| PLANE 3: IMMUTABLE AUDIT EVENT LOG (Cloud Storage WORM Lock & BigQuery Catalog Index)                 |
| SHA-256 Hashed JSON State Trajectories, OpenTelemetry Cloud Trace Spans, Artifact Index Table        |
+-------------------------------------------------------------------------------------------------------+
```

### ADR-6: Cloud Storage Partitioned Storage & BigQuery Artifact Catalog
- **Cloud Storage:** Deliverables stored in `gs://<bucket>/processes/{domain}/{loop_id}/{artifact_name}`.
- **BigQuery Index (`sdo_analytics.process_artifacts`):** Catalogs every artifact (`artifact_id`, `loop_id`, `domain`, `artifact_name`, `artifact_type`, `gcs_uri`, `content_sha256`, `size_bytes`, `created_at`, `created_by`) for instant SQL search, filtering, and audit monitoring.

### ADR-7: Cloud KMS Exclusion (Explicit User Directive)
- **Decision:** Cloud KMS was explicitly removed from this platform per user directive.
- **Compliance:** Immutable compliance is achieved via **Cloud Storage Object Retention (Bucket Lock in WORM mode)**. Do not re-introduce Cloud KMS unless explicitly requested.

### ADR-8: Organization Policy `constraints/run.managed.requireInvokerIam` Compliance
- **Decision:** The platform complies with Google Cloud enterprise org policies that disallow `allUsers` invoker bindings on Cloud Run.
- **Solution:** Ingress is secured via **Identity-Aware Proxy (IAP)**, Serverless NEGs, and Cloud Load Balancing (`terraform/iap_load_balancer.tf`), while developers can use `scripts/start_iam_proxy.sh` for authenticated Chrome access.

---

## 4. Codebase Directory Map

```
sdo-adk-engine/
├── config/
│   ├── settings.py                 # Pydantic BaseSettings (Project: managed-agent-504409, Model: gemini-3.7-flash)
│   └── nodes.yaml                  # Multi-tenant domain definitions
├── gateway/
│   ├── auth.py                     # Dual-Identity Protocol (Google Workspace OIDC & IAP header extraction)
│   ├── policy_interceptor.py       # Domain access control RBAC & table allowlists
│   └── chat_adapter.py             # Google Chat Adaptive Cards (cardsV2) formatter
├── registry/
│   ├── skill_registry.py           # Multi-domain YAML manifest loader and policy engine
│   └── skills/                     # 5 domain manifests: finance.yaml, sales.yaml, firmware.yaml, marketing.yaml, logistics.yaml
├── graphs/
│   ├── state.py                    # Master LoopState Pydantic model (with path selection & GCS URIs)
│   ├── router.py                   # 100% deterministic Python routers for spec harness, review, and gates
│   └── workflow.py                 # ADK StateGraph construction & compilation
├── agents/
│   ├── tradeoff_evaluator.py       # Non-Technical Delivery Path & Trade-Off Evaluator
│   ├── documental.py               # Documental Agent (spec.md authoring with gemini-3.7-flash)
│   ├── arquitecto.py               # Arquitecto Agent (design.md & test plan authoring)
│   ├── implementer.py              # Implementer Agent (code/SQL generation + Sandbox runner)
│   ├── reviewer.py                 # Reviewer Agent (QA, test validation & acceptance criteria)
│   └── watcher.py                  # Watcher Agent (Day 30 telemetry & SLA evaluation)
├── harnesses/
│   ├── tier1_static_rules.py       # Deterministic AST & Pydantic Gherkin parser
│   ├── tier2_policy_critic.py      # PolicyAuditorAgent compliance critic (gemini-3.7-flash)
│   └── harness_node.py             # Composite Two-Tier Quality Harness node
├── tools/
│   ├── bq_mcp_client.py            # BigQuery Managed MCP connector with schema introspection
│   ├── github_client.py            # GitHub PR creation, squash-merge, and release tagging
│   └── managed_sandbox.py          # Ephemeral Linux sandbox runner (isolated pytest & sqlfluff)
├── storage/
│   ├── artifact_catalog.py         # Cloud Storage hierarchy & BigQuery Catalog Manager
│   └── worm_audit.py               # Cloud Storage Object Retention WORM writer (SHA-256 digests)
├── observability/
│   ├── otel.py                     # OpenTelemetry instrumentation (Cloud Trace & Logging)
│   └── analytics.py                # BigQuery Agent Analytics plugin (sdo_analytics)
├── eval/
│   ├── evaluator.py                # Gemini Enterprise evaluation suite
│   ├── custom_metrics.py           # Custom evaluators (Gherkin adherence, Graph conformance, Skill compliance)
│   └── benchmarks/                 # Ground truth evaluation datasets
├── web/
│   ├── app.py                      # FastAPI control plane, REST API, A2A card endpoint, Chat webhook
│   └── static/                     # Web Dashboard SPA (visual FSM graph, trade-off cards, catalog tab)
├── terraform/                      # Complete GCP Infrastructure as Code (Cloud Run, GCS WORM, BigQuery, IAP)
├── scripts/                        # Deployment, Gemini Enterprise registration, and proxy scripts
├── tests/                          # 48 automated unit and integration tests (100% pass rate)
└── docs/                           # Reference architecture, demo scripts, and replication guides
```

---

## 5. Invariants for Future LLM Modifications

When editing or extending this codebase, any LLM **must strictly preserve**:
1. **Model Invariant:** Always use `gemini-3.7-flash` (or `gemini-3.1-pro` / `gemini-3.0-flash`). Never introduce Gemini 1.5 or 2.0.
2. **State Machine Invariant:** Keep graph routing 100% deterministic in Python (`graphs/router.py`). Never let the LLM decide state transitions.
3. **Human Gate Invariant:** Never bypass or remove **Gate H1** or **Gate H2**. Human-in-the-loop sign-off is mandatory for all delivery paths.
4. **Non-Technical Guardrail Invariant:** Never output developer terminal commands (`python3 ...`, `gcloud ...`) to end users. Automatically deploy resources to the active project and present Business Deliverable Cards.
5. **Testing Invariant:** Always run `python3 -m pytest tests/ -v` before finalizing changes to ensure all 48 tests pass.
