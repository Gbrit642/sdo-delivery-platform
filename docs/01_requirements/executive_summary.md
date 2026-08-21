SDO Platform on Google Cloud: Implementation Blueprint & LLM Handover

Document Type: Master Developer Handover & System Implementation PromptTarget Audience: Implementing LLM & Core Engineering TeamCustomer: Wallbox (Pablo Murga, Mario Chueca)Lead Authors: Google Customer Engineering (Practice CE)Companion Documents:

Product Requirements Document: prd_gcp_sdo_platform.md

Technical Design Document: design_doc_gcp_sdo_platform.md

Interactive Architecture & Journey: gcp_transition_proposal_and_weekly_plan.html

1. Executive Handover Prompt for the Implementing LLM

[!IMPORTANT] Directive for the Implementing LLM:You are tasked with implementing the greenfield Software Delivery Optimization (SDO) Platform on Google Cloud Platform (GCP) under directory sdo-adk-engine/.

You must strictly adhere to the technical stack, architectural patterns, deterministic state machine constraints, and security models defined in this document. Do not invent custom queue orchestrators, do not use legacy regex state parsers, do not write DIY docker sandboxes, and never allow an LLM to decide state graph transitions. All transitions must be 100% deterministic in Python code.

2. Business Context & Customer Motivation

Wallbox requires a human-supervised multi-agent system that allows non-technical business service owners (Finance, Logistics, Firmware, Operations) to submit change briefs via Google Chat. The system orchestrates specialized AI agents to generate specifications, design technical blueprints, compile code/queries, and run automated tests, while enforcing two mandatory human approval gates (Gate H1 for spec approval and Gate H2 for merge/deploy approval).

The 5 Core Flaws of the Legacy AWS Prototype (sdo-prototype-main):

Fragile State Engine & Token Ceiling: Custom in-house YAML state loader, custom run_leg re-entrant loop, and fragile regex JSON parsing, coupled with Bedrock Claude 3.5 Sonnet's 8K token ceiling and rolling context truncations.

Compute Inefficiency & SQS Visibility Timeouts: EKS worker pods run continuously without true scale-to-zero. When human gates stay open for days/weeks, SQS visibility expires (ReceiptHandle has expired), triggering duplicate execution and crash loops.

Missing Tool Connectors (Epic E4): Data tasks (Finance node) deterministically crash at SPECIFY because no external database connectors (BigQuery) exist.

Identity Delegation Dilemma: Sandbox runs under static auth bypass (LOCAL_BYPASS_OIDC=true), lacking end-to-end user identity delegation.

Unconstrained Code Execution: No isolated, ephemeral sandbox exists to safely compile, lint, and run unit tests against generated SQL/Python code.

3. Master Architectural Decision Matrix

flowchart TD

    subgraph ClientLayer ["1. Client & Ingress Plane"]

        Chat["Google Chat UI"] -->|OIDC JWT| AGW["Agent Gateway (Auth & Multi-Tenant Interceptor)"]

    end

    subgraph RuntimeEngine ["2. Agent Platform Runtime (ADK 2.0 State Graph)"]

        AGW --> AR["Agent Platform Runtime (Persistent Session & Memory Banks)"]

        

        subgraph ADKGraph ["ADK 2.0 State Graph (gemini-3.7-flash)"]

            INTAKE["INTAKE"] --> SPECIFY["SPECIFY (documental)"]

            SPECIFY --> HARNESS1["Spec Harness (Tier 1 AST + Tier 2 Policy Critic)"]

            HARNESS1 -->|Pass| GATE_H1{{"GATE H1 (Human Spec Approval)"}}

            HARNESS1 -->|Fail Fix| SPECIFY

            

            GATE_H1 -->|Approved| DESIGN["DESIGN (arquitecto)"]

            DESIGN --> IMPLEMENT["IMPLEMENT (Managed Sandbox)"]

            IMPLEMENT --> REVIEW["REVIEW (Reviewer Agent)"]

            REVIEW -->|Pass| GATE_H2{{"GATE H2 (Final Merge Approval)"}}

            REVIEW -->|Fail Fix| IMPLEMENT

            REVIEW -->|Fail Design| DESIGN

            

            GATE_H2 -->|Approved| CLOSE["CLOSE (MR Merge & Deploy)"]

            CLOSE --> WATCH["WATCH (Day 30 Health Check)"]

            WATCH --> DONE(["DONE"])

        end

    end

    subgraph GovernedEcosystem ["3. Governed Tools, Sandboxes & Compliance"]

        AR <-->|Direct Schema & Querying| BQ_MCP["Google BigQuery Managed MCP"]

        AR <-->|MR Merge & Tagging| GL_MCP["GitLab MCP Server"]

        AR <-->|Domain Tool Resolution| REG["Agent Platform Skill Registry"]

        IMPLEMENT <-->|Server-Side Code Testing| SANDBOX["Managed Agent Linux Containers"]

        AR -->|Immutable JSON Logs| GCS_WORM["Cloud Storage Object Retention (WORM) + KMS Shredding"]

        AR -->|OpenTelemetry Eval Traces| TRACE["Cloud Trace & Logging -> BigQuery Sink"]

        AR -->|Async Day 30 Resume| CTASKS["Cloud Tasks / Scheduler"]

    end



