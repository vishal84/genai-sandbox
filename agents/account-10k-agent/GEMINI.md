# Coding Agent Guide: Account 10-K Intelligence Agent (`account-10k-agent`)

This guide documents the agentic development workflow, operational guidelines, and Vertex AI platform configurations for building, evaluating, and running the SEC 10-K Account Intelligence & Recommendation Agent with Google Cloud Vertex AI and `agents-cli`.

---

## Prerequisites

1. **Google Agents CLI**:
   ```bash
   uv tool install google-agents-cli
   ```
2. **Google Cloud Authentication (Application Default Credentials)**:
   ```bash
   gcloud auth application-default login
   gcloud config set project mongo-experiments
   ```

---

## Vertex AI Platform Configuration

Always ensure the following environment variables are configured in `.env`:

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=mongo-experiments
GOOGLE_CLOUD_LOCATION=global
RAG_LOCATION=us-east5
GCS_DOCUMENTS_BUCKET=your-bucket-name
RAG_CORPUS_DISPLAY_NAME=account-10k-corpus
```

---

## Development Commands

| Command | Purpose |
|---|---|
| `make up` / `make provision` | Provisions GCS bucket & Vertex AI RAG store via Terraform and syncs `.env` |
| `make build-frontend` | Compiles the React + Vite + Tailwind frontend into `app/static` |
| `make run-local` | Starts local FastAPI server and React UI at `http://localhost:8080` |
| `make test` | Runs `uv run pytest tests/unit -v` |
| `agents-cli playground` | Interactive CLI playground for testing the ADK agent |
| `agents-cli eval generate` | Run agent on eval dataset, produce traces |
| `agents-cli eval grade` | Run agent evaluations on traces |
| `agents-cli deploy` | Deploy to Cloud Run |

---

## Operational Guidelines for Coding Agents

1. **Code Preservation**: Only modify code directly targeted by the user's request.
2. **Model Selection**: NEVER change the model (`gemini-3.8-flash`) unless explicitly asked.
3. **Vertex AI Authentication**: Always set `GOOGLE_GENAI_USE_VERTEXAI=true`.
4. **Execution Tooling**: Run Python with `uv`: `uv run python ...` or `uv run pytest ...`.

