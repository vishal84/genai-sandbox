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
from app.rag.corpus_manager import RagChunk, VertexRagManager, extract_relevant_excerpt
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
    folder_uri: str | None = Field(default=None, description="Target GCS folder path for bulk ingestion")
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
    q_lower = state.query.lower().strip()
    if (
        state.gcs_uris
        or state.folder_uri
        or state.intent == "ingest"
        or q_lower.startswith("ingest:")
        or q_lower.startswith("ingest_folder:")
        or q_lower.startswith("ingest_all:")
    ):
        return "ingest"
    return "query"


@node(name="ingest_node")
def ingest_node(state: DocWorkflowState) -> dict[str, Any]:
    """Ingests and pre-processes PDF documents from GCS into Vertex AI RAG store."""
    folder_uri = state.folder_uri
    uris = list(state.gcs_uris)

    # Check query string for inline commands if parameters not provided
    if not folder_uri and not uris and state.query:
        q_lower = state.query.lower().strip()
        if q_lower.startswith("ingest_folder:"):
            folder_uri = state.query.split("ingest_folder:", 1)[1].strip()
        elif q_lower.startswith("ingest_all:"):
            folder_uri = state.query.split("ingest_all:", 1)[1].strip()
        elif q_lower.startswith("ingest:"):
            extracted = state.query.split("ingest:", 1)[1].strip()
            # If it looks like a folder path (contains / and no file extension)
            if "/" in extracted and not extracted.lower().endswith((".pdf", ".txt", ".docx", ".html", ".md")):
                folder_uri = extracted
            else:
                uris = [u.strip() for u in extracted.split(",") if u.strip().startswith("gs://")]

    # Folder ingestion branch
    if folder_uri:
        result = rag_manager.import_gcs_folder(folder_uri=folder_uri)
        state.ingest_result = result
        if result.get("status") == "error":
            result.setdefault("imported_files_count", 0)
            err_msg = result.get("message") or result.get("error") or "Unknown error"
            state.answer = f"Ingestion failed: {err_msg}"
        else:
            state.answer = result.get(
                "message",
                f"Successfully submitted folder '{folder_uri}' for ingestion into Vertex AI RAG.",
            )
        return result

    # Single/multiple file URIs branch
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


def is_no_data_response(text: str) -> bool:
    """Returns True if the response indicates no relevant data was found in documents."""
    patterns = [
        r"\b(?:do|does|did)\s+not\s+contain\b",
        r"\bnot\s+contain\s+(?:any|this|sufficient)\b",
        r"\b(?:there\s+is\s+)?no\s+mention\b",
        r"\bnot\s+mentioned\s+in\b",
        r"\b(?:could|can)\s*not\s+find\b",
        r"\b(?:is|are|was|were)\s+not\s+found\b",
        r"\bcannot\s+be\s+found\b",
        r"\bno\s+(?:relevant\s+)?(?:information|info|data)\s+(?:found|available|provided|regarding|about|on|in|to)\b",
        r"\b(?:not\s+provided|not\s+present|not\s+included|not\s+discussed|not\s+available)\s+in\s+the\b",
        r"\b(?:provided|ingested|retrieved|context)\s+documents?\s+do(?:es)?\s+not\b",
        r"\bdocuments?\s+do(?:es)?\s+not\s+(?:contain|mention|have|provide)\b",
        r"\bno\s+data\s+(?:that\s+)?matches\b",
        r"\bunable\s+to\s+(?:find|locate|determine)\b",
        r"\b(?:insufficient|not\s+enough)\s+information\b",
        r"\bnone\s+of\s+the\s+(?:provided|ingested|retrieved)?\s*documents\b",
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)


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
        # Vertex distance: smaller is closer; score <= 0.85 is considered relevant
        score = chunk.get("score", 0.0)
        if score <= 0.85:
            filtered.append(chunk)

    state.filtered_chunks = filtered
    state.is_grounded = len(filtered) > 0
    return filtered


