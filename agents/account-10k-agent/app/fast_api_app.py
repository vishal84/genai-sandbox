"""FastAPI server for account-10k-agent with 10-K Upload, Structured Analysis, Grounded Q&A, A2A, and React UI."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging
from pydantic import BaseModel

from app.agent import (
    Account10KWorkflowState,
    analyze_10k_node,
    app as adk_app,
    filter_node,
    ingest_node,
    rag_manager,
    retrieve_node,
    synthesize_node,
)
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.services import get_artifact_service, get_session_service
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import (
    AccountAnalysisReport,
    AnalyzeRequest,
    ChatRequest,
    ChatResponse,
    Citation,
    Feedback,
    IngestRequest,
    IngestResponse,
)
from app.rag.corpus_manager import LOCAL_UPLOAD_DIR, SAMPLE_10K_FILINGS

logger = logging.getLogger(__name__)

A2A_PATH_PREFIX = f"/a2a/{adk_app.root_agent.name}"
STATIC_DIR = Path(__file__).parent / "static"


class SampleLoadRequest(BaseModel):
    """Request body for loading a built-in sample 10-K filing."""

    sample_key: str = "apex_cloud_retail_2025_10k.txt"


def _invoke_node(node_obj: Any, state: Account10KWorkflowState) -> dict[str, Any]:
    """Invokes an ADK 2.0 @node function directly."""
    if hasattr(node_obj, "_func"):
        return node_obj._func(state)
    return node_obj(state)


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan hook for telemetry, A2A registration, and SPA static serving."""
    setup_telemetry()
    runner = Runner(
        app=adk_app,
        artifact_service=get_artifact_service(),
        session_service=get_session_service(),
    )
    await attach_a2a_routes(
        fast_api_app,
        agent=adk_app.root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=A2A_PATH_PREFIX,
    )

    # Seed default sample 10-K on startup if store is empty so UI has an initial account ready
    if not rag_manager.list_account_reports():
        try:
            doc_meta = rag_manager.load_sample_10k("apex_cloud_retail_2025_10k.txt")
            init_state = Account10KWorkflowState(
                action="analyze",
                document_name=doc_meta["display_name"],
                company_name=doc_meta["company_name"],
                ticker=doc_meta["ticker"],
                fiscal_year=doc_meta["fiscal_year"],
            )
            _invoke_node(analyze_10k_node, init_state)
        except Exception as e:
            logger.warning("Could not pre-seed sample 10-K on startup: %s", e)

    # Register SPA static routes after API and A2A routes so they don't shadow /a2a/* or /api/*
    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            fast_api_app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @fast_api_app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            candidate = STATIC_DIR / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            index_file = STATIC_DIR / "index.html"
            if index_file.is_file():
                return FileResponse(str(index_file))
            raise HTTPException(status_code=404, detail="Frontend assets not built yet.")

    yield


