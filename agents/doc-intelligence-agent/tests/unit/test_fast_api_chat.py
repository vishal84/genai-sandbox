"""Unit tests for FastAPI chat endpoint."""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.fast_api_app import app
import app.fast_api_app as api_module


def test_chat_endpoint_success(monkeypatch):
    client = TestClient(app)

    def mock_retrieve(state):
        state.retrieved_chunks = [
            {
                "text": "Span-based masking replaces multi-token sequences.",
                "score": 0.1,
                "document_name": "11.pdf",
                "source_uri": "gs://bucket/11.pdf",
                "page_number": 6,
                "page_range": "6-7",
            }
        ]

    def mock_synthesize(state):
        state.answer = "Span-based masking replaces multi-token sequences [1]."
        state.citations = [
            {
                "citation_index": 1,
                "document_name": "11.pdf",
                "source_uri": "gs://bucket/11.pdf",
                "page_number": 6,
                "page_range": "6-7",
                "snippet": "11.2.2 Masking Spans For many NLP applications...",
                "signed_url": "https://storage.googleapis.com/view/11.pdf",
            }
        ]

    monkeypatch.setattr(api_module, "retrieve_node", mock_retrieve)
    monkeypatch.setattr(api_module, "filter_node", lambda s: s.retrieved_chunks)
    monkeypatch.setattr(api_module, "synthesize_node", mock_synthesize)

    response = client.post("/api/chat", json={"message": "What is span masking?"})
    assert response.status_code == 200
    data = response.json()
    assert "[1]" in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["citation_index"] == 1
    assert data["citations"][0]["document_name"] == "11.pdf"
    assert data["citations"][0]["page_number"] == 6
    assert data["citations"][0]["page_range"] == "6-7"
    assert "Masking Spans" in data["citations"][0]["snippet"]


def test_chat_endpoint_empty_message():
    client = TestClient(app)
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400
    assert "Query message cannot be empty" in response.json()["detail"]
