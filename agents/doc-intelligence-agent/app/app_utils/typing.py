"""Data schemas and typing definitions for doc-intelligence-agent."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation reference for grounded answer statements."""

    citation_index: int = Field(..., description="1-indexed citation number, e.g. 1 for [1]")
    document_name: str = Field(..., description="Filename or title of the cited document")
    source_uri: str = Field(..., description="Original gs:// URI of the source PDF")
    page_number: int | None = Field(None, description="Page number where content appears if identified")
    snippet: str = Field(..., description="Exact textual excerpt supporting the statement")
    signed_url: str | None = Field(None, description="Direct signed download/view link")


class ChatRequest(BaseModel):
    """Analyst question request."""

    message: str = Field(..., description="Question or research prompt from the analyst")
    session_id: str | None = Field(None, description="Session ID for multi-turn history")


class ChatResponse(BaseModel):
    """Response returned to the analyst with short grounded answer and citations."""

    answer: str = Field(..., description="Short, concise grounded response")
    citations: list[Citation] = Field(default_factory=list, description="Ordered citations")
    session_id: str | None = Field(None, description="Active session ID")
    raw_chunks: list[dict[str, Any]] = Field(default_factory=list, description="Retrieved raw context chunks")


class IngestRequest(BaseModel):
    """Document ingestion request."""

    gcs_uris: list[str] = Field(..., description="List of gs:// paths to PDF documents")
    chunk_size: int = Field(512, description="Target chunk size in tokens/characters")
    chunk_overlap: int = Field(100, description="Chunk overlap")


class IngestResponse(BaseModel):
    """Result of document ingestion."""

    status: str
    imported_files_count: int
    corpus: str | None = None
    paths: list[str] = Field(default_factory=list)
    message: str | None = None


class Feedback(BaseModel):
    """Feedback submitted by users or analysts."""

    score: int = Field(..., ge=1, le=5, description="Satisfaction score 1-5")
    comment: str | None = None
    session_id: str | None = None
    query: str | None = None