Layer

GCP Target Selection

Architectural Justification

Agent Framework

Google ADK 2.0 State Graphs (adk.dev/graphs)

Strict deterministic cyclic routing, typed Pydantic outcome schemas, native retry backstops ($N \le 3$), zero string parsing hacks.

Reasoning Model

Gemini 3.7 Flash

2M token context window (full-repo context), sub-second latency, structured JSON adherence, native multimodal ERD/diagram ingestion.

Compute & State

Agent Platform Runtime

Serverless scale-to-zero compute; persistent Session & Memory Banks allow Gate H1/H2 to pause for weeks at $0 active compute cost.

Security & Identity

Agent Gateway

Intercepts Google Workspace OIDC tokens; strictly separates Human Actor from Agent Actor; contextual MCP authorization.

Code Sandbox

Gemini Enterprise Managed Agent Sandboxes

Ephemeral, serverless Ubuntu Linux containers provisioned on demand for safe compilation, linting, and unit test execution.

Data Connector

Google BigQuery Managed MCP Server

Native first-party MCP server for direct schema introspection and SQL querying for the Finance node (resolves Epic E4).

Compliance Gating

Two-Tier Policy Harness Pipeline

Tier 1: AST/Pydantic parser (Gherkin syntax, YAML frontmatter).

Tier 2: PolicyAuditorAgent (gemini-3.7-flash) checking SOC 2 and GDPR rules.

Immutable Storage

Cloud Storage Object Retention (WORM Lock) + KMS

Satisfies PRD RF-B6-16 (tamper-evident SOC 2 audit trail) and RNF-10 (GDPR Right to be Forgotten via per-user Cloud KMS key destruction).

Observability

Cloud Trace + Cloud Logging $\rightarrow$ BigQuery Sink

OpenTelemetry export capturing complete prompt/response trajectories into BigQuery for automated evaluation datasets (adk eval).

4. Target Greenfield Codebase Layout (sdo-adk-engine/)

The implementing LLM must construct the application under sdo-adk-engine/ following this clean, modular package structure:

sdo-adk-engine/

├── .venv/                         # Project-specific isolated virtual environment

├── pyproject.toml                 # Dependencies: google-adk>=2.5.0, pydantic>=2.0, google-cloud-*

├── README.md                      # Architecture and operational execution guide

├── config/

│   ├── settings.py                # Environment configs (GCP Project, Region, Bucket names)

│   └── nodes.yaml                 # Multi-tenant domain definitions (finance, logistics, firmware)

├── gateway/

│   ├── __init__.py

│   ├── auth.py                    # OIDC token validation & dual-identity classification

│   ├── policy_interceptor.py      # Node partition checks & MCP permission gating

│   └── chat_adapter.py            # Google Chat webhook receiver & Adaptive Card dispatcher

├── graphs/

│   ├── __init__.py

│   ├── state.py                   # Master LoopState Pydantic model

│   ├── router.py                  # Deterministic routing functions (route_spec_harness, route_review)

│   └── workflow.py                # ADK StateGraph assembly & compilation

├── agents/

│   ├── __init__.py

│   ├── documental.py              # Documental Agent (spec.md authoring with gemini-3.7-flash)

│   ├── arquitecto.py              # Arquitecto Agent (design.md & test plan authoring)

│   ├── implementer.py             # Implementer Agent (code generation + Sandbox runner)

│   ├── reviewer.py                # Reviewer Agent (QA, negative testing & AST linting)

│   └── watcher.py                 # Watcher Agent (Day 30 telemetry evaluation)

├── harnesses/

│   ├── __init__.py

│   ├── tier1_static_rules.py      # Deterministic AST & Pydantic Gherkin/Frontmatter validators

│   ├── tier2_policy_critic.py     # PolicyAuditorAgent LLM compliance critic

│   └── harness_node.py            # Composite Two-Tier Harness node execution

├── tools/

│   ├── __init__.py

│   ├── bq_mcp_client.py           # BigQuery Managed MCP tool connector

