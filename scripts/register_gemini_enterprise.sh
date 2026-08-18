#!/usr/bin/env bash
# ==============================================================================
# Wallbox SDO Platform — Gemini Enterprise Publishing & Registration Script
# Target GCP Project: managed-agent-504409
# ==============================================================================

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-managed-agent-504409}"
REGION="${REGION:-europe-west1}"
SERVICE_NAME="sdo-adk-engine"
AGENT_NAME="Wallbox SDO Delivery Platform"
DESCRIPTION="Automated Software & Data Delivery Multi-Agent System for Finance, Sales, Firmware, Marketing, and Logistics."

echo "=============================================================================="
echo "Publishing SDO Platform to Gemini Enterprise (Project: ${PROJECT_ID})"
echo "=============================================================================="

# 1. Check if Cloud Run URL is already provisioned
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)' 2>/dev/null || echo "")

if [ -z "${SERVICE_URL}" ]; then
  echo "ℹ️  Cloud Run service '${SERVICE_NAME}' is not yet deployed on GCP."
  echo "    Using default endpoint: https://${SERVICE_NAME}-${PROJECT_ID}.${REGION}.run.app"
  SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_ID}.${REGION}.run.app"
fi

AGENT_CARD_URL="${SERVICE_URL}/a2a/app/.well-known/agent-card.json"
echo "▸ Agent Card URL: ${AGENT_CARD_URL}"

# 2. Grant Discovery Engine Service Account permissions
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
DISCOVERY_SA="service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

echo "▸ Granting Cloud Run invoker role to Discovery Engine Service Account: ${DISCOVERY_SA}"
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${DISCOVERY_SA}" \
  --role="roles/run.servicesInvoker" \
  --quiet 2>/dev/null || echo "ℹ️  (IAM policy binding can be applied after Cloud Run service is active)"

# 3. Publish to Gemini Enterprise via agents-cli
echo "▸ Registering Agent Card with Gemini Enterprise..."
agents-cli publish gemini-enterprise \
  --project-id "${PROJECT_ID}" \
  --agent-card-url "${AGENT_CARD_URL}" \
  --display-name "${AGENT_NAME}" \
  --description "${DESCRIPTION}" \
  --tool-description "Generates Gherkin specifications, executes BigQuery data pipelines, compiles code, runs sandbox tests, and manages human sign-off gates." \
  --registration-type a2a \
  --deployment-target cloud_run

echo "=============================================================================="
echo "✅ Gemini Enterprise Registration Complete!"
echo "=============================================================================="
