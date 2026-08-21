Technical Design Document: SDO Platform on Google Cloud

Document Type: Google Cloud Architecture Design Blueprint (Level 300/400)Target Audience: Cloud Architects, Enterprise Operators & Security EngineersCustomer: Wallbox (Pablo Murga, Mario Chueca)Lead Authors: Google Customer Engineering (Practice CE)Status: Approved Reference ArchitectureTarget Milestone: Parallel Pilot & Technical Validation (September 15, 2026)

1. System Design & Reference Architecture (The "What & Why")

1.1 Executive Architectural Overview

The Software Delivery Optimization (SDO) Platform is an enterprise multi-agent system that converts business requests submitted via Google Chat into production-ready software deliverables and analytical queries.

The architecture solves the core fragility of the legacy AWS prototype (pinned EKS pods, SQS visibility timeout crashes, custom regex state engines, missing data connectors, and unconstrained code execution) by re-platforming onto a fully governed, cloud-native Google Cloud stack:

flowchart TD

    subgraph ClientPlane ["1. Client & Ingress Plane"]

        User["Business Owner (Google Chat)"] -->|OIDC JWT + Brief| AGW["Agent Gateway (Auth & Policy Boundary)"]

    end

    subgraph RuntimePlane ["2. Agent Platform Runtime (ADK 2.0 State Graph Engine)"]

        AGW -->|Authorize & Forward| AR["Agent Platform Runtime (Session & Memory Banks)"]

        

        subgraph GraphEngine ["ADK 2.0 State Graph (gemini-3.7-flash)"]

            INTAKE["INTAKE"] --> SPECIFY["SPECIFY (documental)"]

            SPECIFY --> HARNESS1["Spec Harness (Tier 1 AST + Tier 2 Policy Critic)"]

            HARNESS1 -->|Pass| GATE_H1{{"GATE H1 (Human Spec Sign-off)"}}

            HARNESS1 -->|Fail Fix| SPECIFY

            

            GATE_H1 -->|Approved| DESIGN["DESIGN (arquitecto)"]

            DESIGN --> IMPLEMENT["IMPLEMENT (Managed Sandbox)"]

            IMPLEMENT --> REVIEW["REVIEW (Reviewer Agent)"]

            REVIEW -->|Pass| GATE_H2{{"GATE H2 (Final Merge Sign-off)"}}

            REVIEW -->|Fail Fix| IMPLEMENT

            REVIEW -->|Fail Design| DESIGN

            

            GATE_H2 -->|Approved| CLOSE["CLOSE (MR Merge & Deploy)"]

            CLOSE --> WATCH["WATCH (Day 30 Health Check)"]

            WATCH --> DONE(["DONE"])

        end

    end

    subgraph GovernedTools ["3. Governed Tools & Ephemeral Sandboxes"]

        AR <-->|Direct Schema & Queries| BQ_MCP["Google BigQuery Managed MCP"]

        AR <-->|Branch & MR Sealing| GL_MCP["GitLab MCP Server"]

        AR <-->|Domain Tools per Node| REG["Agent Platform Skill Registry"]

        IMPLEMENT <-->|Server-Side Code Execution| SANDBOX["Managed Agent Linux Containers"]

    end

    subgraph GovernanceTrace ["4. Observability & WORM Audit Substrate"]

        AR -->|OpenTelemetry Spans & Prompt Logs| TRACE["Cloud Trace & Cloud Logging -> BigQuery Sink"]

        AR -->|Immutable JSON Traces (KMS Shredding)| GCS_WORM["Cloud Storage Object Retention (WORM)"]

        AR -->|Asynchronous Day 30 Resume| CTASKS["Cloud Tasks / Cloud Scheduler"]

    end



1.2 Service Selection & Decision Matrix

Layer / Functional Need

Selected GCP Solution

Alternatives Evaluated

Rationale & Architectural Trade-offs

Agent Orchestration

Google ADK 2.0 State Graphs (adk.dev/graphs)

LangGraph, CrewAI, Custom YAML FSM

ADK 2.0 State Graphs provide strict compile-time determinism, native cyclic retry routing, typed Pydantic outcome schemas, and seamless Agent Platform Runtime integration without third-party framework lock-in.

Core Reasoning Model

Gemini 3.7 Flash

Claude 3.5 Sonnet on Bedrock, GPT-4o

Gemini 3.7 Flash offers a 2M token context window (eliminating Bedrock 8K truncations), sub-second latency, superior structured JSON adherence, and native multimodal ERD/diagram processing at a fraction of the cost.

Serverless Compute & State

Agent Platform Runtime

Pinned EKS Pods + KEDA, Cloud Run DIY

Managed serverless execution environment with native session state hydration and scale-to-zero. Eliminates idle worker costs and SQS ReceiptHandle has expired visibility timeout crashes during multi-week human gate pauses.