│   ├── gitlab_client.py           # GitLab MR merge, squash & tag connector

│   └── managed_sandbox.py         # Gemini Enterprise Managed Agent Linux sandbox wrapper

├── storage/

│   ├── __init__.py

│   ├── worm_audit.py              # Cloud Storage Object Retention writer

│   └── crypto_shredding.py        # Per-user Cloud KMS envelope encryption

└── tests/

    ├── unit/                      # Fast unit tests for graphs, routers, and Tier 1 harnesses

    └── integration/               # End-to-end simulated Finance loop walkthroughs



5. Core Code Contracts & Schemas

5.1 Master Loop State (graphs/state.py)

from pydantic import BaseModel, Field

from typing import Literal, Optional, Any

from datetime import datetime

class ActorIdentity(BaseModel):

    actor_type: Literal["human", "agent"]

    user_email: Optional[str] = None

    subject_id: Optional[str] = None

    roles: list[str] = Field(default_factory=list)

class HarnessEvaluation(BaseModel):

    passed: bool

    tier1_violations: list[str] = Field(default_factory=list)

    tier2_critique: Optional[str] = None

    evaluated_at: datetime = Field(default_factory=datetime.utcnow)

class LoopState(BaseModel):

    loop_id: str

    node_id: str  # e.g., "finance", "logistics"

    initiator: ActorIdentity

    brief_raw: str

    

    # Artifacts (Plane 2)

    spec_content: Optional[str] = None

    design_content: Optional[str] = None

    code_artifacts: dict[str, str] = Field(default_factory=dict)

    test_results: dict[str, Any] = Field(default_factory=dict)

    

    # State tracking

    current_state: str = "INTAKE"

    retry_count: int = 0

    max_retries: int = 3

    

    # Harnesses & Gating

    spec_harness: Optional[HarnessEvaluation] = None

    code_harness: Optional[HarnessEvaluation] = None

    gate_h1_approved: bool = False

    gate_h2_approved: bool = False

    

    # Terminal

    escalation_reason: Optional[str] = None

    close_commit_hash: Optional[str] = None

    worm_audit_record_id: Optional[str] = None

5.2 Deterministic ADK State Graph (graphs/workflow.py)

from google.adk.graphs import StateGraph, START, END

from graphs.state import LoopState

from graphs.router import route_spec_harness, route_review

def build_sdo_graph() -> StateGraph:

    workflow = StateGraph(LoopState)

    

    # Register Nodes

    workflow.add_node("INTAKE", intake_node)

    workflow.add_node("SPECIFY", specify_node)

    workflow.add_node("SPEC_HARNESS", spec_harness_node)

    workflow.add_node("GATE_H1", gate_h1_node)

    workflow.add_node("DESIGN", design_node)

    workflow.add_node("IMPLEMENT", implement_node)

    workflow.add_node("REVIEW", review_node)

    workflow.add_node("GATE_H2", gate_h2_node)

    workflow.add_node("CLOSE", close_node)

    workflow.add_node("WATCH", watch_node)

    workflow.add_node("ESCALATED", escalated_node)

    

    # Deterministic Edges & Back-Edges

    workflow.add_edge(START, "INTAKE")

    workflow.add_edge("INTAKE", "SPECIFY")

    workflow.add_edge("SPECIFY", "SPEC_HARNESS")

    workflow.add_conditional_edges(

        "SPEC_HARNESS", 

        route_spec_harness, 

        {"GATE_H1": "GATE_H1", "SPECIFY": "SPECIFY", "ESCALATED": "ESCALATED"}

    )

    workflow.add_edge("GATE_H1", "DESIGN")

    workflow.add_edge("DESIGN", "IMPLEMENT")

    workflow.add_edge("IMPLEMENT", "REVIEW")

    workflow.add_conditional_edges(

        "REVIEW", 

        route_review, 

        {"GATE_H2": "GATE_H2", "IMPLEMENT": "IMPLEMENT", "DESIGN": "DESIGN", "SPECIFY": "SPECIFY", "ESCALATED": "ESCALATED"}

    )

    workflow.add_edge("GATE_H2", "CLOSE")

    workflow.add_edge("CLOSE", "WATCH")

    workflow.add_edge("WATCH", END)

    workflow.add_edge("ESCALATED", END)

    

    return workflow.compile()

5.3 Deterministic Routers (graphs/router.py)

from graphs.state import LoopState

from typing import Literal

