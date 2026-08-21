Product Requirements Document (PRD): SDO Platform on Google Cloud

Document Version: 2.0 (GCP Target Architecture)Author: Customer Engineering TeamCustomer Stakeholders: Pablo Murga (Engineering Lead), Mario Chueca, Cristabel Talavera, Pape CisseTarget Milestone: Production Pilot / Parallel Demonstration (September 15, 2026)Status: Approved for Implementation

1. Executive Summary & Vision

The Software Delivery Optimization (SDO) Platform is an enterprise-grade, human-supervised multi-agent orchestration engine designed to automate business-to-software and data delivery lifecycles for Wallbox.

The platform enables non-technical domain owners (e.g. Finance, Logistics, Firmware, Operations) to initiate software enhancements, data queries, and reporting views directly through Google Chat. The system orchestrates specialized AI agents through a strictly deterministic, cyclic state graph while mandating human sign-off at critical decision boundaries (Gate H1 for specifications and Gate H2 for deployment).

By transitioning from the initial AWS prototype to a cloud-native architecture on Google Cloud Platform (GCP)—leveraging Google ADK 2.0 State Graphs (adk.dev/graphs), Gemini 3.7 Flash, Agent Platform Runtime, Agent Gateway, Gemini Enterprise Managed Agent Sandboxes, and Google BigQuery Managed MCP—the platform achieves:

Zero-Compute Human Gate Durability: Approvals can remain open for days or weeks with zero active compute cost and zero queue visibility timeouts.

Strict Identity Governance: Enterprise user identity propagation from Google Workspace (OIDC) with contextual MCP authorization, cleanly separating Human Actions from Agent Actions.

Automated Compliance & WORM Auditing: Two-Tier Policy Harnesses enforce validation before human review, and tamper-evident event logging in Cloud Storage Object Retention satisfies SOC 2 Type II and GDPR "Right to be Forgotten" mandates.

2. Problem Statement & Customer Motivation

2.1 Current Bottlenecks in the AWS Prototype

Fragile State Engine & Token Limits: The prototype relies on custom YAML state loaders, custom run_leg re-entrant Python loops, and regex JSON parsing, coupled with Bedrock's 8K token ceiling and rolling context truncations.

Compute Inefficiencies & SQS Visibility Timeouts: Worker pods on EKS run continuously without true scale-to-zero. When human gates stay open for extended periods, SQS message visibility expires (ReceiptHandle has expired), causing duplicate executions and crash loops.

Missing Tooling Connectors (Epic E4): Data-centric requests (Finance node) deterministically crash at SPECIFY because external data store connectors (BigQuery) are missing.

Identity Delegation Dilemma: The prototype lacks granular user identity propagation, relying on static sandbox auth bypasses (LOCAL_BYPASS_OIDC=true).

Unsafe Code Execution: No isolated, ephemeral sandbox exists to safely compile, lint, and run unit tests against generated SQL/Python code before human review.

2.2 Core Product Goals

G1: 100% Deterministic Orchestration: AI models must reason inside designated states, but the transition graph, cyclic retries ($N \le 3$), and escalation backstops must be 100% deterministic in Python code.

G2: Enterprise Identity & Governance: Seamlessly authenticate Google Workspace business users via OIDC and enforce granular role-based access control (RBAC) on external tools.

G3: Serverless Elasticity & Multi-Week Gate Persistence: Support multi-week human approval delays with zero idle compute cost.

G4: Native Data & Sandbox Tooling: Direct, governed integration with BigQuery and ephemeral server-side Linux sandboxes for automated testing.

G5: Immutable Auditability & Compliance: Provide a cryptographic, tamper-evident audit trail for SOC 2 while supporting GDPR data suppression via crypto-shredding.

3. User Personas & Core Journeys

