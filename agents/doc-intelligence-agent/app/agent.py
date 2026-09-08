"""Doc Intelligence Agent using ADK 2.0 with Graph-based Workflows and Vertex AI RAG."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

# Ensure local .env is loaded and Vertex AI mode is forced for ADC on GCP
load_dotenv()
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import (
    DEFAULT_ROUTE,
    START,
    Edge,
    FunctionNode,
    Workflow,
    node,
)

# Ensure FunctionNode instances are directly callable as functions
if "__call__" not in FunctionNode.__dict__:
    def _function_node_call(self, *args, **kwargs):
        func = getattr(self, "_func", None)
        if callable(func):
            return func(*args, **kwargs)
        raise TypeError(f"FunctionNode '{self.name}' has no underlying callable function.")

    FunctionNode.__call__ = _function_node_call

from google.genai import Client as GenAiClient
from google.genai import types
from pydantic import BaseModel, Field

from app.app_utils.typing import Citation
from app.rag.corpus_manager import RagChunk, VertexRagManager
from app.rag.signed_urls import generate_gcs_signed_url

logger = logging.getLogger(__name__)

# Initialize RAG manager singleton
rag_manager = VertexRagManager()


# ---------------------------------------------------------------------------
# Graph State Schema
# ---------------------------------------------------------------------------


class DocWorkflowState(BaseModel):
    """Workflow state tracking ingestion, retrieval, relevance, and synthesis."""

    intent: str = Field(default="query", description="Route intent: 'ingest' or 'query'")
    query: str = Field(default="", description="Analyst query string")
    gcs_uris: list[str] = Field(default_factory=list, description="Target GCS URIs for ingestion")
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list, description="Retrieved raw chunks")
    filtered_chunks: list[dict[str, Any]] = Field(default_factory=list, description="Filtered relevant chunks")
    is_grounded: bool = Field(default=False, description="Whether chunks sufficiently ground the answer")
    answer: str = Field(default="", description="Concise synthesized answer")
    citations: list[dict[str, Any]] = Field(default_factory=list, description="Structured citation metadata")
    ingest_result: dict[str, Any] = Field(default_factory=dict, description="Ingestion execution result")


# ---------------------------------------------------------------------------
# Graph Workflow Nodes
# ---------------------------------------------------------------------------


@node(name="router_node")
def router_node(state: DocWorkflowState) -> str:
    """Routes execution to either 'ingest' or 'query' based on input state."""
    if state.gcs_uris or state.intent == "ingest" or state.query.lower().startswith("ingest:"):
        return "ingest"
    return "query"


@node(name="ingest_node")
def ingest_node(state: DocWorkflowState) -> dict[str, Any]:
    """Ingests and pre-processes PDF documents from GCS into Vertex AI RAG store."""
    uris = state.gcs_uris
    if not uris and state.query.lower().startswith("ingest:"):
        extracted = state.query.split("ingest:", 1)[1].strip()
        uris = [u.strip() for u in extracted.split(",") if u.strip().startswith("gs://")]

    if not uris:
        result = {
            "status": "error",
            "message": "No valid gs:// PDF URIs provided for ingestion.",
            "imported_files_count": 0,
        }
        state.ingest_result = result
        state.answer = result["message"]
        return result

    result = rag_manager.import_gcs_documents(gcs_uris=uris)
    state.ingest_result = result
    if result.get("status") == "error":
        result.setdefault("imported_files_count", 0)
        state.answer = f"Ingestion failed: {result.get('error', 'Unknown error')}"
    else:
        count = result.get("imported_files_count", len(uris))
        state.answer = f"Successfully submitted {count} document(s) for ingestion into Vertex AI RAG."
    return result


@node(name="retrieve_node")
def retrieve_node(state: DocWorkflowState) -> list[dict[str, Any]]:
    """Retrieves top matching document chunks from the Vertex AI RAG corpus."""
    if not state.query:
        return []

    chunks = rag_manager.query_corpus(query_text=state.query, top_k=5)
    serialized = [chunk.to_dict() for chunk in chunks]
    state.retrieved_chunks = serialized
    return serialized


@node(name="filter_node")
def filter_node(state: DocWorkflowState) -> list[dict[str, Any]]:
    """Filters chunks to ensure relevance and verifies evidence coverage."""
    raw = state.retrieved_chunks
    if not raw:
        state.filtered_chunks = []
        state.is_grounded = False
        return []

    # Keep chunks with acceptable distance/relevance score
    filtered = []
    for chunk in raw:
        # Vertex distance: smaller is closer; score <= 0.8 is considered relevant
        score = chunk.get("score", 0.0)
        if score <= 0.85:
            filtered.append(chunk)

    if not filtered:
        # Fall back to top 2 if non-empty
        filtered = raw[:2]

    state.filtered_chunks = filtered
    state.is_grounded = len(filtered) > 0
    return filtered


@node(name="synthesize_node")
def synthesize_node(state: DocWorkflowState) -> str:
    """Synthesizes a short, concise grounded answer with citations and signed URLs."""
    if not state.filtered_chunks:
        answer = "I could not find any relevant information in the ingested documents to answer your question."
        state.answer = answer
        state.citations = []
        return answer

    # Build context string with numbered references
    context_sections = []
    citation_map: dict[int, dict[str, Any]] = {}

    for idx, chunk in enumerate(state.filtered_chunks, start=1):
        doc_name = chunk.get("document_name", f"Doc-{idx}")
        source_uri = chunk.get("source_uri", "")
        page_num = chunk.get("page_number")
        text = chunk.get("text", "")

        signed_url = generate_gcs_signed_url(source_uri) if source_uri else None

        citation_info = {
            "citation_index": idx,
            "document_name": doc_name,
            "source_uri": source_uri,
            "page_number": page_num,
            "snippet": text[:200] + ("..." if len(text) > 200 else ""),
            "signed_url": signed_url,
        }
        citation_map[idx] = citation_info

        page_str = f" (Page {page_num})" if page_num else ""
        context_sections.append(f"[{idx}] Source: {doc_name}{page_str}\n{text}")

    context_str = "\n\n".join(context_sections)

    synthesis_prompt = f"""You are a precise document analyst. Answer the user query based ONLY on the provided context excerpts.
