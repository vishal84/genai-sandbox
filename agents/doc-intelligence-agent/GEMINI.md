# Coding Agent Guide: Doc Intelligence Agent

This guide documents the full agentic development workflow, operational guidelines, and Vertex AI platform configurations for building, evaluating, and running autonomous agents with Google Cloud Vertex AI (GEAP).

---

## Prerequisites

1. **Google Agents CLI (one-time)**:
   ```bash
   uv tool install google-agents-cli
   ```
2. **Google Cloud Authentication (Application Default Credentials)**:
   When using Vertex AI, authentication is handled via Google Cloud ADC rather than an AI Studio API key:
   ```bash
   gcloud auth application-default login
   gcloud config set project mongo-experiments
   ```

---

## Vertex AI Platform vs. Google AI Studio Authentication

### Root Cause of "No API key was provided" Error
When using Google ADK 2.0 or `google-genai`, the SDK defaults to Google AI Studio mode unless explicitly instructed to target Vertex AI. In AI Studio mode, the SDK looks for `GEMINI_API_KEY` and raises:
> `No API key was provided. Please pass a valid API key. Learn how to create an API key at https://ai.google.dev/gemini-api/docs/api-key.`

### How to Run on Vertex AI Platform (GCP)
To use Google Cloud's Vertex AI platform with IAM and ADC credentials, always ensure the following environment variables are set:

```env
# Forces Google GenAI and ADK to authenticate via Vertex AI (ADC)
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=mongo-experiments
GOOGLE_CLOUD_LOCATION=global
RAG_LOCATION=us-east5
```

In Python code, initialize `GenAiClient` with `vertexai=True`:
```python
from google.genai import Client as GenAiClient

client = GenAiClient(vertexai=True, project=project, location="global")
```

---

## Region Topology: LLM Model, RAG Corpus, and Storage

To prevent 404 model not found errors and regional capacity constraints, the stack separates locations:

| Environment Variable / Config | Value | Purpose |
|---|---|---|
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex AI Gemini models (`gemini-3.8-flash` is routed via the global endpoint; regional endpoints like `us-central1` return 404) |
| `RAG_LOCATION` | `us-east5` (or `us-east4`) | Strictly used for the Vertex AI RAG Engine Managed DB and RAG Corpus to bypass regional vector capacity constraints |
| `STORAGE_REGION` (Makefile/Terraform) | `us-central1` | Regional location for Google Cloud Storage bucket (`gs://...`) and Cloud Run container hosting |

---

## Development Phases

### Phase 1: Understand Requirements
Before writing or modifying any agent code, analyze requirements, inputs, outputs, grounding constraints, and data schemas.

### Phase 2: Build and Implement
- Implement agent logic in `app/`.
- Use ADK 2.0 graph-based workflows (`Workflow`, `Edge`, and `@node` decorators) for multi-step reasoning, retrieval, filtering, and synthesis.
- Use `agents-cli playground` or `make run-local` for interactive testing.

### Phase 3: The Evaluation Loop (Main Iteration Phase)
Start with 1-2 evaluation cases, run `agents-cli eval generate`, then `agents-cli eval grade`. Iterate by making changes and rerunning both commands until satisfied (expect 5-10+ iterations):
- `agents-cli eval dataset synthesize`: Synthesize multi-turn eval scenarios for your agent.
- `agents-cli eval generate`: Run agent on eval dataset and produce execution traces.
- `agents-cli eval grade`: Run LLM-as-judge evaluations on the traces.
- `agents-cli eval compare`: Compare two grade-results files (regression check).
- `agents-cli eval analyze`: Cluster failure modes from grade results.
- `agents-cli eval optimize`: Auto-tune agent prompts using eval data.

### Phase 4: Pre-Deployment Tests
Run automated unit tests:
```bash
uv run pytest tests/unit -v
```
Fix issues until all tests pass.

### Phase 5: Deploy to Dev / Cloud Run
**Requires explicit human approval.**
- Deploy the unified container using `make deploy-cloud-run` or `agents-cli deploy`.
- Validate the Cloud Run service URL and verify `/a2a/doc_intelligence_agent/.well-known/agent-card.json`.

### Phase 6: Production Deployment
Choose between:
- **Option A**: Managed Cloud Run deployment via `make deploy-cloud-run`.
- **Option B**: Full CI/CD pipeline via `agents-cli infra cicd`.

---

## Development & Operational Commands

| Command | Purpose |
|---|---|
| `make up` / `make provision` | Provisions GCS bucket & Vertex AI RAG store via Terraform and syncs `.env` |
| `make status` | Displays status of Terraform outputs, GCS bucket, and Vertex AI RAG Corpus |
| `make run-local` | Starts local FastAPI server and React UI at `http://localhost:8080` |
| `make build-frontend` | Compiles the React + Vite frontend into `app/static` |
| `make deploy-cloud-run` | Builds and deploys the unified agent container to Cloud Run |
| `make down` / `make destroy` | Cleans up and destroys all provisioned GCP infrastructure |
| `agents-cli playground` | Interactive CLI playground for testing the ADK agent |
| `agents-cli eval generate` | Run agent on eval dataset, produce traces |
| `agents-cli eval grade` | Run agent evaluations on traces |
| `agents-cli eval compare` | Compare grade results (regression testing) |
| `agents-cli eval analyze` | Cluster failure modes from grade results |
| `agents-cli eval optimize` | Auto-tune agent prompts using eval data |
| `agents-cli lint` | Check code quality and agent conventions |
| `uv run pytest tests/unit -v` | Run local unit test suite |

---

## Operational Guidelines for Coding Agents

1. **Code Preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values, comments, and formatting.
2. **Model Selection**: NEVER change the model unless explicitly asked.
3. **Model 404 Errors**: Fix `GOOGLE_CLOUD_LOCATION` (e.g., `global` or `us-central1`), not the model name.
4. **Vertex AI Authentication**: Always set `GOOGLE_GENAI_USE_VERTEXAI=true`. Never prompt for or require `GEMINI_API_KEY` when targeting GCP Vertex AI.
5. **ADK Tool Imports**: Import the tool instance, not the module:
   ```python
   from google.adk.tools.load_web_page import load_web_page
   ```
6. **Execution Tooling**: Run Python with `uv`: `uv run python script.py`.
7. **Stop on Repeated Errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
8. **Terraform Resource Conflicts (Error 409)**: Use `terraform import` instead of retrying creation.
9. **Capacity Management**: Use `RAG_LOCATION` for Vertex AI RAG operations to isolate vector search compute from regional capacity shortages.
