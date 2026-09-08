"""Unit tests for VertexRagManager and RagChunk."""

from app.rag.corpus_manager import RagChunk, VertexRagManager


def test_rag_chunk_serialization():
    chunk = RagChunk(
        text="Revenue grew by 14% year-over-year.",
        score=0.12,
        source_uri="gs://financial-docs/q4_report.pdf",
        document_name="q4_report.pdf",
        page_number=12,
        signed_url="https://storage.googleapis.com/signed-url-test",
    )
    serialized = chunk.to_dict()
    assert serialized["text"] == "Revenue grew by 14% year-over-year."
    assert serialized["score"] == 0.12
    assert serialized["document_name"] == "q4_report.pdf"
    assert serialized["page_number"] == 12
    assert serialized["signed_url"] == "https://storage.googleapis.com/signed-url-test"


def test_rag_manager_initialization():
    manager = VertexRagManager(
        project_id="test-project",
        location="us-central1",
        corpus_id="corpus-123",
        display_name="custom-corpus",
    )
    assert manager.project_id == "test-project"
    assert manager.location == "us-central1"
    assert manager.corpus_id == "corpus-123"
    corpus_name = manager.get_or_create_corpus()
    assert "ragCorpora/corpus-123" in corpus_name

