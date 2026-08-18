#!/usr/bin/env bash
# ==============================================================================
# Wallbox SDO Platform — Authenticated Local Proxy for Cloud Run
# Solves org policy: constraints/run.managed.requireInvokerIam
# Automatically injects your active gcloud IAM Identity Token for Chrome Web UI
# ==============================================================================

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-managed-agent-504409}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sdo-adk-cloudrun-a2a}"
PORT="${PORT:-8080}"

echo "=============================================================================="
echo "🔒 Starting Authenticated IAM Proxy for Cloud Run Service: ${SERVICE_NAME}"
echo "   Project: ${PROJECT_ID} | Region: ${REGION} | Local Port: ${PORT}"
echo "=============================================================================="
echo "This allows you to open http://localhost:${PORT} in Chrome while fully complying"
echo "with GCP Org Policy: constraints/run.managed.requireInvokerIam"
echo ""

gcloud run services proxy "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --port="${PORT}"
