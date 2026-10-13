# Copyright 2026 Google LLC

variable "project_id" {
  description = "The Google Cloud Project ID where resources will be provisioned."
  type        = string
  default     = "mongo-experiments"
}

variable "region" {
  description = "Google Cloud region for Cloud Storage and general services."
  type        = string
  default     = "us-central1"
}

variable "rag_location" {
  description = "Google Cloud region strictly used for the Vertex AI RAG Engine and RAG Corpus."
  type        = string
  default     = "us-east5"
}

variable "bucket_name_prefix" {
  description = "Prefix for the GCS document storage bucket."
  type        = string
  default     = "account-10k-agent"
}

variable "rag_corpus_display_name" {
  description = "Display name for the Vertex AI RAG Corpus."
  type        = string
  default     = "account-10k-corpus"
}

variable "rag_embedding_model" {
  description = "Embedding publisher model used for RAG chunking and vector index."
  type        = string
  default     = "publishers/google/models/text-embedding-005"
}

variable "enable_apis" {
  description = "List of Google Cloud APIs required for account-10k-agent."
  type        = list(string)
  default = [
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "iam.googleapis.com",
  ]
}

