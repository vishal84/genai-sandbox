# Copyright 2026 Google LLC

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(var.enable_apis)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "documents" {
  name                        = "${var.bucket_name_prefix}-${random_id.bucket_suffix.hex}"
  location                    = var.region
  project                     = var.project_id
  force_destroy               = true
  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = {
    managed_by = "terraform"
    agent      = "account-10k-agent"
  }

  depends_on = [
    google_project_service.enabled_apis["storage.googleapis.com"]
  ]
}

resource "google_vertex_ai_rag_engine_config" "default" {
  provider = google-beta
  project  = var.project_id
  region   = var.rag_location

  rag_managed_db_config {
    basic {}
  }

  depends_on = [
    google_project_service.enabled_apis["aiplatform.googleapis.com"]
  ]
}

