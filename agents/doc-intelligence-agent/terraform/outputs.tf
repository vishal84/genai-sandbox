# Copyright 2026 Google LLC

output "project_id" {
  description = "Google Cloud Project ID."
  value       = var.project_id
}

output "region" {
  description = "Google Cloud region."
  value       = var.region
}

output "rag_location" {
  description = "Google Cloud region strictly used for the Vertex AI RAG Engine and RAG Corpus."
  value       = var.rag_location
}

output "bucket_name" {
  description = "Created Google Cloud Storage bucket name for documents."
  value       = google_storage_bucket.documents.name
}

output "bucket_url" {
  description = "GCS bucket URL (gs://...)."
  value       = google_storage_bucket.documents.url
}

output "rag_corpus_display_name" {
  description = "Display name of the Vertex AI RAG Corpus."
  value       = var.rag_corpus_display_name
}

output "rag_engine_config_id" {
  description = "Resource ID of the Vertex AI RAG Engine Managed DB config."
  value       = google_vertex_ai_rag_engine_config.default.id
}

