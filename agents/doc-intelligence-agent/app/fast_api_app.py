"""FastAPI backend server for doc-intelligence-agent.

Exposes REST APIs for analyst chat, document ingestion, and status,
attaches Agent2Agent (A2A) protocol endpoints, and serves the React frontend.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncIterator
from pathlib import Path

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging

from app.agent import (
    DocWorkflowState,
    filter_node,
    ingest_node,
    rag_manager,
    retrieve_node,
    synthesize_node,
)
from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import (
    ChatRequest,
    ChatResponse,
    Citation,
    Feedback,
    IngestRequest,
    IngestResponse,
)

load_dotenv()
setup_telemetry()

try:
    _, project_id = google.auth.default()
    logging_client = google_cloud_logging.Client()
    logger = logging_client.logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "*").split(",") if os.getenv("ALLOW_ORIGINS") else ["*"]
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name

    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )

    # Mount compiled React frontend static files as fallback after all API & A2A routes
    if os.path.isdir(STATIC_DIR):
        app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = os.path.join(STATIC_DIR, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=False,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "doc-intelligence-agent"
app.description = "ADK 2.0 Document Intelligence Agent API with Vertex AI RAG and A2A Support"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Executes the query branch of the ADK graph workflow.

    Retrieves top chunks from Vertex AI RAG, filters for relevance, and
    synthesizes a concise grounded answer with citations and signed download links.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Query message cannot be empty.")

    state = DocWorkflowState(intent="query", query=request.message.strip())
    retrieve_node(state)
    filter_node(state)
    synthesize_node(state)

    citations = [
        Citation(
            citation_index=c.get("citation_index", i + 1),
            document_name=c.get("document_name", "Document"),
            source_uri=c.get("source_uri", ""),
            page_number=c.get("page_number"),
            page_range=c.get("page_range"),
            snippet=c.get("snippet", ""),
            signed_url=c.get("signed_url"),
        )
        for i, c in enumerate(state.citations)
    ]

    return ChatResponse(
        answer=state.answer,
        citations=citations,
        session_id=request.session_id,
        raw_chunks=state.filtered_chunks if (state.is_grounded and citations) else [],
    )


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_endpoint(request: IngestRequest) -> IngestResponse:
    """Executes the ingestion branch of the ADK graph workflow.

    Imports GCS PDF documents into the Vertex AI RAG corpus using layout-aware parsing.
    Supports either individual file URIs or bulk folder ingestion.
    """
    folder_uri = request.folder_uri.strip() if request.folder_uri else None
    gcs_uris = [u.strip() for u in request.gcs_uris if u.strip()]

    if not folder_uri and not gcs_uris:
        raise HTTPException(
            status_code=400,
            detail="At least one GCS URI must be provided (or folder_uri for bulk ingestion).",
        )

    if folder_uri:
        if not folder_uri.startswith("gs://"):
            raise HTTPException(status_code=400, detail=f"Invalid folder URI '{folder_uri}': must start with gs://")

        path_part = folder_uri[5:].strip("/")
        parts = path_part.split("/", 1)
        if len(parts) < 2 or not parts[1].strip("/"):
            raise HTTPException(
                status_code=400,
                detail="When ingesting all, a folder path must be provided (e.g., gs://bucket-name/folder/). A bucket root alone is not permitted.",
            )

        if parts[1].strip("/").lower().endswith((".pdf", ".txt", ".docx", ".html", ".md")):
            raise HTTPException(
                status_code=400,
                detail=f"A folder path must be provided when ingesting all, not a single file URI ('{folder_uri}'). For single files, use file ingestion.",
            )

        norm_folder_uri = f"gs://{parts[0]}/{parts[1].strip('/')}/"
        state = DocWorkflowState(intent="ingest", folder_uri=norm_folder_uri)
        result = ingest_node(state)

        return IngestResponse(
            status=result.get("status", "success"),
            imported_files_count=result.get("imported_files_count", 0 if result.get("status") == "error" else 1),
            corpus=result.get("corpus"),
            paths=result.get("paths", [norm_folder_uri]),
            folder_uri=norm_folder_uri,
            message=state.answer,
        )

    for uri in gcs_uris:
        if not uri.startswith("gs://"):
            raise HTTPException(status_code=400, detail=f"Invalid URI '{uri}': must start with gs://")

    state = DocWorkflowState(intent="ingest", gcs_uris=gcs_uris)
    result = ingest_node(state)

    return IngestResponse(
        status=result.get("status", "success"),
        imported_files_count=result.get("imported_files_count", 0 if result.get("status") == "error" else len(gcs_uris)),
        corpus=result.get("corpus"),
        paths=gcs_uris,
        message=state.answer,
    )


@app.get("/api/documents")
async def list_documents_endpoint():
    """Lists all documents currently indexed in the Vertex AI RAG corpus."""
    try:
        files = rag_manager.list_imported_files()
        return {"documents": files}
    except Exception as e:
        return {"documents": [], "warning": str(e)}


@app.get("/api/status")
async def api_status_endpoint():
    """Returns runtime health and configuration metadata."""
    return {
        "status": "online",
        "agent": "doc-intelligence-agent",
        "project": rag_manager.project_id,
        "rag_location": rag_manager.location,
        "corpus_id": rag_manager.corpus_id,
        "bucket": os.getenv("GCS_BUCKET_NAME", ""),
    }


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collects and logs analyst feedback."""
    try:
        if hasattr(logger, "log_struct"):
            logger.log_struct(feedback.model_dump(), severity="INFO")
    except Exception:
        pass
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