app = FastAPI(
    title="account-10k-agent",
    description="SEC 10-K Account Intelligence & Recommendation Agent on Vertex AI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    """Returns Vertex AI RAG corpus and GCS configuration status."""
    return {
        "status": "ok",
        "agent": adk_app.root_agent.name,
        "model": "gemini-3.8-flash",
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        "rag_location": os.environ.get("RAG_LOCATION", "us-central1"),
        "rag_corpus_id": os.environ.get("RAG_CORPUS_ID", ""),
        "gcs_bucket": os.environ.get("GCS_DOCUMENTS_BUCKET", ""),
        "accounts_count": len(rag_manager.list_account_reports()),
        "documents_count": len(rag_manager.list_imported_files()),
    }


@app.get("/api/samples")
def list_samples() -> dict[str, Any]:
    """Lists built-in sample SEC 10-K filings available for one-click analysis."""
    samples = [
        {
            "sample_key": key,
            "filename": val["filename"],
            "company_name": val["company_name"],
            "ticker": val["ticker"],
            "fiscal_year": val["fiscal_year"],
        }
        for key, val in SAMPLE_10K_FILINGS.items()
    ]
    return {"samples": samples}


@app.post("/api/sample")
def load_and_analyze_sample(request: SampleLoadRequest) -> dict[str, Any]:
    """Loads a built-in sample SEC Form 10-K filing and runs full account intelligence analysis."""
    doc_meta = rag_manager.load_sample_10k(request.sample_key)
    state = Account10KWorkflowState(
        action="analyze",
        document_name=doc_meta["display_name"],
        company_name=doc_meta.get("company_name"),
        ticker=doc_meta.get("ticker"),
        fiscal_year=doc_meta.get("fiscal_year"),
    )
    out = _invoke_node(analyze_10k_node, state)
    return {
        "status": "success",
        "document": doc_meta,
        "account_report": out.get("account_report"),
    }


@app.post("/api/upload")
async def upload_10k_file(
    file: UploadFile = File(...),
    company_name: str | None = Form(default=None),
    ticker: str | None = Form(default=None),
    fiscal_year: str | None = Form(default=None),
    custom_focus: str | None = Form(default=None),
    auto_analyze: bool = Form(default=True),
) -> dict[str, Any]:
    """Uploads a 10-K report (.pdf, .html, .txt, .md), indexes into GCS + Vertex AI RAG, and runs account analysis."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    allowed_exts = {".pdf", ".html", ".htm", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext and ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Supported formats: {', '.join(sorted(allowed_exts))}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    doc_meta = rag_manager.upload_and_ingest_file(
        file_bytes=file_bytes,
        filename=file.filename,
        company_name=company_name,
        ticker=ticker,
        fiscal_year=fiscal_year,
    )

    account_report = None
    if auto_analyze:
        state = Account10KWorkflowState(
            action="analyze",
            document_name=doc_meta["display_name"],
            company_name=doc_meta.get("company_name"),
            ticker=doc_meta.get("ticker"),
            fiscal_year=doc_meta.get("fiscal_year"),
            custom_focus=custom_focus,
        )
        out = _invoke_node(analyze_10k_node, state)
        account_report = out.get("account_report")

    return {
        "status": "success",
        "document": doc_meta,
        "account_report": account_report,
    }


@app.post("/api/analyze", response_model=AccountAnalysisReport)
def analyze_10k_endpoint(request: AnalyzeRequest) -> AccountAnalysisReport:
    """Runs or re-runs structured 10-K account analysis on an uploaded/indexed document."""
    state = Account10KWorkflowState(
        action="analyze",
        document_name=request.document_name,
        company_name=request.company_name,
        ticker=request.ticker,
        fiscal_year=request.fiscal_year,
        custom_focus=request.custom_focus,
    )
    out = _invoke_node(analyze_10k_node, state)
    report_data = out.get("account_report")
    if not report_data:
        raise HTTPException(status_code=500, detail="Failed to generate 10-K account analysis report.")
    return AccountAnalysisReport(**report_data)


@app.get("/api/accounts")
def list_accounts() -> dict[str, Any]:
    """Returns all analyzed 10-K AccountAnalysisReport objects."""
    reports = [
        r.model_dump() if hasattr(r, "model_dump") else r
        for r in rag_manager.list_account_reports()
    ]
    return {"accounts": reports}


