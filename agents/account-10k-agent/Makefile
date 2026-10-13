# ==============================================================================
# Makefile: Account 10-K Intelligence Agent Infrastructure & Lifecycle
# ==============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

ifneq (,$(wildcard ./.env))
    include .env
    export
endif

export GOOGLE_GENAI_USE_VERTEXAI ?= true

PROJECT_ID ?= $(if $(GOOGLE_CLOUD_PROJECT),$(GOOGLE_CLOUD_PROJECT),mongo-experiments)
LOCATION ?= $(if $(GOOGLE_CLOUD_LOCATION),$(GOOGLE_CLOUD_LOCATION),global)
STORAGE_REGION ?= us-central1
RAG_LOCATION ?= $(if $(RAG_LOCATION),$(RAG_LOCATION),us-east5)
RAG_DISPLAY_NAME ?= $(if $(RAG_CORPUS_DISPLAY_NAME),$(RAG_CORPUS_DISPLAY_NAME),account-10k-corpus)
TF_DIR := terraform

.PHONY: help
help: ## Show this help message
	@echo "Account 10-K Intelligence Agent - Infrastructure & App Lifecycle"
	@echo "================================================================"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: up provision
up: provision ## Alias for provision
provision: ## Provision GCS bucket and Vertex AI RAG store via Terraform and update .env
	@echo "🚀 [1/4] Initializing Terraform..."
	@terraform -chdir=$(TF_DIR) init -upgrade
	@echo "🚀 [2/4] Applying Terraform infrastructure (GCS Bucket + Vertex AI RAG Config)..."
	@terraform -chdir=$(TF_DIR) apply -auto-approve \
		-var="project_id=$(PROJECT_ID)" \
		-var="region=$(STORAGE_REGION)" \
		-var="rag_location=$(RAG_LOCATION)" \
		-var="rag_corpus_display_name=$(RAG_DISPLAY_NAME)"
	@$(eval BUCKET_NAME := $(shell terraform -chdir=$(TF_DIR) output -raw bucket_name))
	@echo "📦 Created GCS Bucket: $(BUCKET_NAME)"
	@echo "🚀 [3/4] Creating / Linking Vertex AI RAG Corpus ($(RAG_LOCATION))..."
	@CORPUS_JSON=$$(uv run python scripts/manage_rag_corpus.py create \
		--project=$(PROJECT_ID) \
		--location=$(RAG_LOCATION) \
		--display-name=$(RAG_DISPLAY_NAME)) ; \
	CORPUS_ID=$$(echo "$$CORPUS_JSON" | grep -o '"corpus_id": "[^"]*' | cut -d'"' -f4) ; \
	echo "🧠 Vertex AI RAG Corpus ID: $$CORPUS_ID" ; \
	echo "🚀 [4/4] Synchronizing resource IDs to local .env file..." ; \
	uv run python scripts/manage_rag_corpus.py sync-env \
		--env-path=.env \
		--project=$(PROJECT_ID) \
		--location=$(LOCATION) \
		--rag-location=$(RAG_LOCATION) \
		--bucket=$(BUCKET_NAME) \
		--corpus-id=$$CORPUS_ID \
		--display-name=$(RAG_DISPLAY_NAME)
	@echo "✅ Infrastructure provisioned and .env updated!"

.PHONY: down destroy
down: destroy ## Alias for destroy
destroy: ## Destroy all Terraform infrastructure and delete the Vertex AI RAG Corpus
	@uv run python scripts/manage_rag_corpus.py delete \
		--project=$(PROJECT_ID) \
		--location=$(RAG_LOCATION) \
		--display-name=$(RAG_DISPLAY_NAME) || true
	@terraform -chdir=$(TF_DIR) destroy -auto-approve \
		-var="project_id=$(PROJECT_ID)" \
		-var="region=$(STORAGE_REGION)" \
		-var="rag_location=$(RAG_LOCATION)" \
		-var="rag_corpus_display_name=$(RAG_DISPLAY_NAME)"
	@uv run python scripts/manage_rag_corpus.py sync-env \
		--env-path=.env \
		--corpus-id=""
	@echo "✅ All resources cleanly destroyed."

.PHONY: status
status: ## Display status of Terraform resources, GCS bucket, and Vertex AI RAG Corpus
	@echo "=== Local .env Configuration ==="
	@cat .env
	@echo ""
	@echo "=== Terraform Outputs ==="
	@terraform -chdir=$(TF_DIR) output || echo "No active Terraform state found."
	@echo ""
	@echo "=== Vertex AI RAG Corpus Status ==="
	@uv run python scripts/manage_rag_corpus.py status \
		--project=$(PROJECT_ID) \
		--location=$(RAG_LOCATION) \
		--display-name=$(RAG_DISPLAY_NAME)

.PHONY: build-frontend
build-frontend: ## Build the React + Vite + Tailwind frontend into app/static
	@echo "📦 Building React + Tailwind frontend..."
	@cd frontend && npm install && npm run build

.PHONY: run-local
run-local: ## Run the agent and frontend locally via FastAPI and uvicorn
	@echo "🌐 Starting account-10k-agent at http://localhost:8080..."
	@uv run python -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8080 --reload

.PHONY: deploy-cloud-run
deploy-cloud-run: ## Build and deploy the agent container to Cloud Run
	@echo "☁️ Deploying account-10k-agent to Cloud Run in $(STORAGE_REGION)..."
	@gcloud run deploy account-10k-agent \
		--source . \
		--region $(STORAGE_REGION) \
		--project $(PROJECT_ID) \
		--allow-unauthenticated \
		--port 8080 \
		--set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$(PROJECT_ID),GOOGLE_CLOUD_LOCATION=$(LOCATION),RAG_LOCATION=$(RAG_LOCATION),GCS_DOCUMENTS_BUCKET=$(GCS_DOCUMENTS_BUCKET),RAG_CORPUS_ID=$(RAG_CORPUS_ID),RAG_CORPUS_DISPLAY_NAME=$(RAG_DISPLAY_NAME)

.PHONY: test
test: ## Run unit tests
	@uv run pytest tests/unit -v

