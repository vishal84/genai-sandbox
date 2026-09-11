"""Unit tests for VertexRagManager and RagChunk."""

from app.rag.corpus_manager import RagChunk, VertexRagManager


def test_rag_chunk_serialization():
    chunk = RagChunk(
        text="Revenue grew by 14% year-over-year.",
        score=0.12,
        source_uri="gs://financial-docs/q4_report.pdf",
        document_name="q4_report.pdf",
        page_number=12,
        page_range="12-13",
        signed_url="https://storage.googleapis.com/signed-url-test",
    )
    serialized = chunk.to_dict()
    assert serialized["text"] == "Revenue grew by 14% year-over-year."
    assert serialized["score"] == 0.12
    assert serialized["document_name"] == "q4_report.pdf"
    assert serialized["page_number"] == 12
    assert serialized["page_range"] == "12-13"
    assert serialized["signed_url"] == "https://storage.googleapis.com/signed-url-test"


def test_extract_relevant_excerpt():
    from app.rag.corpus_manager import extract_relevant_excerpt

    full_text = (
        "Introduction to neural networks. Section 1 covers basic MLPs. "
        "Span-based masking selects contiguous spans of words rather than single tokens. "
        "The masking rate is typically 15 percent of all tokens. Section 3 covers evaluation."
    )
    excerpt = extract_relevant_excerpt("what is span-based masking?", full_text, max_chars=120)
    assert "Span-based masking" in excerpt
    assert "Introduction" not in excerpt


def test_extract_relevant_excerpt_short_text():
    from app.rag.corpus_manager import extract_relevant_excerpt

    short_text = "Span-based masking is used in SpanBERT."
    excerpt = extract_relevant_excerpt("masking", short_text, max_chars=200)
    assert excerpt == short_text


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


def test_parse_gcs_uri():
    bucket, prefix = VertexRagManager.parse_gcs_uri("gs://my-bucket/contracts/2024/")
    assert bucket == "my-bucket"
    assert prefix == "contracts/2024/"

    bucket2, prefix2 = VertexRagManager.parse_gcs_uri("gs://my-bucket")
    assert bucket2 == "my-bucket"
    assert prefix2 == ""

    bucket3, prefix3 = VertexRagManager.parse_gcs_uri("invalid-uri")
    assert bucket3 == ""
    assert prefix3 == ""


def test_import_gcs_folder_validation():
    manager = VertexRagManager(project_id="test-proj")

    # Invalid scheme
    res1 = manager.import_gcs_folder("https://storage.googleapis.com/bucket/folder/")
    assert res1["status"] == "error"
    assert "starting with gs://" in res1["message"]

    # Missing folder path (bucket root only)
    res2 = manager.import_gcs_folder("gs://my-bucket")
    assert res2["status"] == "error"
    assert "When ingesting all, a folder path must be provided" in res2["message"]

    res3 = manager.import_gcs_folder("gs://my-bucket/")
    assert res3["status"] == "error"
    assert "When ingesting all, a folder path must be provided" in res3["message"]

    # Single file rejected
    res4 = manager.import_gcs_folder("gs://my-bucket/contracts/report.pdf")
    assert res4["status"] == "error"
    assert "not a single file URI" in res4["message"]


def test_import_gcs_folder_success(monkeypatch):
    manager = VertexRagManager(project_id="test-proj")

    # Mock list_gcs_folder_files to return 2 discovered files
    monkeypatch.setattr(
        manager,
        "list_gcs_folder_files",
        lambda folder_uri: (
            ["gs://my-bucket/contracts/c1.pdf", "gs://my-bucket/contracts/c2.pdf"],
            None,
        ),
    )
    # Mock import_gcs_documents
    monkeypatch.setattr(
        manager,
        "import_gcs_documents",
        lambda gcs_uris, chunk_size=512, chunk_overlap=100, corpus_name=None: {
            "status": "success",
            "corpus": "projects/test-proj/locations/us-central1/ragCorpora/123",
            "imported_files_count": len(gcs_uris),
            "paths": gcs_uris,
        },
    )

    res = manager.import_gcs_folder("gs://my-bucket/contracts")
    assert res["status"] == "success"
    assert res["imported_files_count"] == 2
    assert res["folder_uri"] == "gs://my-bucket/contracts/"
    assert "2 document(s)" in res["message"]