@app.get("/api/accounts/{account_id}", response_model=AccountAnalysisReport)
def get_account_detail(account_id: str) -> AccountAnalysisReport:
    """Returns a specific AccountAnalysisReport by account_id, ticker, or document_name."""
    report = rag_manager.get_account_report(account_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Account report '{account_id}' not found.")
    if isinstance(report, AccountAnalysisReport):
        return report
    return AccountAnalysisReport(**report)


@app.post("/api/chat", response_model=ChatResponse)
def chat_with_10k(request: ChatRequest) -> ChatResponse:
    """Executes grounded Q&A over the selected account's 10-K filing with page citations."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())
    target_doc = request.document_name
    if not target_doc and request.account_id:
        rep = rag_manager.get_account_report(request.account_id)
        if rep:
            target_doc = getattr(rep, "document_name", None) or (
                rep.get("document_name") if isinstance(rep, dict) else None
            )

    state = Account10KWorkflowState(
        action="query",
        query=request.message,
        document_name=target_doc,
    )

    r_out = _invoke_node(retrieve_node, state)
    state = state.model_copy(update=r_out)
    f_out = _invoke_node(filter_node, state)
    state = state.model_copy(update=f_out)
    s_out = _invoke_node(synthesize_node, state)
    state = state.model_copy(update=s_out)

    citations = [Citation(**c) for c in state.citations]
    return ChatResponse(
        answer=state.answer,
        citations=citations,
        session_id=session_id,
        raw_chunks=state.filtered_chunks,
    )


@app.post("/api/ingest", response_model=IngestResponse)
def ingest_gcs_documents(request: IngestRequest) -> IngestResponse:
    """Ingests 10-K documents from GCS URIs or a GCS folder into the Vertex AI RAG corpus."""
    has_files = bool(request.gcs_uris)
    has_folder = bool(request.folder_uri and request.folder_uri.strip())
    if not has_files and not has_folder:
        raise HTTPException(
            status_code=400,
            detail="Either 'gcs_uris' or 'folder_uri' must be provided.",
        )

    state = Account10KWorkflowState(
        action="ingest",
        gcs_uris=request.gcs_uris,
        folder_uri=request.folder_uri,
    )
    out = _invoke_node(ingest_node, state)
    res = out.get("ingestion_result", {})

    account_report: AccountAnalysisReport | None = None
    if request.auto_analyze and res.get("status") in {"success", "partial_success"}:
        doc_name = None
        if request.gcs_uris:
            doc_name = request.gcs_uris[0].rstrip("/").split("/")[-1]
        analyze_state = Account10KWorkflowState(
            action="analyze",
            document_name=doc_name,
            company_name=request.company_name,
            ticker=request.ticker,
            fiscal_year=request.fiscal_year,
        )
        a_out = _invoke_node(analyze_10k_node, analyze_state)
        if a_out.get("account_report"):
            account_report = AccountAnalysisReport(**a_out["account_report"])

    return IngestResponse(
        status=res.get("status", "unknown"),
        imported_files_count=res.get("imported_files_count", 0),
        corpus=res.get("corpus"),
        paths=res.get("paths", request.gcs_uris),
        folder_uri=res.get("folder_uri", request.folder_uri),
        message=out.get("answer") or res.get("error"),
        account_report=account_report,
    )


@app.get("/api/documents")
def list_documents() -> dict[str, Any]:
    """Lists all 10-K filings indexed in local cache and Vertex AI RAG corpus."""
    files = rag_manager.list_imported_files()
    return {"documents": files}


@app.get("/api/files/{filename}")
def download_local_file(filename: str) -> FileResponse:
    """Serves locally cached 10-K filings so citation links can be opened in local/dev mode."""
    safe_name = Path(filename).name
    target = LOCAL_UPLOAD_DIR / safe_name
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found.")
    media_type = "application/pdf" if safe_name.lower().endswith(".pdf") else "text/plain; charset=utf-8"
    return FileResponse(str(target), media_type=media_type, filename=safe_name)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Logs user feedback on 10-K analysis or Q&A responses."""
    try:
        client = google_cloud_logging.Client()
        cloud_logger = client.logger("account-10k-agent-feedback")
        cloud_logger.log_struct(feedback.model_dump(), severity="INFO")
    except Exception as e:
        logger.info("Feedback logged locally: %s (cloud logging skipped: %s)", feedback.model_dump(), e)
    return {"status": "success"}
