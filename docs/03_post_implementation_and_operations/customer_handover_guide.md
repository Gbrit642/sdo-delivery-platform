# Customer Handover & Operations Guide: Wallbox SDO Platform

## 1. Quickstart & Local Verification

### Prerequisites
- Python >= 3.12
- Google Cloud SDK (`gcloud`) authenticated to project `managed-agent-504409`
- `pytest` for automated test execution

### Step 1: Install Dependencies
```bash
cd sdo-adk-engine
pip install -e ".[dev]"
```

### Step 2: Run Full Automated Test Suite
```bash
pytest tests/ -v
```

### Step 3: Start the Control Plane & Web Dashboard
```bash
python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8080 --reload
```
Open **`http://localhost:8080`** in **Google Chrome** to view the live dashboard and submit test loops.

---

## 2. Deploying Infrastructure to GCP (`managed-agent-504409`)

All cloud infrastructure is fully automated via Terraform in `terraform/`:

```bash
cd sdo-adk-engine/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### Deployed GCP Resources:
1. **Cloud Run Service:** `sdo-adk-engine` (Serverless Control Plane and Web Dashboard).
2. **Cloud Storage WORM Bucket:** `sdo-worm-audit-managed-agent-504409` (Object Retention / Bucket Lock).
3. **BigQuery Datasets:** `sdo_finance_demo` (sample tables) & `sdo_analytics` (Agent Analytics).

---

## 3. Human Approval Gate Operations

### Gate H1: Specification Sign-Off
- **Trigger:** Generated `spec.md` passes Two-Tier Quality Harness.
- **Actions Available:**
  - `[Approve]`: Advances loop to `DESIGN` -> `IMPLEMENT` -> `REVIEW`.
  - `[Request Changes]`: Re-routes back to `SPECIFY` (consumes 1 retry from budget).
  - `[Reject]`: Transitions loop to `CLOSED`.

### Gate H2: Final Merge & Deploy Sign-Off
- **Trigger:** Code compiles, sandbox test suite passes with 100% pass rate, and Reviewer signs off.
- **Actions Available:**
  - `[Approve Merge & Deploy]`: Squash-merges GitHub PR, creates semantic tag (`v1.0.x`), and writes immutable record to WORM audit bucket.
  - `[Request Changes]`: Re-routes to `IMPLEMENT` for code fixes.
  - `[Reject]`: Transitions loop to `CLOSED`.