Security & Identity Boundary

Agent Gateway

Static Service Accounts, API Gateway

Enforces strict dual-identity boundaries: accepts human Google Workspace OIDC tokens, verifies tenant node permissions, and performs token exchange before proxying calls to external MCP servers.

Code Execution Sandbox

Gemini Enterprise Managed Agent Sandboxes

DIY Docker Daemon, Local Subprocess

Serverless, ephemeral Ubuntu Linux containers provisioned server-side for safe execution of unit tests, SQL compilation, and security linters without exposing the host OS.

Enterprise Data Connector

Google BigQuery Managed MCP

Custom REST API, DIY Postgres Connector

Native first-party Model Context Protocol server provided by Google. Enables instant schema introspection and governed querying for the Finance node with zero custom code (resolving Epic E4).

Immutable Audit Storage

Cloud Storage Object Retention (WORM) + KMS

DynamoDB + S3 Object Lock, Bigtable

Satisfies PRD RF-B6-16 (tamper-evident immutable audit log for SOC 2 Type II) and RNF-10 (GDPR Right to be Forgotten via per-user Cloud KMS envelope encryption / crypto-shredding).

Telemetry & Observability

Cloud Trace + Cloud Logging $\rightarrow$ BigQuery Sink

Datadog, Prometheus/Grafana

Built-in OpenTelemetry export capturing complete prompt/response trajectories and tool calls into BigQuery for automated evaluation datasets (adk eval).

2. Subsystem Deep Dives & Data Flows

2.1 Ingress, Identity & Agent Gateway Governance

sequenceDiagram

    autonumber

    actor User as Business User (Sarah)

    participant Chat as Google Chat

    participant AGW as Agent Gateway

    participant AR as Agent Platform Runtime

    participant BQ as BigQuery Managed MCP

    User->>Chat: Submit Brief ("Create Weekly FX Variance View")

    Chat->>AGW: Dispatch Webhook (OIDC JWT + Payload)

    Note over AGW: 1. Validate OIDC Token & Roles<br/>2. Classify: Actor = Human (sarah@wallbox.com)<br/>3. Verify Node Access: node_id == "finance"

    AGW->>AR: Initialize Session (session_id = loop_id)

    AR->>BQ: Query Schema (Delegated Token)

    Note over AGW,BQ: Agent Gateway enforces least-privilege table permissions

    BQ-->>AR: Return Table Metadata (finance_billing.invoices)

    AR-->>Chat: Post Interactive Gate H1 Card (Adaptive Card)

Dual-Identity Governance Protocol

Human Action Classification: When a user initiates a brief or clicks an approval button in Google Chat, the request carries an OIDC JWT. Agent Gateway verifies the signature against Google Workspace public keys, extracts claims (email, sub, department), and logs the event with actor_type: "human".

Agent Action Classification: When the engine generates code, compiles SQL, or executes internal state transitions, the request executes under the Agent Service Identity (sa-sdo-engine@project.iam.gserviceaccount.com).

MCP Tool Authorization: When agents invoke external tools (e.g. querying BigQuery), Agent Gateway evaluates the human's IAM permissions (e.g., Is Sarah authorized to access the finance dataset?) before proxying the call to the BigQuery Managed MCP Server.

2.2 ADK 2.0 Deterministic State Graph Engine

The core lifecycle runs on ADK State Graphs (adk.dev/graphs), strictly enforcing deterministic routing and eliminating rogue model transitions:

from google.adk.graphs import StateGraph, START, END

from pydantic import BaseModel, Field

from typing import Literal, Optional

class LoopState(BaseModel):

    loop_id: str

    node_id: str

    brief: str

    spec_content: Optional[str] = None

    design_content: Optional[str] = None

    code_artifacts: dict[str, str] = Field(default_factory=dict)

    retry_count: int = 0

    gate_h1_approved: bool = False

    gate_h2_approved: bool = False

    harness_failures: list[str] = Field(default_factory=list)

def route_spec_harness(state: LoopState) -> Literal["GATE_H1", "SPECIFY", "ESCALATED"]:

    if not state.harness_failures:

        return "GATE_H1"

    if state.retry_count < 3:

        return "SPECIFY"

    return "ESCALATED"

def route_review(state: LoopState) -> Literal["GATE_H2", "IMPLEMENT", "DESIGN", "SPECIFY", "ESCALATED"]:

    outcome = state.code_artifacts.get("review_outcome", "pass")

    if outcome == "pass":

        return "GATE_H2"

    if state.retry_count >= 3:

        return "ESCALATED"

    if outcome == "fail_fix":

        return "IMPLEMENT"

    if outcome == "fail_design":

        return "DESIGN"

    return "SPECIFY"

# Build Deterministic Graph