def test_import_gcs_documents_batches_over_25_files(monkeypatch):
    from unittest.mock import MagicMock
    manager = VertexRagManager(project_id="test-proj", corpus_id="c-123")

    mock_rag = MagicMock()
    recorded_batches = []

    def mock_import_files(corpus_name, paths, transformation_config, max_embedding_requests_per_min):
        assert len(paths) <= 25, f"Batch size {len(paths)} exceeded 25 limit!"
        recorded_batches.append(list(paths))
        mock_resp = MagicMock()
        mock_resp.imported_rag_files_count = len(paths)
        return mock_resp

    mock_rag.import_files.side_effect = mock_import_files
    monkeypatch.setattr("vertexai.preview.rag.import_files", mock_rag.import_files)
    monkeypatch.setattr("vertexai.preview.rag.TransformationConfig", MagicMock())
    monkeypatch.setattr("vertexai.preview.rag.ChunkingConfig", MagicMock())
    monkeypatch.setattr(manager, "_ensure_initialized", lambda: None)

    # 60 files: should be split into 3 batches (25, 25, 10)
    test_uris = [f"gs://my-bucket/doc_{i}.pdf" for i in range(60)]
    res = manager.import_gcs_documents(test_uris)

    assert res["status"] == "success"
    assert res["imported_files_count"] == 60
    assert len(recorded_batches) == 3
    assert len(recorded_batches[0]) == 25
    assert len(recorded_batches[1]) == 25
    assert len(recorded_batches[2]) == 10


def test_import_gcs_folder_direct_folder_avoids_25_limit(monkeypatch):
    manager = VertexRagManager(project_id="test-proj")

    # 50 discovered files in the folder
    fake_50_files = [f"gs://my-bucket/contracts/doc_{i}.pdf" for i in range(50)]
    monkeypatch.setattr(
        manager,
        "list_gcs_folder_files",
        lambda folder_uri: (fake_50_files, None),
    )

    imported_paths = []

    def mock_import_docs(gcs_uris, **kwargs):
        imported_paths.append(list(gcs_uris))
        return {
            "status": "success",
            "corpus": "projects/test-proj/locations/us-central1/ragCorpora/123",
            "imported_files_count": len(gcs_uris),
            "paths": gcs_uris,
        }

    monkeypatch.setattr(manager, "import_gcs_documents", mock_import_docs)

    res = manager.import_gcs_folder("gs://my-bucket/contracts/")

    assert res["status"] == "success"
    # Should submit the single folder URI to Vertex AI directly
    assert imported_paths == [["gs://my-bucket/contracts/"]]
    assert len(imported_paths[0]) == 1  # 1 path submitted, NOT 50
    assert res["imported_files_count"] == 50
    assert "50 document(s)" in res["message"]


def test_import_gcs_folder_fallback_to_batched_files(monkeypatch):
    manager = VertexRagManager(project_id="test-proj")

    fake_30_files = [f"gs://my-bucket/contracts/doc_{i}.pdf" for i in range(30)]
    monkeypatch.setattr(
        manager,
        "list_gcs_folder_files",
        lambda folder_uri: (fake_30_files, None),
    )

    call_count = 0

    def mock_import_docs(gcs_uris, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Direct folder import fails (e.g. simulated server error)
            return {"status": "error", "error": "Folder path not supported in region", "imported_files_count": 0}
        # Fallback to batched files succeeds
        return {
            "status": "success",
            "corpus": "projects/test-proj/locations/us-central1/ragCorpora/123",
            "imported_files_count": len(gcs_uris),
            "paths": gcs_uris,
        }

    monkeypatch.setattr(manager, "import_gcs_documents", mock_import_docs)

    res = manager.import_gcs_folder("gs://my-bucket/contracts/")
    assert res["status"] == "success"
    assert call_count == 2
    assert res["imported_files_count"] == 30