def route_spec_harness(state: LoopState) -> Literal["GATE_H1", "SPECIFY", "ESCALATED"]:

    if state.spec_harness and state.spec_harness.passed:

        return "GATE_H1"

    if state.retry_count < state.max_retries:

        state.retry_count += 1

        return "SPECIFY"

    state.escalation_reason = "Spec harness validation failed after max retries."

    return "ESCALATED"

def route_review(state: LoopState) -> Literal["GATE_H2", "IMPLEMENT", "DESIGN", "SPECIFY", "ESCALATED"]:

    outcome = state.code_artifacts.get("review_outcome", "pass")

    if outcome == "pass":

        return "GATE_H2"

    if state.retry_count >= state.max_retries:

        state.escalation_reason = f"Review failed with outcome '{outcome}' after max retries."

        return "ESCALATED"

    

    state.retry_count += 1

    if outcome == "fail_fix":

        return "IMPLEMENT"

    elif outcome == "fail_design":

        return "DESIGN"

    else:

        return "SPECIFY"



6. Step-by-Step Implementation Sequence

The implementing LLM should follow this exact build sequence:

Sprint 1: Core Foundation & Parallel Pilot Build

Step 1: Environment & Package Scaffolding

Initialize directory sdo-adk-engine/.

Create isolated virtual environment (python3 -m venv .venv).

Install google-adk>=2.5.0, google-genai, google-cloud-storage, pydantic>=2.0, fastapi, uvicorn, pytest.

Step 2: Core State Graph & Router Implementation

Implement graphs/state.py, graphs/router.py, and graphs/workflow.py.

Write unit tests in tests/unit/test_graph_routing.py verifying deterministic cyclic transitions and retry escalation to ESCALATED.

Step 3: Documental Agent & Two-Tier Policy Harness

Implement agents/documental.py with gemini-3.7-flash system prompt for Gherkin and frontmatter authoring.

Implement harnesses/tier1_static_rules.py (AST/Pydantic parser) and harnesses/tier2_policy_critic.py (PolicyAuditorAgent).

Wire harnesses/harness_node.py before Gate H1.

Step 4: Agent Gateway & BigQuery Managed MCP Integration

Implement gateway/auth.py and gateway/policy_interceptor.py enforcing dual-identity separation and node authorization.

Connect tools/bq_mcp_client.py targeting Google's Managed BigQuery MCP Server.

Step 5: Managed Sandbox & Implementer Agent

Implement tools/managed_sandbox.py wrapping Gemini Enterprise Managed Agent Linux containers.

Implement agents/implementer.py and agents/reviewer.py to compile SQL/Python and run test suites inside the sandbox.

Step 6: Gate H1/H2 Session Durability & WORM Audit Trail

Configure Agent Platform Runtime Session persistence.

Implement storage/worm_audit.py (Cloud Storage Object Retention Bucket Lock) and storage/crypto_shredding.py (Cloud KMS envelope encryption).

Enable Cloud Trace and OpenTelemetry logging exporting to BigQuery.

Step 7: End-to-End Walkthrough Test

Write integration test tests/integration/test_finance_loop_e2e.py simulating a full brief: Intake $\to$ Specify $\to$ Gate H1 $\to$ BQ Query $\to$ Sandbox Test $\to$ Gate H2 $\to$ Close $\to$ WORM Seal.

7. Mandatory Engineering Rules & Anti-Patterns to Avoid

================================================================================

                               CRITICAL RULES

================================================================================

1. NEVER LET AN LLM DECIDE GRAPH ROUTING: State transitions MUST be governed

   strictly by Python router functions inspecting typed Pydantic models.

2. NEVER POLL IN TIGHT LOOPS DURING HUMAN GATES: Gate H1 and H2 MUST use

   Agent Platform Runtime session suspension (scale-to-zero) with zero active compute.

3. NEVER POLLUTE GLOBAL PYTHON ENVIRONMENTS: Always execute in an isolated

   virtual environment (sdo-adk-engine/.venv) using google-adk>=2.5.0.

4. NEVER STORE UNENCRYPTED PII IN WORM AUDIT LOGS: User identifiers must be

   envelope-encrypted with Cloud KMS before landing in Object Retention buckets.

5. NEVER EXECUTE UNCONSTRAINED CODE ON LOCAL HOST: All code compilation, SQL

   execution, and unit testing MUST run inside Managed Agent Linux Sandboxes.

================================================================================



8. Summary of Companion Files

Product Requirements Document (PRD): prd_gcp_sdo_platform.md

Technical Design Document: design_doc_gcp_sdo_platform.md

Interactive HTML Visual Presentation: gcp_transition_proposal_and_weekly_plan.html

Meeting Notes & Transcript (Customer Context): Wallbox agents - 2026_08_14 14_30 CEST - Notes by Gemini.md