journey

    title SDO Platform End-User Journey (Finance Domain)

    section Intake & Spec

      Initiate Request in Google Chat: 5: Sarah (Finance)

      Schema Query & Draft Spec: 4: SDO Bot (Documental)

      Validate Gherkin & Metrics: 5: Two-Tier Policy Harness

    section Gate H1 (Human Review)

      Review Interactive Spec Card: 5: Sarah (Finance)

      Approve Specification: 5: Sarah (Finance)

    section Build & Test

      Generate Architecture Blueprint: 4: SDO Bot (Arquitecto)

      Execute Tests in Linux Sandbox: 5: SDO Bot (Managed Sandbox)

      Security & QA Review: 4: SDO Bot (Reviewer)

    section Gate H2 (Merge & Deploy)

      Review Final Deliverable Card: 5: Sarah (Finance)

      Approve Merge to Production: 5: Sarah (Finance)

    section Close & Audit

      Deploy BigQuery Query & Merge MR: 5: SDO Platform

      Seal WORM Audit Log & Schedule Watch: 5: Cloud Storage & Cloud Tasks

3.1 Primary Personas

Business Service Owner (e.g. Sarah, Financial Controller):

Needs: Submit business requirements in natural language; review clear, unambiguous acceptance criteria; approve deployments with one click.

Constraints: Zero knowledge of Git, CLI, SQL syntax, or Kubernetes.

Platform Operator / Cloud Architect (Pablo Murga, Mario Chueca):

Needs: Total visibility into agent trajectories, token costs, latency, and deterministic state transitions; zero maintenance of pinned worker clusters.

Constraints: Must ensure 99.9% uptime, multi-tenant node isolation, and zero runaway LLM loops.

CISO & Compliance Auditor:

Needs: Immutable, non-repudiable audit logs of every prompt, response, tool invocation, and human sign-off; SOC 2 Type II compliance; GDPR compliance.

4. 3-Plane Governance Model

The platform strictly segregates responsibilities across three immutable architectural planes:

Plane

Scope

Storage Substrate

Access Control & Immutability

Plane 1: Definitions & Contracts

Agent prompts, state graphs, FSM tables, policy rules, and Skill definitions.

Git (SDO-Master) & Agent Platform Skill Registry

Versioned, release-tagged, reviewed via standard pull requests.

Plane 2: Deliverables & Work Products

Specifications (spec.md), technical designs (design.md), generated code, and test suites.

GitLab Repositories (Branch / MR)

Feature branches tied to loop_id; merged into main upon Gate H2 approval.

Plane 3: Immutable Audit Event Log

Chronological record of prompts, tool outputs, policy harness evaluations, and human sign-offs.

Cloud Storage Object Retention (WORM Bucket)

WORM mode (Bucket Lock); tamper-evident; KMS crypto-shredding for GDPR.

5. Detailed Functional Requirements

flowchart TD

    INTAKE["B1: INTAKE<br><i>Ingress & Identity Interception</i>"] --> SPECIFY["B2: SPECIFY<br><i>Documental Agent (Gemini 3.7 Flash)</i>"]

    SPECIFY --> HARNESS1["B6.1: Spec Harness<br><i>Tier 1 AST + Tier 2 Policy Critic</i>"]

    

    HARNESS1 -->|Pass| GATE_H1{{"B3: GATE_H1<br><i>Human Spec Review (Google Chat)</i>"}}

    HARNESS1 -->|Fail & Retries < 3| SPECIFY

    HARNESS1 -->|Retries >= 3| ESCALATED["B1.3: ESCALATED<br><i>Human Backstop</i>"]

    GATE_H1 -->|Approved| DESIGN["B4: DESIGN<br><i>Arquitecto Agent</i>"]

    GATE_H1 -->|Rejected / Cancelled| LOOP_CLOSED["CLOSED"]

    DESIGN --> IMPLEMENT["B5: IMPLEMENT<br><i>Managed Agent Linux Sandbox</i>"]

    IMPLEMENT --> REVIEW["B6: REVIEW<br><i>Reviewer Agent + Security Linter</i>"]

    

    REVIEW -->|Pass| GATE_H2{{"B7: GATE_H2<br><i>Final Merge Approval (Google Chat)</i>"}}

    REVIEW -->|Fail Fix| IMPLEMENT

    REVIEW -->|Fail Design| DESIGN

    REVIEW -->|Fail Spec| SPECIFY

    GATE_H2 -->|Approved| CLOSE["B8: CLOSE<br><i>GitLab MR Merge & Deploy</i>"]

    CLOSE --> WATCH["B9: WATCH<br><i>Asynchronous Telemetry Check</i>"]

    WATCH --> DONE(["DONE"])

