output "cloud_run_service_uri" {
  description = "De-facto public URL for SDO Control Plane & Web Dashboard"
  value       = google_cloud_run_v2_service.sdo_service.uri
}

output "worm_audit_bucket_name" {
  description = "Name of the GCS WORM Audit Bucket"
  value       = google_storage_bucket.worm_audit_bucket.name
}

output "kms_crypto_key_id" {
  description = "Full resource ID of the GDPR Crypto-Shredding KMS key"
  value       = google_kms_crypto_key.gdpr_crypto_key.id
}

output "bigquery_finance_dataset" {
  description = "BigQuery Finance Demo Dataset ID"
  value       = google_bigquery_dataset.finance_demo.dataset_id
}

output "bigquery_analytics_dataset" {
  description = "BigQuery Agent Analytics Dataset ID"
  value       = google_bigquery_dataset.agent_analytics.dataset_id
}
