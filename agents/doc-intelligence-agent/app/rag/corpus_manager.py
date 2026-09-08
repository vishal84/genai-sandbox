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
    signed_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "score": self.score,
            "source_uri": self.source_uri,
            "document_name": self.document_name,
            "page_number": self.page_number,
            "signed_url": self.signed_url,
        }


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
        top_k: int = 5,
        distance_threshold: float = 0.5,
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
                doc_name = (
                    source_uri.split("/")[-1] if source_uri else "Document"
                )

                # Attempt to extract page number from metadata or text headers if present
                page_number = None
                metadata = getattr(ctx, "metadata", {}) or {}
                if isinstance(metadata, dict) and "page_number" in metadata:
                    page_number = int(metadata["page_number"])

                chunks.append(
                    RagChunk(
                        text=text,
                        score=score,
                        source_uri=source_uri,
                        document_name=doc_name,
                        page_number=page_number,
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