Block B1: Client Ingress & Agent Gateway

RF-B1-01 (Google Chat Integration): The platform shall provide a Google Chat webhook receiver capable of ingesting brief prompts and posting interactive Adaptive Cards.

RF-B1-02 (Identity Interception): The Agent Gateway shall intercept all incoming requests, validate the user's Google Workspace OIDC token, and attach the user's verified corporate identity (email, sub, roles) to the session context.

RF-B1-03 (Actor Separation): Every action in the system shall be explicitly classified and logged as either a Human Action (initiated/approved by OIDC user) or an Agent Action (executed by system service identity).

RF-B1-04 (Multi-Tenant Node Partitioning): Requests shall be tagged with a domain node_id (finance, logistics, firmware). The Agent Gateway shall enforce access control ensuring users only initiate loops in authorized domains.

Block B2: Specification Generation (SPECIFY)

RF-B2-01 (Documental Agent): A specialized LlmAgent powered by gemini-3.7-flash shall synthesize raw user briefs into a formal spec.md.

RF-B2-02 (Structured Schema): spec.md shall strictly adhere to:

YAML Frontmatter (id, title, node_id, created_at, target_repository).

Acceptance Criteria formatted in unambiguous Gherkin syntax (Feature, Scenario, Given, When, Then).

Mandatory Business Metrics Block (baseline values, target SLAs, telemetry thresholds).

RF-B2-03 (Context Exploration): The agent shall dynamically query the BigQuery Managed MCP Server to inspect table schemas and column statistics before finalizing the specification.

Block B3: Gate H1 & Session Persistence (GATE_H1)

RF-B3-01 (Interactive Approval Card): Upon passing pre-harness checks, the engine shall dispatch an interactive card to the user's Google Chat space containing the specification summary, Gherkin scenarios, and action buttons ([Approve Spec], [Request Changes]).

RF-B3-02 (Serverless Scale-to-Zero): The execution session must automatically freeze and persist state in Agent Platform Runtime Session & Memory Banks. The container shall scale to zero with zero idle CPU/RAM usage.

RF-B3-03 (Multi-Week Durability): Gate H1 shall support being suspended indefinitely (hours, days, or weeks) without timing out, failing, or requiring polling loops.

Block B4: Architecture & Technical Design (DESIGN)

RF-B4-01 (Arquitecto Agent): Upon Gate H1 sign-off, the arquitecto agent shall generate design.md detailing technical components, SQL queries, DDL statements, dependencies, and execution sequences.

RF-B4-02 (Test Plan Authoring): The design must include an explicit test plan defining unit, integration, and negative boundary test cases to be executed in the sandbox.

Block B5: Implementation & Ephemeral Sandbox (IMPLEMENT)

RF-B5-01 (Managed Agent Sandbox Provisioning): The implementer agent shall spin up an ephemeral Gemini Enterprise Managed Agent Sandbox (isolated Ubuntu Linux container).

RF-B5-02 (Automated Test Execution): Inside the sandbox, the agent shall generate code, compile SQL/Python scripts, and execute test suites (pytest, sqlfluff, bigquery-mock).

RF-B5-03 (Isolation): Sandboxes must be hermetically isolated with strictly controlled egress, ensuring no unapproved network calls or access to production datasets.

Block B6: Review & Two-Tier Policy Harness (REVIEW)

RF-B6-01 (Tier 1 Deterministic Static Rules): Python AST and Pydantic validators shall verify:

Frontmatter schema completeness.

Valid Gherkin AST syntax.

Zero forbidden imports or hardcoded credentials.

RF-B6-02 (Tier 2 Policy Auditor Sub-Agent): A specialized PolicyAuditorAgent (gemini-3.7-flash) shall evaluate qualitative criteria:

Verification that code strictly implements all Gherkin scenarios.

