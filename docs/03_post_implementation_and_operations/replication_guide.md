# Replication & Multi-Project Deployment Guide: Autonomous SDO Platform

This guide explains how to replicate and deploy the entire Autonomous SDO platform into **any new Google Cloud Platform (GCP) project** in minutes.

---

## 📋 Prerequisites

1. A new or existing GCP Project with billing enabled (e.g. `your-company-prod`).
2. Google Cloud SDK (`gcloud`) installed and logged in.
3. Terraform >= 1.5.0 installed.
4. Python >= 3.12 installed.

---

## 🚀 4-Step Replication Procedure

### Step 1: Set Target Project & Authenticate
```bash
export NEW_PROJECT_ID="your-target-project-id"
export REGION="us-central1"

gcloud config set project "${NEW_PROJECT_ID}"
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project "${NEW_PROJECT_ID}"
```

### Step 2: Enable Required GCP APIs
```bash
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  discoveryengine.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  cloudbuild.googleapis.com \
  --project="${NEW_PROJECT_ID}"
```

### Step 3: Deploy Infrastructure via Terraform
```bash
cd sdo-adk-engine/terraform
terraform init
terraform apply \
  -var="project_id=${NEW_PROJECT_ID}" \
  -var="region=${REGION}" \
  -auto-approve
```

#### What Terraform Provisions:
- **Cloud Run Service:** `sdo-adk-engine` (FastAPI Control Plane, Web UI, A2A endpoint).
- **Cloud Storage WORM Bucket:** `sdo-worm-audit-${NEW_PROJECT_ID}` (Object Retention in WORM mode).
- **BigQuery Demo Dataset:** `sdo_finance_demo` (with billing/invoicing sample tables).
- **BigQuery Agent Analytics Dataset:** `sdo_analytics` (streaming session telemetry).

### Step 4: Deploy & Register Agents to Gemini Enterprise
```bash
cd ..
# Deploy & register Option A (Agent Runtime) + Option B (Cloud Run A2A)
./scripts/deploy_both_to_gemini_enterprise.sh
```

---

## 🔒 Verification After Replication

1. **Verify Cloud Run Service:**
   ```bash
   gcloud run services list --project="${NEW_PROJECT_ID}" --region="${REGION}"
   ```
2. **Verify WORM Bucket Lock:**
   ```bash
   gcloud storage buckets describe "gs://sdo-worm-audit-${NEW_PROJECT_ID}" --format="json(retention_policy)"
   ```
3. **Verify BigQuery Sample Data:**
   ```bash
   bq query --project_id="${NEW_PROJECT_ID}" --use_legacy_sql=false \
     "SELECT invoice_id, amount_eur, amount_usd, status FROM \`${NEW_PROJECT_ID}.sdo_finance_demo.invoices\` LIMIT 5;"
   ```
4. **Open Web Dashboard:**  
   Navigate to the Cloud Run service URL outputted by Terraform in Google Chrome.
