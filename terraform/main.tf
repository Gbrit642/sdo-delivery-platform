terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Service Account for SDO ADK Engine Runtime
resource "google_service_account" "sdo_runtime_sa" {
  account_id   = "sdo-adk-engine-runtime"
  display_name = "SDO ADK Engine Runtime Service Account"
}

# 2. Cloud Storage WORM Audit Bucket with Object Retention (Bucket Lock)
resource "google_storage_bucket" "worm_audit_bucket" {
  name                     = var.gcs_worm_bucket_name
  location                 = var.region
  uniform_bucket_level_access = true
  force_destroy            = false

  retention_policy {
    is_locked        = false # Customer locks after initial validation
    retention_period = var.retention_period_seconds
  }

  versioning {
    enabled = true
  }
}

# 3. Cloud KMS KeyRing & CryptoKey for GDPR Envelope Crypto-Shredding
resource "google_kms_key_ring" "sdo_keyring" {
  name     = var.kms_keyring_name
  location = var.region
}

resource "google_kms_crypto_key" "gdpr_crypto_key" {
  name            = var.kms_key_name
  key_ring        = google_kms_key_ring.sdo_keyring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = false
  }
}

# 4. BigQuery Demo & Analytics Datasets
resource "google_bigquery_dataset" "finance_demo" {
  dataset_id                  = var.bq_dataset_id
  friendly_name               = "SDO Finance Demo Dataset"
  description                 = "Wallbox finance tables for currency variance and billing"
  location                    = var.region
  delete_contents_on_destroy  = true
}

resource "google_bigquery_dataset" "agent_analytics" {
  dataset_id                  = var.bq_analytics_dataset_id
  friendly_name               = "SDO BigQuery Agent Analytics"
  description                 = "Live session telemetry streamed via BigQuery Agent Analytics plugin"
  location                    = var.region
  delete_contents_on_destroy  = true
}

# 5. Cloud Run Deployment for SDO Control Plane & Web Dashboard
resource "google_cloud_run_v2_service" "sdo_service" {
  name     = "sdo-adk-engine"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.sdo_runtime_sa.email

    containers {
      image = "gcr.io/${var.project_id}/sdo-adk-engine:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "MODEL_NAME"
        value = "gemini-3.7-flash"
      }
      env {
        name  = "GCS_WORM_BUCKET"
        value = google_storage_bucket.worm_audit_bucket.name
      }
    }
  }
}
