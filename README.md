# Wallbox SDO Platform — Google Cloud ADK 2.0 Engine

> **Autonomous, Human-Supervised Software & Data Delivery Platform on Google Cloud Platform**  
> **Customer:** Wallbox • **Target GCP Project:** `managed-agent-504409` • **Core Reasoning Model:** `gemini-3.7-flash`

---

## ⚡ Highlights & Key Innovations

- **Gemini 3.7 Flash Reasoning Engine:** 2,000,000 token context window, eliminating legacy AWS token truncation.
- **100% Deterministic ADK 2.0 State Graph:** Strict Python routing logic governing all state transitions and retry budgets. LLMs never decide graph transitions.
- **Scale-to-Zero Human Governance:** Human gates (`Gate H1` and `Gate H2`) persist state at $0 compute cost with zero timeout crashes.
- **Multi-Domain Skill Registry:** Modular YAML manifests (`finance.yaml`, `sales.yaml`, `firmware.yaml`, `marketing.yaml`) governing intake, spec policies, and post-implementation acceptance criteria.
- **Two-Tier Quality Harness:** Tier 1 AST/Pydantic static parsing + Tier 2 `PolicyAuditorAgent` compliance critic.
- **Governed BigQuery & GitHub Connectors:** BigQuery Managed MCP connector and GitHub client with offline mock mode.
- **Ephemeral Managed Sandboxes:** Isolated Linux container runner executing `pytest` and `sqlfluff` in isolation.
- **WORM Audit Trail:** Cloud Storage Object Retention (Bucket Lock) for tamper-evident compliance.
- **Observability & Analytics:** Cloud Trace (OpenTelemetry) + native BigQuery Agent Analytics plugin + Gemini Enterprise evaluation metrics.
- **Infrastructure as Code:** 100% automated Terraform scripts ready to deploy in `managed-agent-504409`.

---

## 🚀 Quickstart

### 1. Installation & Environment
```bash
cd sdo-adk-engine
pip install -e ".[dev]"
```

### 2. Run Test Suite (Unit & End-to-End Integration)
```bash
pytest tests/ -v
```

### 3. Launch Web Dashboard & REST API
```bash
python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8080 --reload
```
Open **`http://localhost:8080`** in **Google Chrome** to interactively launch delivery loops and sign off on human gates.

---

## 📁 Repository Structure

```
sdo-adk-engine/
├── config/              # Application settings and domain node definitions
├── gateway/             # OIDC authentication, policy interceptor, Google Chat adapter
├── registry/            # Multi-domain Skill Registry and YAML manifests (finance, sales, etc.)
├── graphs/              # Master LoopState schema, deterministic routers, StateGraph workflow
├── agents/              # Gemini 3.7 Flash sub-agents (Documental, Arquitecto, Implementer, Reviewer, Watcher)
├── harnesses/           # Two-Tier Quality Harness (Tier 1 AST + Tier 2 Policy Auditor)
├── tools/               # BigQuery MCP, GitHub client, and Managed Agent Linux Sandbox
├── storage/             # WORM audit trail writer in Cloud Storage Object Retention
├── observability/       # OpenTelemetry Cloud Trace & BigQuery Agent Analytics plugin
├── eval/                # Gemini Enterprise custom evaluation metrics & benchmarks
├── web/                 # FastAPI REST API, Google Chat webhook, and interactive Web Dashboard
├── terraform/           # GCP Infrastructure as Code (Cloud Run, WORM Bucket, BigQuery)
├── tests/               # Comprehensive unit and end-to-end integration test suites
└── docs/                # Level 300 architecture, customer handover guide, and Google Chat setup
```

---

## 🔒 Security, Compliance & Governance

- **SOC 2 Type II:** All state transitions and human approvals produce cryptographically hashed immutable records in Cloud Storage Object Retention.
- **Zero-Trust Access Control:** Agent Gateway validates Google Workspace OIDC tokens and verifies domain roles before allowing loop creation or gate resolution.
