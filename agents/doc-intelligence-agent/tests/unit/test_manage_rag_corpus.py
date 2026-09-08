"""Unit tests for manage_rag_corpus.py .env parsing and synchronization."""

import tempfile
from pathlib import Path
from scripts.manage_rag_corpus import parse_env_file, update_env_file


def test_parse_env_file():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".env") as f:
        f.write("# Sample configuration\n")
        f.write("GOOGLE_CLOUD_PROJECT=test-proj\n")
        f.write("GCS_DOCUMENTS_BUCKET=bucket-123\n")
        f.write("RAG_CORPUS_ID=\n")
        f_path = Path(f.name)

    try:
        parsed = parse_env_file(f_path)
        assert parsed["GOOGLE_CLOUD_PROJECT"] == "test-proj"
        assert parsed["GCS_DOCUMENTS_BUCKET"] == "bucket-123"
        assert parsed["RAG_CORPUS_ID"] == ""
    finally:
        f_path.unlink()


def test_update_env_file_preserves_comments_and_updates():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".env") as f:
        f.write("# Header comment\n")
        f.write("GOOGLE_CLOUD_PROJECT=old-project\n")
        f.write("GCS_DOCUMENTS_BUCKET=old-bucket\n")
        f.write("RAG_CORPUS_ID=\n")
        f_path = Path(f.name)

    try:
        update_env_file(
            f_path,
            {
                "GCS_DOCUMENTS_BUCKET": "new-bucket-456",
                "RAG_CORPUS_ID": "corpus-789",
                "NEW_KEY": "new-val",
            },
        )
        content = f_path.read_text()
        assert "# Header comment" in content
        assert "GOOGLE_CLOUD_PROJECT=old-project" in content
        assert "GCS_DOCUMENTS_BUCKET=new-bucket-456" in content
        assert "RAG_CORPUS_ID=corpus-789" in content
        assert "NEW_KEY=new-val" in content
    finally:
        f_path.unlink()

