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


def test_ingest_endpoint_folder_success(monkeypatch):
    monkeypatch.setattr(
        rag_manager,
        "import_gcs_folder",
        lambda folder_uri: {
            "status": "success",
            "corpus": "projects/test-proj/locations/us-central1/ragCorpora/123",
            "imported_files_count": 3,
            "paths": ["gs://my-bucket/contracts/doc1.pdf", "gs://my-bucket/contracts/doc2.pdf", "gs://my-bucket/contracts/doc3.pdf"],
            "folder_uri": folder_uri,
            "message": f"Successfully submitted 3 document(s) from folder '{folder_uri}' for ingestion into Vertex AI RAG.",
        },
    )

    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"folder_uri": "gs://my-bucket/contracts/"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_files_count"] == 3
    assert data["folder_uri"] == "gs://my-bucket/contracts/"
    assert "Successfully submitted 3 document(s)" in data["message"]


def test_ingest_endpoint_folder_missing_folder_path():
    client = TestClient(app, raise_server_exceptions=True)

    # Bucket root without slash
    response = client.post(
        "/api/ingest",
        json={"folder_uri": "gs://my-bucket"},
    )
    assert response.status_code == 400
    assert "When ingesting all, a folder path must be provided" in response.json()["detail"]

    # Bucket root with slash only
    response2 = client.post(
        "/api/ingest",
        json={"folder_uri": "gs://my-bucket/"},
    )
    assert response2.status_code == 400
    assert "When ingesting all, a folder path must be provided" in response2.json()["detail"]


def test_ingest_endpoint_folder_single_file_rejected():
    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"folder_uri": "gs://my-bucket/contracts/quarterly_report.pdf"},
    )
    assert response.status_code == 400
    assert "A folder path must be provided when ingesting all, not a single file URI" in response.json()["detail"]


def test_ingest_endpoint_folder_invalid_scheme():
    client = TestClient(app, raise_server_exceptions=True)
    response = client.post(
        "/api/ingest",
        json={"folder_uri": "https://storage.googleapis.com/my-bucket/contracts/"},
    )
    assert response.status_code == 400
    assert "must start with gs://" in response.json()["detail"]