@node(name="synthesize_node")
def synthesize_node(state: DocWorkflowState) -> str:
    """Synthesizes an accurate, grounded analyst answer with evidence excerpts and page citations."""
    if not state.filtered_chunks:
        answer = "I could not find any relevant information in the ingested documents to answer your question."
        state.answer = answer
        state.citations = []
        state.is_grounded = False
        return answer

    # Build context string with numbered references and extracted excerpts
    context_sections = []
    citation_map: dict[int, dict[str, Any]] = {}

    for idx, chunk in enumerate(state.filtered_chunks, start=1):
        doc_name = chunk.get("document_name", f"Doc-{idx}")
        source_uri = chunk.get("source_uri", "")
        page_num = chunk.get("page_number")
        page_range = chunk.get("page_range")
        text = chunk.get("text", "")

        signed_url = generate_gcs_signed_url(source_uri) if source_uri else None
        page_display = page_range or (str(page_num) if page_num else None)

        snippet = extract_relevant_excerpt(state.query, text, max_chars=350)

        citation_info = {
            "citation_index": idx,
            "document_name": doc_name,
            "source_uri": source_uri,
            "page_number": page_num,
            "page_range": page_display,
            "snippet": snippet,
            "signed_url": signed_url,
        }
        citation_map[idx] = citation_info

        page_str = f" (Page {page_display})" if page_display else ""
        context_sections.append(
            f"[{idx}] Source Document: {doc_name}{page_str}\n"
            f"Relevant Evidence Excerpt: \"{snippet}\"\n"
            f"Full Chunk Text:\n{text}"
        )

    context_str = "\n\n".join(context_sections)

    synthesis_prompt = f"""You are an expert Document Intelligence Analyst. Answer the user's research query accurately and comprehensively using ONLY the provided document excerpts.

Instructions:
1. Grounding & Accuracy: Rely STRICTLY on the clear factual statements present in the provided Context Sources. Under NO circumstances should you fabricate, speculate, extrapolate, or use outside knowledge.
2. Negative / No Match Case: If the provided context does NOT contain information to answer the user query, or if the documents are irrelevant to the query, you MUST state clearly that the ingested documents do not contain this information. In this case, do NOT make up an answer, do NOT provide speculative information, and do NOT cite or reference any source numbers or bracketed citations (e.g., do NOT output [1], [2]).
3. Factual Statements & Citations: When the context DOES answer the query, provide a direct, well-structured, and factual explanation. Every factual statement MUST cite the source using inline brackets corresponding to the source number, e.g. [1] or [1][2].
4. Page References: When referencing evidence from a specific page, cite the page number as indicated in the source headers (e.g., "[1] (Page 7)").
5. Evidence Excerpts: When answering with evidence, incorporate or quote concise relevant excerpts from the document to support your answer.

Context Sources:
{context_str}

User Query: {state.query}

Grounded Analyst Answer:"""

    try:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        client = GenAiClient(vertexai=True, project=project, location=location)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=synthesis_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1500,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        answer = (response.text or "").strip()
    except Exception as e:
        logger.warning("Synthesis LLM call failed (%s); providing extractive summary fallback.", e)
        top_chunk = state.filtered_chunks[0]
        top_text = top_chunk.get("text", "")
        query_words = [
            w.lower()
            for w in re.findall(r"\b\w{3,}\b", state.query)
            if w.lower() not in {"what", "when", "where", "which", "who", "whom", "whose", "why", "how", "the", "and", "for", "with", "from"}
        ]
        has_match = any(w in top_text.lower() for w in query_words)
        if has_match:
            top_doc = top_chunk.get("document_name", "document")
            top_page = top_chunk.get("page_range") or top_chunk.get("page_number")
            page_ref = f" (Page {top_page})" if top_page else ""
            top_excerpt = extract_relevant_excerpt(state.query, top_text, max_chars=300)
            answer = f"Based on {top_doc}{page_ref} [1]: \"{top_excerpt}\""
        else:
            answer = "I could not find any relevant information in the ingested documents to answer your question."

    is_no_data = is_no_data_response(answer)

    # Detect which citations were actually referenced in the answer
    found_indices = set(re.findall(r"\[(\d+)\]", answer))
    used_citations = []
    for idx_str in sorted(found_indices, key=int):
        idx = int(idx_str)
        if idx in citation_map:
            used_citations.append(citation_map[idx])

    # If the answer indicates no data was found or no citations were emitted/grounded
    if is_no_data or not used_citations:
        clean_answer = re.sub(r"\s*\[\d+\]", "", answer).strip()
        if not is_no_data and not used_citations:
            clean_answer = (
                f"Based on the provided documents, there is no mention or information regarding "
                f"\"{state.query}\". The ingested documents do not contain this information."
            )
        state.answer = clean_answer
        state.citations = []
        state.is_grounded = False
        return clean_answer

    state.answer = answer
    state.citations = used_citations
    state.is_grounded = True
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


def ingest_bucket_folder_tool(folder_uri: str) -> str:
    """Ingests all PDF documents from a Google Cloud Storage bucket folder path into the Vertex AI RAG store.

    Args:
        folder_uri: GCS folder path (e.g. 'gs://my-bucket/contracts/'). A folder path must be provided.

    Returns:
        A status message detailing the bulk folder ingestion result.
    """
    state = DocWorkflowState(intent="ingest", folder_uri=folder_uri)
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
        page_val = c.get("page_range") or c.get("page_number")
        page_str = f" (Page {page_val})" if page_val else ""
        link_str = f" ({c['signed_url']})" if c.get("signed_url") else ""
        snippet_str = f"\n   Evidence: \"{c['snippet']}\"" if c.get("snippet") else ""
        citation_summary.append(f"[{c['citation_index']}] {c['document_name']}{page_str}{link_str}{snippet_str}")

    citations_text = "\n".join(citation_summary)
    if citations_text and state.is_grounded and state.citations:
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
2. Never extrapolate, fabricate, or make ungrounded claims. Rely strictly on facts directly stated in the RAG store.
3. Always include bracketed citations [1], [2] referencing the source document and page number when citing facts. If no data or evidence matching the query is found in the documents, clearly state that the documents do not contain the information, and do NOT cite any sources or fabricate facts.
4. If documents need to be indexed, use ingest_documents_tool for specific files, or ingest_bucket_folder_tool to ingest all documents in a bucket folder path (a folder path must be provided).
""",
    tools=[
        ingest_documents_tool,
        ingest_bucket_folder_tool,
        query_doc_intelligence_tool,
        list_indexed_documents_tool,
    ],
)

app = App(
    root_agent=root_agent,
    name="doc_intelligence_agent",
)

