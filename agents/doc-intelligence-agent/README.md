# Doc Intelligence Agent (ADK 2.0 Graph + Vertex AI RAG + React UI)

An enterprise document intelligence agent built with **Google ADK 2.0**, using graph-based workflows to ingest PDF documents from Cloud Storage into a **Vertex AI RAG Corpus**, and answer analyst questions with concise, strictly grounded summaries and direct GCS signed download citations.

---

## Architecture & Features

- **ADK 2.0 Graph Workflow**: Defined with `@node` decorators and directed `Workflow(edges=[...])` routing between:
  - **Ingestion Pathway**: Imports PDFs directly from GCS into the Vertex AI RAG store with layout-aware chunking and automatic page metadata.
  - **Query Pathway**: Multi-node pipeline (`Retrieve` $\to$ `Filter & Verify Relevance` $\to$ `Concise Grounded Synthesizer`).
- **Grounded Citations with Signed URLs**: Answers are strictly grounded in retrieved chunks with inline citations `[1]`, `[2]`. Each citation provides a short-lived V4 GCS signed URL so analysts can click to view/download the original PDF directly in their browser without GCP console friction.
- **Auto-Provisioned Vertex AI RAG Corpus**: Looks up or creates `doc-intelligence-corpus` with `text-embedding-005`, configurable via `.env`.
- **React + Vite Analyst UI**: Modern dark-mode workspace with real-time chat, clickable citation badges, a slide-over citation drawer with chunk snippets and download buttons, and a document corpus manager.
- **Dual Deployment Ready**:
  - **Cloud Run**: Multi-stage container serving the compiled React frontend, FastAPI backend, and health checks on port 8080.
  - **Agent-to-Agent (A2A)**: Fully compliant A2A protocol endpoint (`/a2a/doc_intelligence_agent/.well-known/agent-card.json`).

---

## Directory Structure

```
doc-intelligence-agent/
├── app/
│   ├── agent.py               # ADK 2.0 Graph Workflow, nodes, and root_agent
│   ├── fast_api_app.py        # FastAPI server, REST routes, A2A routes, static UI
│   ├── rag/
│   │   ├── corpus_manager.py  # Vertex AI RAG engine client and chunk manager
│   │   └── signed_urls.py     # GCS V4 signed URL generator
│   └── app_utils/             # Services, A2A card builder, telemetry, typing
├── frontend/                  # React + Vite analyst interface
│   ├── src/
│   │   ├── components/        # ChatInterface, CitationDrawer, DocumentExplorer
│   │   └── api/               # Typed client calling /api/chat and /api/ingest
│   └── package.json
├── tests/                     # Unit tests for graph nodes and signed URLs
├── Dockerfile                 # Multi-stage build (Node Vite + Python runtime)
├── agents-cli-manifest.yaml   # Google agents-cli configuration
├── pyproject.toml             # Python dependencies (google-adk, aiplatform, storage)
└── GEMINI.md                  # Development guide
```

---

## Getting Started

### 1. Environment Setup

Copy `.env.example` to `.env` and configure your GCP project:

```bash
cp .env.example .env
```

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_DOCUMENTS_BUCKET=your-bucket-name
RAG_CORPUS_DISPLAY_NAME=doc-intelligence-corpus
SIGNED_URL_EXPIRATION_MINUTES=60
```

### 2. Install Python Dependencies

Using `uv`:

```bash
uv sync
```

### 3. Build & Run Frontend (Optional for local dev)

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Run Locally

```bash
uv run python -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8080 --reload
```

- Open `http://localhost:8080` to access the Analyst UI.
- API documentation: `http://localhost:8080/docs`
- A2A Agent Card: `http://localhost:8080/a2a/doc_intelligence_agent/.well-known/agent-card.json`

---

## Deploying to Google Cloud

### Deploying to Cloud Run

Deploy directly from source:

```bash
gcloud run deploy doc-intelligence-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project),GOOGLE_CLOUD_LOCATION=us-central1
```

### Deploying with `agents-cli`

```bash
agents-cli deploy
```