SOC 2 compliance and personal data handling compliance.

RF-B6-03 (Deterministic Back-Edge Routing):

pass $\rightarrow$ Transition to GATE_H2.

fail_fix $\rightarrow$ Return diagnostic error to IMPLEMENT (max 3 retries).

fail_design $\rightarrow$ Return architectural discrepancy to DESIGN.

fail_definition $\rightarrow$ Return requirement conflict to SPECIFY.

retries_exhausted $\rightarrow$ Transition to ESCALATED.

Block B7: Gate H2 & Final Merge Approval (GATE_H2)

RF-B7-01 (Final Deliverable Card): The engine shall render an interactive card in Google Chat displaying the validated deliverable summary, test execution pass rate (100%), sample output data, and the GitLab Merge Request link.

RF-B7-02 (Mandatory Human Sign-off): No code or query shall be deployed or merged into main without explicit, authenticated human approval from an authorized service owner.

Block B8: Close, Merge & Deployment (CLOSE)

RF-B8-01 (GitLab Sealing): Upon Gate H2 approval, the platform shall squash feature branch commits, merge the MR into main, and generate a semantic release tag.

RF-B8-02 (Live Resource Deployment): The platform shall deploy the BigQuery Scheduled Query or production view.

RF-B8-03 (Audit Event Sealing): The entire execution history, artifact hashes, and OIDC approval signatures shall be sealed into the WORM audit bucket.

Block B9: Long-Term Watch Checkpoint (WATCH)

RF-B9-01 (Asynchronous Scheduling): The platform shall schedule an asynchronous telemetry checkpoint for Day 30 post-deployment using Cloud Tasks.

RF-B9-02 (Health Evaluation): On Day 30, the watcher agent evaluates production error logs and query latency metrics in BigQuery, reporting a final health summary to Google Chat.

Block B10: Multi-Tenancy & Dynamic Skill Registry

RF-B10-01 (Tenant Isolation): Every execution runs inside an isolated Agent Platform Runtime session. No session can read or write to another session's state.

RF-B10-02 (Dynamic Skill Resolution): When a request targets a specific node (finance, logistics), the agent dynamically resolves and binds authorized domain tools from the Agent Platform Skill Registry.

6. Non-Functional Requirements (NFRs)

ID

Category

Requirement Description

Target Metric

RNF-01

Durability

Zero state loss during human gate interruptions; resilient to worker crashes.

99.999% state recovery

RNF-02

Elasticity

Compute must scale to zero during human gate review pauses.

0 active vCPU/RAM parked

RNF-03

Latency

Turnaround time for agent reasoning steps (SPECIFY, DESIGN).

≤ 10 seconds per turn

RNF-04

Observability

100% of LLM prompts, raw responses, and tool calls exported to Cloud Trace & BigQuery.

100% trace capture

RNF-05

Immutability

Audit logs stored in Cloud Storage with Object Retention (Bucket Lock).

Non-deletable / WORM compliant

RNF-06

GDPR Compliance

Crypto-shredding (per-subject Cloud KMS key destruction) for personal data deletion requests.

Instant irrecoverability

RNF-07

Security & IAM

Strict separation of human user credentials (OIDC) from machine agent service identities.

Least-privilege RBAC

7. Acceptance Criteria & Definition of Done for September 15 Demo

End-to-End Finance Walkthrough: User submits a currency variance brief via Google Chat; platform generates Gherkin spec; user approves Gate H1 card.

Governed BigQuery Querying: documental and implementer agents query live BigQuery tables via Google BigQuery Managed MCP Server without custom API code.

Managed Sandbox Validation: Code compiled and tested inside an isolated Gemini Enterprise Managed Agent Linux container with 100% unit test pass rate.

Zero-Compute Interruption: Gate H1 intentionally left open for >24 hours without worker crashes or SQS timeout errors.

Gate H2 & Audit Seal: User approves Gate H2 in Google Chat; BigQuery view deploys; audit record is verified in Cloud Storage WORM bucket.

Traceability: Full OpenTelemetry trace is queryable in BigQuery and visible in Cloud Trace.