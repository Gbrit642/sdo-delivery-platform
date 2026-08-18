# ==============================================================================
# Enterprise Identity-Aware Proxy (IAP) & HTTPS Load Balancer Architecture
# Complies with org policy constraint: constraints/run.managed.requireInvokerIam
# ==============================================================================

# 1. Serverless Network Endpoint Group (NEG) pointing to Cloud Run
resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "sdo-serverless-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  project               = var.project_id

  cloud_run {
    service = google_cloud_run_v2_service.sdo_engine.name
  }
}

# 2. Backend Service with Identity-Aware Proxy (IAP) Enabled
resource "google_compute_backend_service" "iap_backend" {
  name                  = "sdo-iap-backend-service"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }

  iap {
    enabled = true
    # Configure oauth2_client_id and oauth2_client_secret for custom domain OAuth brand
    # oauth2_client_id     = var.iap_oauth_client_id
    # oauth2_client_secret = var.iap_oauth_client_secret
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# 3. URL Map Routing
resource "google_compute_url_map" "sdo_url_map" {
  name            = "sdo-iap-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.iap_backend.id
}

# 4. Global Reserved Static IP Address
resource "google_compute_global_address" "sdo_ip" {
  name    = "sdo-iap-static-ip"
  project = var.project_id
}

# 5. IAM Policy: Allow IAP Service Account to invoke Cloud Run backend
# Required by constraints/run.managed.requireInvokerIam
resource "google_cloud_run_service_iam_member" "iap_invoker" {
  location = var.region
  project  = var.project_id
  service  = google_cloud_run_v2_service.sdo_engine.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${var.project_number != "" ? var.project_number : "316329647160"}@gcp-sa-iap.iam.gserviceaccount.com"
}
