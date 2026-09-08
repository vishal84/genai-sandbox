"""Vertex AI RAG Corpus Manager.

Manages RAG corpus lookup, creation with embedding models, GCS document imports
with layout-aware chunking, and similarity retrieval queries.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RagChunk:
    """Represents a retrieved chunk with metadata and source information."""

    text: str
    score: float
    source_uri: str
    document_name: str
    page_number: int | None = None
    page_range: str | None = None
    signed_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "score": self.score,
            "source_uri": self.source_uri,
            "document_name": self.document_name,
            "page_number": self.page_number,
            "page_range": self.page_range,
            "signed_url": self.signed_url,
        }


STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "in", "on", "of", "and", "or", "for", "to",
    "with", "about", "can", "you", "tell", "me", "how", "why", "which", "do", "does",
    "did", "from", "at", "by", "this", "that", "these", "those", "it", "its", "be",
    "been", "being", "have", "has", "had", "as", "their", "there", "were", "was"
}


def extract_relevant_excerpt(query: str, text: str, max_chars: int = 350) -> str:
    """Extracts a focused textual excerpt from chunk text that is directly relevant to query.

    Splits text into sentences, scores them based on overlap with query terms
    (filtering out stop words), and selects the highest scoring continuous
    passage up to max_chars, cleanly formatted.
    """
    import re

    cleaned = re.sub(r"\r\n|\r", "\n", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    query_words = [
        w.lower()
        for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", query)
        if len(w) >= 3 and w.lower() not in STOP_WORDS
    ]
    if not query_words:
        query_words = [
            w.lower()
            for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", query)
            if w.lower() not in STOP_WORDS
        ]

    # Split into sentences or lines
    raw_sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if s.strip()
    ]
    if not raw_sentences:
        clean_prefix = cleaned[:max_chars]
        if " " in clean_prefix:
            return clean_prefix.rsplit(" ", 1)[0] + "..."
        return clean_prefix + "..."

    # Score each sentence
    scored_sentences = []
    for i, s in enumerate(raw_sentences):
        s_lower = s.lower()
        score = sum(2 if w in s_lower else 0 for w in query_words)
        # Bonus for query bigrams
        for j in range(len(query_words) - 1):
            if f"{query_words[j]} {query_words[j+1]}" in s_lower:
                score += 5
        scored_sentences.append((score, i, s))

    # Sort descending by score, maintaining order for ties
    scored_sentences.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    best_score, best_idx, _ = scored_sentences[0]

    if best_score <= 0:
        best_idx = 0

    # Build window around best sentence up to max_chars
    selected_indices = [best_idx]
    current_len = len(raw_sentences[best_idx])

    if best_idx + 1 < len(raw_sentences) and current_len + len(raw_sentences[best_idx + 1]) + 1 <= max_chars:
        selected_indices.append(best_idx + 1)
        current_len += len(raw_sentences[best_idx + 1]) + 1

    if best_idx - 1 >= 0 and current_len + len(raw_sentences[best_idx - 1]) + 1 <= max_chars:
        selected_indices.insert(0, best_idx - 1)
        current_len += len(raw_sentences[best_idx - 1]) + 1

    excerpt = " ".join(raw_sentences[i] for i in selected_indices)
    if selected_indices[0] > 0:
        excerpt = "..." + excerpt
    if selected_indices[-1] < len(raw_sentences) - 1:
        excerpt = excerpt + "..."

    return excerpt


class VertexRagManager:
    """Interface to Vertex AI RAG Engine."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        corpus_id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = (
            location
            or os.getenv("RAG_LOCATION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or "us-central1"
        )
        self.corpus_id = corpus_id or os.getenv("RAG_CORPUS_ID")
        self.display_name = (
            display_name
            or os.getenv("RAG_CORPUS_DISPLAY_NAME")
            or "doc-intelligence-corpus"
        )
        self._corpus_resource_name: str | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Initializes Vertex AI SDK if not already done."""
        if self._initialized:
            return

        import vertexai

        if self.project_id:
            vertexai.init(project=self.project_id, location=self.location)
            self._initialized = True
        else:
            logger.warning("GOOGLE_CLOUD_PROJECT is not set; running in uninitialized mode.")

    def get_or_create_corpus(
        self,
        display_name: str | None = None,
        embedding_model: str = "publishers/google/models/text-embedding-005",
    ) -> str:
        """Looks up or auto-creates the Vertex AI RAG corpus.

        Returns:
            The fully-qualified corpus resource name.
        """
        if self._corpus_resource_name:
            return self._corpus_resource_name

        # If a specific corpus ID was configured via environment variable, use it directly
        if self.corpus_id:
            if "/" in self.corpus_id:
                self._corpus_resource_name = self.corpus_id
            else:
                self._corpus_resource_name = (
                    f"projects/{self.project_id}/locations/{self.location}/ragCorpora/{self.corpus_id}"
                )
            return self._corpus_resource_name

        self._ensure_initialized()

        from vertexai.preview import rag

        target_name = display_name or self.display_name

        try:
            # Check existing corpora
            existing_corpora = list(rag.list_corpora())
            for corpus in existing_corpora:
                if getattr(corpus, "display_name", "") == target_name:
                    logger.info("Found existing RAG corpus: %s (%s)", corpus.name, target_name)
                    self._corpus_resource_name = corpus.name
                    return corpus.name

            # If not found, create new corpus
            logger.info("Creating new RAG corpus: %s with model %s", target_name, embedding_model)
            embedding_model_config = rag.EmbeddingModelConfig(
                publisher_model=embedding_model
            )
            corpus = rag.create_corpus(
                display_name=target_name,
                embedding_model_config=embedding_model_config,
            )
            self._corpus_resource_name = corpus.name
            logger.info("Successfully created RAG corpus: %s", corpus.name)
            return corpus.name

        except Exception as e:
            logger.error("Error managing Vertex AI RAG corpus: %s", e)
            fallback_name = (
                f"projects/{self.project_id or 'default'}/locations/{self.location}/ragCorpora/{target_name}"
            )
            self._corpus_resource_name = fallback_name
            return fallback_name

    def import_gcs_documents(
        self,
        gcs_uris: list[str],
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        corpus_name: str | None = None,
    ) -> dict[str, Any]:
        """Imports PDF documents from GCS into the Vertex AI RAG corpus.

        Uses layout-aware parsing and chunking to preserve section structure.
        """
        self._ensure_initialized()
        from vertexai.preview import rag

        corpus = corpus_name or self.get_or_create_corpus()

        # Build chunking config
        transformation_config = rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

        logger.info("Importing %d URIs into corpus %s: %s", len(gcs_uris), corpus, gcs_uris)

        try:
            response = rag.import_files(
                corpus_name=corpus,
                paths=gcs_uris,
                transformation_config=transformation_config,
                max_embedding_requests_per_min=1000,
            )
            imported_count = getattr(response, "imported_rag_files_count", len(gcs_uris))
            return {
                "status": "success",
                "corpus": corpus,
                "imported_files_count": imported_count,
                "paths": gcs_uris,
            }
        except Exception as e:
            logger.error("Failed to import files into Vertex AI RAG: %s", e)
            return {
                "status": "error",
                "corpus": corpus,
                "error": str(e),
                "paths": gcs_uris,
            }

    def query_corpus(
        self,
        query_text: str,
        top_k: int = 7,
        distance_threshold: float = 0.8,
        corpus_name: str | None = None,
    ) -> list[RagChunk]:
        """Retrieves top-k relevant chunks from the Vertex AI RAG corpus."""
        self._ensure_initialized()
        from vertexai.preview import rag

        corpus = corpus_name or self.get_or_create_corpus()

        try:
            response = rag.retrieval_query(
                rag_corpora=[corpus],
                text=query_text,
                similarity_top_k=top_k,
                vector_distance_threshold=distance_threshold,
            )

            chunks: list[RagChunk] = []
            contexts = getattr(response, "contexts", None)
            if contexts and hasattr(contexts, "contexts"):
                raw_contexts = contexts.contexts
            else:
                raw_contexts = []

            for ctx in raw_contexts:
                text = getattr(ctx, "text", "")
                score = getattr(ctx, "distance", 0.0)
                source_uri = getattr(ctx, "source_uri", "") or ""
                display_name = getattr(ctx, "source_display_name", "") or ""
                doc_name = (
                    display_name
                    or (source_uri.split("/")[-1] if source_uri else "Document")
                )

                # Extract page number and span from Vertex AI RAG chunk.page_span or fallbacks
                page_number = None
                page_range = None

                chunk_obj = getattr(ctx, "chunk", None)
                if chunk_obj:
                    page_span = getattr(chunk_obj, "page_span", None)
                    if page_span:
                        first = getattr(page_span, "first_page", None)
                        last = getattr(page_span, "last_page", None)
                        if first is not None and first > 0:
                            page_number = int(first)
                            if last is not None and last > first:
                                page_range = f"{first}-{last}"
                            else:
                                page_range = str(first)

                if page_number is None:
                    metadata = getattr(ctx, "metadata", {}) or {}
                    if isinstance(metadata, dict) and "page_number" in metadata:
                        try:
                            page_number = int(metadata["page_number"])
                            page_range = str(page_number)
                        except (ValueError, TypeError):
                            pass

                if page_number is None:
                    import re
                    page_match = re.search(r"(?:\[|\b)(?:page|p\.)\s*(\d+)(?:\]|\b)", text, re.IGNORECASE)
                    if page_match:
                        try:
                            page_number = int(page_match.group(1))
                            page_range = str(page_number)
                        except (ValueError, TypeError):
                            pass

                chunks.append(
                    RagChunk(
                        text=text,
                        score=score,
                        source_uri=source_uri,
                        document_name=doc_name,
                        page_number=page_number,
                        page_range=page_range,
                    )
                )

            return chunks
        except Exception as e:
            logger.error("Error executing RAG retrieval query: %s", e)
            return []

    def list_imported_files(self, corpus_name: str | None = None) -> list[dict[str, Any]]:
        """Lists imported files in the RAG corpus."""
        self._ensure_initialized()
        from vertexai.preview import rag

        corpus = corpus_name or self.get_or_create_corpus()

        try:
            files_iter = rag.list_files(corpus_name=corpus)
            files = []
            for f in files_iter:
                files.append({
                    "name": getattr(f, "name", ""),
                    "display_name": getattr(f, "display_name", ""),
                    "source_uri": getattr(f, "source_uri", ""),
                    "create_time": str(getattr(f, "create_time", "")),
                })
            return files
        except Exception as e:
            logger.warning("Could not list RAG files: %s", e)
            return []