workflow = StateGraph(LoopState)

workflow.add_node("INTAKE", intake_node)

workflow.add_node("SPECIFY", specify_agent_node)

workflow.add_node("SPEC_HARNESS", spec_harness_node)

workflow.add_node("GATE_H1", gate_h1_human_node)

workflow.add_node("DESIGN", design_agent_node)

workflow.add_node("IMPLEMENT", implement_sandbox_node)

workflow.add_node("REVIEW", review_agent_node)

workflow.add_node("GATE_H2", gate_h2_human_node)

workflow.add_node("CLOSE", close_merge_node)

workflow.add_node("WATCH", watch_checkpoint_node)

workflow.add_node("ESCALATED", human_escalation_node)

workflow.add_edge(START, "INTAKE")

workflow.add_edge("INTAKE", "SPECIFY")

workflow.add_edge("SPECIFY", "SPEC_HARNESS")

workflow.add_conditional_edges("SPEC_HARNESS", route_spec_harness)

workflow.add_edge("GATE_H1", "DESIGN")

workflow.add_edge("DESIGN", "IMPLEMENT")

workflow.add_edge("IMPLEMENT", "REVIEW")

workflow.add_conditional_edges("REVIEW", route_review)

workflow.add_edge("GATE_H2", "CLOSE")

workflow.add_edge("CLOSE", "WATCH")

workflow.add_edge("WATCH", END)



2.3 Two-Tier Policy & Compliance Harness Architecture

To guarantee that no hallucinated or malformed specification reaches human reviewers at Gate H1 or H2, the platform implements a Two-Tier Hybrid Harness Pipeline:

flowchart LR

    Input["Generated Artifact (spec.md / code)"] --> Tier1["Tier 1: Deterministic Static Rules<br>• AST Parser: YAML Frontmatter<br>• Gherkin Syntax: Given/When/Then<br>• Mandatory Metrics Block Present<br>• AST Linter: Zero Hardcoded Keys"]

    

    Tier1 -->|Static Checks Passed| Tier2["Tier 2: Policy Auditor Sub-Agent<br>• gemini-3.7-flash Critic<br>• Evaluates SOC 2 Compliance<br>• Validates Scope vs Original Brief<br>• Tests Edge Case Coverage"]

    

    Tier1 -->|Syntax Error| Fail["Harness Result: FAIL<br>Emit Diagnostic Violations"]

    Tier2 -->|Policy Violation| Fail

    Tier2 -->|Auditor Approved| Pass["Harness Result: PASS<br>Transition to Gate H1 / H2"]



Tier 1 (Deterministic Static Code Verifier):

Parses spec.md with Python AST and Pydantic schemas.

Enforces exact Gherkin keyword syntax (Feature:, Scenario:, Given, When, Then).

Validates mandatory metrics block presence (target_sla, baseline_error_rate).

Tier 2 (Policy Auditor Sub-Agent):

Executes PolicyAuditorAgent (gemini-3.7-flash) with a strict compliance system prompt.

Checks for personal data isolation (GDPR), Wallbox financial coding standards, and negative test completeness.

2.4 Serverless Code Execution via Managed Agent Sandboxes

When the implementer agent writes SQL transformations or Python validation scripts, it triggers an ephemeral Gemini Enterprise Managed Agent Sandbox:

Environment: Serverless, isolated Ubuntu Linux container provisioned on demand.

Capabilities: Python 3.11+, pytest, sqlfluff, Google Cloud client libraries.

Security Guardrails:

Strict network egress filtering (no access to external internet or production databases).

Storage is ephemeral; containers are destroyed immediately upon test completion.

Test execution logs and coverage reports are extracted and attached to the session context for the reviewer agent.

2.5 Multi-Week Gate Persistence & Zero Parked Compute

sequenceDiagram

    autonumber

    participant Engine as ADK State Graph

    participant Runtime as Agent Platform Runtime

    participant Mem as Session & Memory Store

    actor Sarah as Sarah (Finance Lead)

    participant Tasks as Cloud Tasks

    Engine->>Runtime: Hit Gate H1 -> require_human_confirmation()

    Runtime->>Mem: Snapshot State (Snap_Prime)

    Note over Runtime: Container Scales to ZERO (0 vCPU / 0 RAM)

    Note over Sarah: Sarah is away on leave for 10 Days...

    Sarah->>Runtime: Click [Approve] in Google Chat (10 Days Later)

    Runtime->>Mem: Hydrate State (Snap_Prime)

    Runtime->>Engine: Resume Leg 2 (DESIGN & IMPLEMENT)

    Note over Engine: Execution completes seamlessly

    Engine->>Tasks: Register Day 30 Watch Timer (+30 Days Dispatch)



