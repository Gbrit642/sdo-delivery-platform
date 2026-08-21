# SDO Platform Documentation Directory Map

This directory organizes all project documentation into three structured lifecycle phases:

```
docs/
├── 01_requirements/                      # Provided BEFORE implementation (Ground Truth Customer Needs)
│   ├── prd_v2.md                         # Product Requirements Document (PRD v2.0 - GCP Target Architecture)
│   ├── technical_design_doc.md           # Technical Architecture & System Design Blueprint
│   └── executive_summary.md              # Executive Problem Statement & AWS Prototype Bottleneck Analysis
│
├── 02_architecture_and_decisions/        # Architecture Invariants, System Models & ADRs
│   ├── architectural_decisions.md        # Architectural Decision Records (ADR-1 through ADR-8)
│   ├── context_blueprint_agents.md       # LLM Context Blueprint & Invariants Guide
│   └── system_architecture.md            # 3-Plane Governance Model & Dual-Identity Gateway
│
└── 03_post_implementation_and_operations/# Created AFTER implementation (Operational Runbooks & Handover)
    ├── gcp_console_walkthrough.md        # 9-Step GCP Console Human Verification Guide
    ├── customer_handover_guide.md        # Production Handover, Prerequisites & Runbook
    ├── live_demo_script.md               # Interactive Web Dashboard (Chrome) & A2A Demo Script
    ├── validation_matrix.md              # Test Matrix covering SC-01..05 & NEG-01..07
    ├── gemini_enterprise_a2a.md          # Google A2A v1.0 Wire Protocol & SSE Streaming Guide
    ├── org_policy_and_iap_guide.md       # IAP Load Balancer & Org Policy Ingress Guide
    ├── google_chat_setup.md              # Google Chat App Registration & Webhook Setup
    └── replication_guide.md              # Clean Environment Setup & Deployment Replication
```

---

## 📑 1. Phase 1: Requirements & Ground Truth (Given BEFORE Implementation)

| Document | Purpose | Audience |
|---|---|---|
| [**`01_requirements/prd_v2.md`**](./01_requirements/prd_v2.md) | Ground truth customer product requirements: functional blocks B1–B10, non-functional requirements RNF-01–RNF-07, and success metrics. | Product Managers & Engineers |
| [**`01_requirements/technical_design_doc.md`**](./01_requirements/technical_design_doc.md) | Core technical architecture, ADK 2.0 state graph design, and BigQuery MCP integration design. | Cloud Architects |
| [**`01_requirements/executive_summary.md`**](./01_requirements/executive_summary.md) | Detailed analysis of AWS prototype failure modes (EKS costs, SQS timeouts, Bedrock 8K ceiling, missing DB connectors). | Stakeholders & Leads |

---

## 🏛️ 2. Phase 2: Architecture & Decision Records

| Document | Purpose | Key Topics Covered |
|---|---|---|
| [**`02_architecture_and_decisions/architectural_decisions.md`**](./02_architecture_and_decisions/architectural_decisions.md) | Key Architectural Decisions (ADR-1 through ADR-8). | Deterministic routing, gemini-3.7-flash, non-technical guardrails, 3-plane storage, KMS exclusion, IAP ingress. |
| [**`02_architecture_and_decisions/context_blueprint_agents.md`**](./02_architecture_and_decisions/context_blueprint_agents.md) | Context blueprint explaining what was built, why, and critical invariants for future coding agents. | LLMs & Autonomous Agents |
| [**`02_architecture_and_decisions/system_architecture.md`**](./02_architecture_and_decisions/system_architecture.md) | High-level system architecture, Dual-Identity Protocol, and Two-Tier Quality Harness. | System Engineers |

---

## 🚀 3. Phase 3: Post-Implementation & Operations (Created AFTER Implementation)

| Document | Purpose | Key Topics Covered |
|---|---|---|
| [**`03_post_implementation_and_operations/gcp_console_walkthrough.md`**](./03_post_implementation_and_operations/gcp_console_walkthrough.md) | Visual guide for technical engineers to verify all deployed services in the Google Cloud Console. | Cloud Run, BigQuery, Cloud Storage WORM, Cloud Trace, IAM. |
| [**`03_post_implementation_and_operations/customer_handover_guide.md`**](./03_post_implementation_and_operations/customer_handover_guide.md) | Step-by-step handover runbook for customer operators. | Quickstart, Terraform deployment, Human Gate operations. |
| [**`03_post_implementation_and_operations/live_demo_script.md`**](./03_post_implementation_and_operations/live_demo_script.md) | Interactive demo script across Web Dashboard (Chrome), Gemini Enterprise, and REST API. | Finance FX Variance, Sales Stage Conversion, Gate approvals. |
| [**`03_post_implementation_and_operations/validation_matrix.md`**](./03_post_implementation_and_operations/validation_matrix.md) | Mapping of all acceptance scenarios (SC-01 to SC-05) and security tests (NEG-01 to NEG-07). | 50/50 automated test suite coverage. |
| [**`03_post_implementation_and_operations/gemini_enterprise_a2a.md`**](./03_post_implementation_and_operations/gemini_enterprise_a2a.md) | Authoritative reference for Google A2A v1.0 wire protocol, Server-Sent Events, and Pydantic schemas. | SSE streaming, role="agent", parts, messageId, typed artifacts list. |
| [**`03_post_implementation_and_operations/google_chat_setup.md`**](./03_post_implementation_and_operations/google_chat_setup.md) | Google Workspace Developer Console setup for Google Chat app registration. | Webhook URL, cardsV2 interactive buttons. |
| [**`03_post_implementation_and_operations/replication_guide.md`**](./03_post_implementation_and_operations/replication_guide.md) | Guide for replicating the deployment in a clean GCP project. | Prerequisites, Terraform apply, service deployment. |
| [**`03_post_implementation_and_operations/auth_credential_delegation_flow.html`**](./03_post_implementation_and_operations/auth_credential_delegation_flow.html) <br>*(Live Cloud Run: [**Launch Visualizer**](https://html-interactive-visualizer-c2rnccvaca-ew.a.run.app/auth_credential_delegation_flow.html))* | Interactive visual HTML guide for cross-platform BigQuery & Databricks MCP credential delegation. | Dual-Identity Protocol, SVG sequence diagram, Gherkin specs, BigQuery federated SQL. |

