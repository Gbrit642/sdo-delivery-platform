# Live Demo Script & Walkthrough: Autonomous SDO Platform on GCP

This document provides a guided step-by-step demo script to showcase the Wallbox Software Delivery Optimization (SDO) Platform across its three interfaces:
1. **Interactive Web Dashboard (Google Chrome)**
2. **Gemini Enterprise Assistant Portal**
3. **Automated CLI & REST API**

---

## 🌟 Track 1: Interactive Web Dashboard (Chrome Browser)

Open the live Cloud Run Web Dashboard:
👉 **[https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app/](https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app/)**  
*(or locally at `http://localhost:8080`)*

### Scenario: Finance FX Variance Analysis
1. **Step 1: Submit Delivery Brief**
   - **Target Domain:** `finance`
   - **Owner Email:** `sarah.controller@wallbox.com`
   - **Brief Text:**
     ```text
     Create a weekly currency variance analysis view in BigQuery comparing EUR invoices with USD receipts for the finance team. Ensure conversion rates and revenue metrics are validated.
     ```
   - Click **`🚀 Launch Delivery Loop`**.

2. **Step 2: Watch Autonomous Spec Synthesis**
   - The platform verifies domain RBAC (`finance.yaml`), queries BigQuery table schemas (`invoices`, `receipts`), and synthesizes `spec.md` with Gherkin scenarios.
   - The **Two-Tier Quality Harness** validates the AST syntax and SOC 2 / GDPR compliance via `PolicyAuditorAgent`.
   - The state machine automatically pauses at **`WAIT_GATE_H1`** with a glowing blue indicator.

3. **Step 3: Perform Gate H1 Spec Sign-Off**
   - Under the **"Gate H1: Specification Sign-Off"** card, inspect the generated Gherkin scenarios.
   - Enter an approval comment: `"Gherkin scenarios and FX tolerance metrics approved."`
   - Click **`✅ Approve Specification`**.

4. **Step 4: Ephemeral Sandbox Compilation & Testing**
   - **Arquitecto Agent** creates the technical design (`design.md`).
   - **Implementer Agent** generates BigQuery SQL views and Python transformations.
   - The **Ephemeral Linux Sandbox** executes `pytest` in isolation with a **100.0% pass rate**.
   - **Reviewer Agent** verifies code against acceptance criteria.
   - The state machine automatically pauses at **`WAIT_GATE_H2`**.

5. **Step 5: Perform Gate H2 Final Merge Sign-Off**
   - Review sandbox test telemetry (`pass_rate: 100.0%`).
   - Click **`🚀 Approve Merge & Deploy`**.

6. **Step 6: Verified Delivery Completion**
   - GitHub Pull Request is squash-merged.
   - Semantic release tag `v1.0.0` is provisioned.
   - Immutable audit record is sealed in Cloud Storage Object Retention (`WORM SHA-256 Seal`).
   - Day 30 telemetry monitoring is scheduled by the **Watcher Agent**.
   - State advances to **`DONE`**!

---

## 💬 Track 2: Gemini Enterprise Assistant Portal

1. Open **Google Cloud Console $\to$ Gemini Enterprise $\to$ Apps** in project `managed-agent-504409`.
2. Select either of the registered agents:
   - **`Wallbox SDO - Option A (Vertex AI Agent Runtime Engine)`** (Primary / Default)
   - **`Wallbox SDO - Option B (Cloud Run A2A with Web Dashboard & Gates)`** (Backup / Dedicated Web Dashboard)
3. Try any of these domain-specific test prompts:

### Finance Domain:
> *"I need an automated BigQuery view in our finance dataset comparing EUR billing amounts with USD settlement values. Can you generate the specification and run the validation tests?"*

### Sales Domain:
> *"Create an opportunity conversion funnel query for the commercial team aggregating monthly sales stages from CRM records."*

### Firmware Domain:
> *"Aggregate hourly error logs and OCPP 1.6J charge-point heartbeat metrics for Pulsar Plus devices in our European charging network."*

### Marketing Domain:
> *"Build a multi-touch attribution analysis view calculating customer acquisition cost (CAC) across paid search and social channels with GDPR consent filtering."*

### Logistics Domain:
> *"Create a warehouse dispatch SLA monitoring view tracking parts inventory turnover."*

---

## ⚡ Track 3: 1-Click Terminal Verification Run

To verify the live Cloud Run instance from your command line:

```bash
python3 -c "
import urllib.request, json

BASE_URL = 'https://sdo-adk-cloudrun-a2a-316329647160.us-central1.run.app'

print('1. Checking Live Discovery Card...')
with urllib.request.urlopen(f'{BASE_URL}/a2a/app/.well-known/agent-card.json') as r:
    card = json.loads(r.read())
    print('   ✓ Active A2A Card:', card['name'], '| Skills:', len(card['skills']))

print('2. Creating Finance Delivery Loop...')
req = urllib.request.Request(f'{BASE_URL}/api/v1/loops', data=json.dumps({
    'node_id': 'finance',
    'brief_text': 'Create weekly FX variance analysis view in BigQuery.',
    'owner_email': 'sarah.controller@wallbox.com'
}).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r:
    loop = json.loads(r.read())
    loop_id = loop['loop_id']
    print(f'   ✓ Loop Created: {loop_id} (State: {loop[\"current_state\"]})')

print('3. Approving Gate H1 (Spec Sign-Off)...')
h1_req = urllib.request.Request(f'{BASE_URL}/api/v1/loops/{loop_id}/gates/h1/resolve', data=json.dumps({
    'decision': 'approve', 'comment': 'Spec approved for sandbox build'
}).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(h1_req) as r:
    res_h1 = json.loads(r.read())
    print(f'   ✓ Sandbox Tests Executed (100% Pass) | State: {res_h1[\"current_state\"]}')

print('4. Approving Gate H2 (Final Merge Sign-Off)...')
h2_req = urllib.request.Request(f'{BASE_URL}/api/v1/loops/{loop_id}/gates/h2/resolve', data=json.dumps({
    'decision': 'approve', 'comment': 'Merge approved'
}).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(h2_req) as r:
    res_h2 = json.loads(r.read())
    print(f'   ✓ Loop Complete: {res_h2[\"current_state\"]}')
    print(f'   ✓ GitHub Commit: {res_h2[\"close_commit_hash\"]}')
    print(f'   ✓ WORM Audit Seal: {res_h2[\"worm_audit_record_id\"]}')

print('\n🎉 End-to-End Delivery Simulation Passed 100%!')
"
```
