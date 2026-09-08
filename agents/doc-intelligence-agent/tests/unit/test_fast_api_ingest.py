"""Unit tests for FastAPI /api/ingest endpoint."""

from fastapi.testclient import TestClient
from app.agent import rag_manager
from app.fast_api_app import app


def test_ingest_endpoint_success(monkeypatch):
    monkeypatch.setattr(
        rag_manager,
        "import_gcs_documents",
        lambda gcs_uris: {
            "status": "success",
            "corpus": "projects/test-proj/locations/us-central1/ragCorpora/123",
            "imported_files_count": len(gcs_uris),
            "paths": gcs_uris,
        },
    )

    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"gcs_uris": ["gs://my-bucket/doc1.pdf", "gs://my-bucket/doc2.pdf"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_files_count"] == 2
    assert data["paths"] == ["gs://my-bucket/doc1.pdf", "gs://my-bucket/doc2.pdf"]
    assert "Successfully submitted 2 document(s)" in data["message"]


def test_ingest_endpoint_error_handling(monkeypatch):
    monkeypatch.setattr(
        rag_manager,
        "import_gcs_documents",
        lambda gcs_uris: {
            "status": "error",
            "corpus": "projects/test-proj/locations/us-central1/ragCorpora/123",
            "error": "Storage bucket not found",
            "paths": gcs_uris,
        },
    )

    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"gcs_uris": ["gs://my-bucket/doc.pdf"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["imported_files_count"] == 0
    assert "Ingestion failed: Storage bucket not found" in data["message"]


def test_ingest_endpoint_invalid_uris():
    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"gcs_uris": ["https://not-a-gcs-path.com/doc.pdf"]},
    )

    assert response.status_code == 400
    assert "must start with gs://" in response.json()["detail"]


def test_ingest_endpoint_empty_uris():
    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"gcs_uris": []},
    )

    assert response.status_code == 400
    assert "At least one GCS URI must be provided" in response.json()["detail"]

