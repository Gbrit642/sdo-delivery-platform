variable "project_id" {
  description = "Target Google Cloud Project ID"
  type        = string
  default     = "managed-agent-504409"
}

variable "region" {
  description = "GCP primary resource region"
  type        = string
  default     = "europe-west1"
}

variable "gcs_worm_bucket_name" {
  description = "Cloud Storage WORM bucket name with Object Retention"
  type        = string
  default     = "sdo-worm-audit-managed-agent-504409"
}

variable "retention_period_seconds" {
  description = "WORM Object Retention duration in seconds (e.g. 7 years = 220752000s)"
  type        = number
  default     = 220752000
}

variable "kms_keyring_name" {
  description = "Cloud KMS KeyRing name for GDPR Crypto-Shredding"
  type        = string
  default     = "sdo-keyring"
}

variable "kms_key_name" {
  description = "Cloud KMS CryptoKey name for per-subject envelope encryption"
  type        = string
  default     = "sdo-gdpr-shredding-key"
}

variable "bq_dataset_id" {
  description = "BigQuery primary demo dataset"
  type        = string
  default     = "sdo_finance_demo"
}

variable "bq_analytics_dataset_id" {
  description = "BigQuery Agent Analytics dataset"
  type        = string
  default     = "sdo_analytics"
}
