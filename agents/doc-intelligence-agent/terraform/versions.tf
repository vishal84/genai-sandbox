# Copyright 2026 Google LLC
terraform {
  required_version = ">= 1.5.0"

  backend "gcs" {
    bucket = "mongo-experiments-tfstate"
    prefix = "doc-intelligence-agent"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
  }
}

