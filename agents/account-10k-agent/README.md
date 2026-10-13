# Account 10-K Intelligence & Recommendation Agent (`account-10k-agent`)

An enterprise **SEC Form 10-K Account Intelligence & Recommendation Agent** built with **Google ADK 2.0**, **Google `agents-cli`**, **Vertex AI Gemini (`gemini-3.8-flash`)**, **Vertex AI RAG Engine**, and a custom **React 18 + TypeScript + Vite + Tailwind CSS** frontend.

---

## Key Capabilities

- **Direct 10-K Report Upload & GCS/RAG Indexing**:
  - Upload SEC Form 10-K filings (`.pdf`, `.html`, `.txt`, `.md`) directly from the browser UI via drag-and-drop, or ingest from Google Cloud Storage (`gs://`) URIs.
  - Automatically extracts page-numbered text and SEC Item sections (`Item 1. Business`, `Item 1A. Risk Factors`, `Item 7. MD&A`, `Item 8. Financial Statements`), uploads to Cloud Storage, and indexes into the **Vertex AI RAG Corpus** (`text-embedding-005`) with a built-in local fallback cache for instant analysis.
- **Dual Financial Health & Strategic Account Recommendations**:
  - **Financial Health & KPIs**: Extracts Revenue, Operating Income, Net Margin, Free Cash Flow, R&D / CapEx investments, YoY growth trends, and computes an overall **Account Health Score (0–100)**.
  - **Strategic Account Recommendations**: Generates prioritized account plays across *Cloud & AI Modernization*, *Data & Analytics*, *Security & Compliance*, *Cost & Operational Efficiency*, and *Revenue & GTM Expansion*, complete with confidence scores, target executive personas (`CIO`, `CFO`, `CISO`, `COO`), rationale, recommended action steps, and ready-to-use **Executive Talking Points**.
  - **SEC Item 1A Risk Factor Mapping**: Maps material 10-K risks to actionable account mitigation opportunities.
- **Grounded 10-K Analyst Chat & Citation Drawer**:
  - Ask follow-up questions scoped to a specific company's 10-K or across all indexed filings.
  - Inline `[1]`, `[2]` citations open a slide-over **Evidence Drawer** with exact 10-K excerpts, page numbers, and V4 GCS signed URL download links.
- **A2A Protocol Ready**:
  - Exposes `/a2a/account_10k_agent/.well-known/agent-card.json` for Agent-to-Agent discovery and orchestration.

---

## Directory Structure

```text
account-10k-agent/
├── app/
│   ├── agent.py               # ADK 2.0 Graph Workflow, @node functions, and root_agent
│   ├── fast_api_app.py        # FastAPI server (/api/upload, /api/analyze, /api/accounts, /api/chat, A2A)
│   ├── rag/
│   │   ├── corpus_manager.py  # Vertex AI RAG client, GCS upload, and 10-K PDF/text parser
│   │   └── signed_urls.py     # GCS V4 signed URL generator
│   └── app_utils/             # Services, A2A card builder, telemetry, Pydantic schemas
├── frontend/                  # Custom React 18 + TypeScript + Vite + Tailwind CSS UI
│   ├── src/
│   │   ├── components/        # AccountSidebar, Upload10KModal, AccountIntelligenceDashboard,
│   │   │                      # AnalystChatDrawer, CitationDrawer
│   │   ├── api/               # Typed API client
│   │   └── types/             # TypeScript interfaces
│   └── package.json
├── tests/unit/                # Pytest unit & FastAPI endpoint tests
├── terraform/                 # GCP bucket & Vertex AI RAG Engine Terraform config
├── scripts/                   # Corpus & .env lifecycle script
├── Dockerfile                 # Multi-stage build (Node Vite + Python ADK runtime)
├── Makefile                   # Build, test, local run, and Cloud Run deploy targets
├── agents-cli-manifest.yaml   # Google agents-cli manifest
└── pyproject.toml             # Python dependencies
```

---

## Quick Start

### 1. Install Python Dependencies

```bash
cd agents/account-10k-agent
uv sync
```

### 2. Build Frontend

```bash
make build-frontend
```

### 3. Run Locally

```bash
make run-local
```

Open `http://localhost:8080` in your browser. Click **Load Sample 10-K** to immediately explore a full 10-K account analysis and recommendation report, or click **Upload 10-K Report** to upload any PDF/HTML/TXT Form 10-K filing.