Elimination of SQS Visibility Expirations: In AWS, SQS messages expire after hours (ReceiptHandle has expired), causing worker crash loops. In GCP, Agent Platform Runtime Sessions store serialized state snapshots in managed distributed memory banks.

Cost Efficiency: While waiting for human input at Gate H1 or H2, compute scales to 0 active instances, parking $0 in compute costs.

2.6 WORM Audit Substrate & GDPR Crypto-Shredding

To satisfy SOC 2 Type II (PRD RF-B6-16) and GDPR Right to be Forgotten (PRD RNF-10):

WORM Storage: Every state snapshot, prompt trajectory, tool output, and human signature is streamed as a signed JSON record to a Cloud Storage Bucket with Object Retention (Bucket Lock) in WORM mode. Objects cannot be modified or deleted by any user or administrator within the retention period (e.g. 7 years).

Crypto-Shredding (Per-Subject Envelope Encryption):

Identifiable user data (e.g. employee names, user emails in briefs) is encrypted using a per-user Cloud KMS key before writing to the WORM bucket.

If a user exercises their GDPR "Right to be Forgotten", the corresponding Cloud KMS key is permanently destroyed. The encrypted payload becomes mathematically irrecoverable, satisfying GDPR without violating the structural immutability of the WORM audit log.

3. Capacity Sizing, Elasticity & Cost Modeling

3.1 Compute Sizing Model

Because the system runs serverlessly on Agent Platform Runtime and Managed Agent Sandboxes, there is zero baseline compute cost during idle or human review periods:

$$\text{Monthly Cost} = \text{Ingress Invocations} + \text{Agent Reasoning Tokens} + \text{Sandbox Test Seconds} + \text{WORM Storage}$$

Component

Sizing Parameter

Unit Cost

Estimated Monthly Usage (100 Loops)

Projected Monthly Cost

Gemini 3.7 Flash

Input: ~50K tokens/loop

Output: ~10K tokens/loop

$0.075 / 1M in

$0.30 / 1M out

5M Input Tokens

1M Output Tokens

$0.68

Agent Platform Runtime

Session execution

Per vCPU-second

~300 active execution seconds/loop

$12.50

Managed Agent Sandboxes

Linux test containers

Per execution-second

~120 test seconds/loop

$8.20

BigQuery Managed MCP

Schema & query exploration

BigQuery On-Demand

~200 MB scanned/loop (20 GB total)

$0.12

Cloud Storage WORM

Audit log retention

$0.02 / GB-month

~50 MB audit JSON/loop

$0.10

Cloud Trace & Logging

OpenTelemetry spans

Free tier + log storage

~100K spans/month

$0.50

Total Estimated Cost

—

—

100 End-to-End Delivery Loops

~$22.10 / month

Note: Compared to the pinned AWS EKS baseline (~$350+/month for idle worker nodes), GCP serverless delivers a >90% cost reduction while providing infinite scale-to-zero durability.

4. Implementation Roadmap & Sprint Plan

4.1 Sprint Breakdown (Target: September 15 Demo)

gantt

    title Wallbox SDO Platform — GCP Implementation Sprints

    dateFormat  YYYY-MM-DD

    section Sprint 1 (Week 1)

    ADK State Graph & FSM Engine       :a1, 2026-08-18, 1d

    Two-Tier Policy Harness           :a2, 2026-08-19, 1d

    Agent Gateway & BigQuery MCP       :a3, 2026-08-20, 1d

    Managed Sandboxes & Sessions       :a4, 2026-08-21, 1d

    End-to-End Walkthrough & Demo Prep :a5, 2026-08-22, 1d

    section Sprint 2 (Week 2-3)

    GitLab MCP Sealing & Work Item Sync:b1, 2026-08-25, 4d

    Cloud Tasks Day 30 Watcher Wiring :b2, 2026-08-29, 3d

    KMS Crypto-Shredding Pipeline      :b3, 2026-09-02, 3d

    section Final Validation

    Parallel Run vs AWS Prototype      :c1, 2026-09-08, 5d

    Customer Sign-Off (Sep 15 Demo)    :milestone, c2, 2026-09-15, 0d



5. Security & Pre-Sales Guardrails

5.1 Pre-Sales Isolation

The parallel demonstration environment is deployed into an isolated Google Cloud project with VPC Service Controls (VPC-SC) perimeter protection.

All BigQuery test queries operate against synthetic or anonymized billing datasets.

5.2 Legal & Engagement Boundaries

[!IMPORTANT] Advisory Reference Architecture: This technical design document, starter configurations, and ADK graph definitions are provided for architectural evaluation and demonstration purposes. Google provides these assets on an "as-is" basis.

Customer Engineering Boundary: Wallbox's internal engineering team retains full ownership and authority over production deployments, GitLab repository access, and live database permissions. Google Customer Engineering operates strictly in an advisory and enablement capacity.