Rules:
1. Be short, concise, and direct (maximum 3-4 sentences).
2. Every factual claim MUST include inline citations in square brackets matching the context source numbers, e.g., [1] or [1][2].
3. If the context does not contain the answer, state that clearly. Do NOT assume or hallucinate external knowledge.

Context:
{context_str}

User Query: {state.query}

Concise Grounded Answer:"""

    try:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        client = GenAiClient(vertexai=True, project=project, location=location)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=synthesis_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=350,
            ),
        )
        answer = (response.text or "").strip()
    except Exception as e:
        logger.warning("Synthesis LLM call failed (%s); providing extractive summary fallback.", e)
        top_chunk = state.filtered_chunks[0]
        answer = f"Based on {top_chunk.get('document_name', 'document')} [1]: {top_chunk.get('text', '')[:250]}..."

    # Detect which citations were actually referenced in the answer
    used_citations = []
    found_indices = set(re.findall(r"\[(\d+)\]", answer))
    for idx_str in sorted(found_indices, key=int):
        idx = int(idx_str)
        if idx in citation_map:
            used_citations.append(citation_map[idx])

    # If no citation numbers were emitted by LLM, default to the available filtered chunks
    if not used_citations:
        used_citations = list(citation_map.values())

    state.answer = answer
    state.citations = used_citations
    return answer


# ---------------------------------------------------------------------------
# ADK 2.0 Graph Workflow Definition
# ---------------------------------------------------------------------------

doc_workflow = Workflow(
    name="doc_intelligence_workflow",
    edges=[
        Edge(from_node=START, to_node=router_node),
        Edge(from_node=router_node, to_node=ingest_node, route="ingest"),
        Edge(from_node=router_node, to_node=retrieve_node, route="query"),
        Edge(from_node=retrieve_node, to_node=filter_node),
        Edge(from_node=filter_node, to_node=synthesize_node),
    ],
)


# ---------------------------------------------------------------------------
# Operational Agent Tools
# ---------------------------------------------------------------------------


def ingest_documents_tool(gcs_uris: list[str]) -> str:
    """Ingests PDF documents from Google Cloud Storage into Vertex AI RAG store.

    Args:
        gcs_uris: List of Google Cloud Storage URIs (e.g. ['gs://my-bucket/doc.pdf']).

    Returns:
        A status message detailing the ingestion result.
    """
    state = DocWorkflowState(intent="ingest", gcs_uris=gcs_uris)
    ingest_node(state)
    return state.answer


def query_doc_intelligence_tool(analyst_query: str) -> str:
    """Queries the document corpus and returns a short, concise answer with citations and signed source links.

    Args:
        analyst_query: The question or information request from the analyst.

    Returns:
        A concise grounded answer with citations.
    """
    state = DocWorkflowState(intent="query", query=analyst_query)
    retrieve_node(state)
    filter_node(state)
    synthesize_node(state)

    citation_summary = []
    for c in state.citations:
        page_str = f" p.{c['page_number']}" if c.get("page_number") else ""
        link_str = f" ({c['signed_url']})" if c.get("signed_url") else ""
        citation_summary.append(f"[{c['citation_index']}] {c['document_name']}{page_str}{link_str}")

    citations_text = "\n".join(citation_summary)
    if citations_text:
        return f"{state.answer}\n\nSources:\n{citations_text}"
    return state.answer


def list_indexed_documents_tool() -> str:
    """Lists all documents currently indexed in the Vertex AI RAG corpus.

    Returns:
        JSON string listing document names and source URIs.
    """
    files = rag_manager.list_imported_files()
    return json.dumps(files, indent=2)


# ---------------------------------------------------------------------------
# Root Agent & App Definition
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="doc_intelligence_agent",
    model=Gemini(
        model="gemini-3.8-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are an expert Document Intelligence Analyst Agent.
Your role is to help analysts investigate and retrieve facts from PDF documents ingested into the Vertex AI RAG store.
Guidelines:
1. Always keep answers short, crisp, and concise (under 4 sentences).
2. Never extrapolate or state ungrounded claims. Every claim must be grounded in the RAG store.
3. Always include bracketed citations [1], [2] referencing the source document and page number.
4. If documents need to be indexed, use the ingestion tool with the relevant gs:// bucket path.
""",
    tools=[
        ingest_documents_tool,
        query_doc_intelligence_tool,
        list_indexed_documents_tool,
    ],
)

app = App(
    root_agent=root_agent,
    name="doc_intelligence_agent",
)

