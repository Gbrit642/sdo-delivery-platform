# Architectural Decision Records (ADRs): SDO Platform on GCP

This document records the foundational Architectural Decision Records (ADRs) that govern the design, execution, and security invariants of the Autonomous SDO Platform.

---

## ADR-1: Compile-Time Deterministic ADK State Graphs (Zero LLM Graph Routing)
- **Context:** The AWS prototype used a custom YAML state loader, fragile regex parsing, and allowed dynamic LLM routing. This led to non-deterministic loops, unpredictable execution paths, and infinite retry loops.
- **Decision:** State transitions, cyclic retries, and error escalation are governed **strictly by deterministic Python router functions** (`graphs/router.py`) and typed Pydantic models (`graphs/state.py`).
- **Rationale:** Enterprise governance requires mathematically predictable state execution. The LLM acts purely as a worker/synthesizer inside nodes; it is **strictly forbidden** from dynamically deciding the next state in the state graph.
- **Retry Budget:** Retries are charged per destination state ($N=3$). If a stage fails 3 times consecutively, it transitions directly to `ESCALATED` for human intervention.

---

## ADR-2: Gemini 3.7 Flash as the Mandatory Reasoning Engine
- **Context:** Bedrock Claude 3.5 Sonnet's 8K token ceiling caused truncated designs and unparseable outputs in the prototype.
- **Decision:** All sub-agents (**Documental**, **Arquitecto**, **Implementer**, **Reviewer**, **Watcher**, and **PolicyAuditorAgent**) use Vertex AI `gemini-3.7-flash`.
- **Rationale:** Sub-second latency, structured JSON mode adherence, multimodal diagram understanding, and a 2,000,000 token context window.
- **Invariable Rule:** Under **NO circumstance** should Gemini 1.5 or 2.0 be used (they are deprecated in this deployment and will return 501 errors).

---

## ADR-3: Strict Non-Technical / Business-Facing Guardrails
- **Context:** Business domain owners in Finance, Sales, and Logistics do not know how to run terminal commands and should never see developer errors or placeholders.
- **Decision:** All agent system prompts and output handlers must enforce strict non-technical communication rules:
  1. **NEVER** instruct business users to execute terminal/shell commands (such as `python3 deploy_view.py <YOUR_PROJECT_ID>...`, `gcloud ...`, `pip ...`, `curl ...`).
  2. **NEVER** output project ID placeholders (such as `<YOUR_PROJECT_ID>`).
  3. All GCP resource deployments are executed **automatically by the platform** in the active GCP project (`settings.project_id`, default `managed-agent-504409`) upon Gate H2 sign-off.
  4. Output non-technical **Business Deliverable Cards** featuring 1-click BigQuery Studio console links and live sample data previews.

---

## ADR-4: Intelligent Delivery Path Selection (Direct Connector vs. Multi-Agent)
- **Context:** 90%+ of business requests are standard data queries or report views, not complex new software codebases. Additionally, Google Cloud Managed Agents API currently has constraints with authenticating to third-party MCP servers (Salesforce, NetSuite, Jira, Databricks, ServiceNow).
- **Decision:** At Intake, the system analyzes the brief and presents a business-friendly **Trade-Off Card** between:
  - **Path 1: Direct Connector Automation (Tool-Native / MCP):** Fast (<5s), $0 active server compute, ideal for standard data aggregation and reports pulling from BigQuery, Salesforce, NetSuite, etc. Connects via Agent Gateway with enterprise credential delegation.
  - **Path 2: Autonomous Multi-Agent Software Development (Full ADK Graph):** Synthesizes bespoke Python modules, APIs, Gherkin specs, and runs tests in an isolated Linux sandbox.
- **Invariable Rule:** Both paths strictly retain **Gate H1 (Spec Sign-Off)** and **Gate H2 (Activation Sign-Off)**!

---

## ADR-5: 3-Plane Governance Model
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

---

## ADR-6: Cloud Storage Partitioned Storage & BigQuery Artifact Catalog
- **Context:** Need instant SQL search, audit tracing, and partitioned artifact storage.
- **Decision:**
  - **Cloud Storage:** Deliverables stored in `gs://<bucket>/processes/{domain}/{loop_id}/{artifact_name}`.
  - **BigQuery Index (`sdo_analytics.process_artifacts`):** Catalogs every artifact (`artifact_id`, `loop_id`, `domain`, `artifact_name`, `artifact_type`, `gcs_uri`, `content_sha256`, `size_bytes`, `created_at`, `created_by`) for instant SQL search, filtering, and audit monitoring.

---

## ADR-7: Cloud KMS Exclusion (Explicit User Directive)
- **Context:** The customer directive explicitly excluded Cloud KMS envelope encryption for cost and operational simplification.
- **Decision:** Cloud KMS was explicitly removed from this platform.
- **Compliance:** Immutable compliance and tamper-proofing are achieved via **Cloud Storage Object Retention (Bucket Lock in WORM mode)** and SHA-256 state hashing.

---

## ADR-8: Organization Policy `constraints/run.managed.requireInvokerIam` Compliance
- **Context:** Google Cloud enterprise organization policies disallow `allUsers` invoker bindings on Cloud Run.
- **Decision:** The platform complies with Google Cloud enterprise org policies that disallow unauthenticated Cloud Run endpoints.
- **Solution:** Ingress is secured via **Identity-Aware Proxy (IAP)**, Serverless NEGs, and Cloud Load Balancing (`terraform/iap_load_balancer.tf`), while developers can use `scripts/start_iam_proxy.sh` for authenticated Chrome access.
