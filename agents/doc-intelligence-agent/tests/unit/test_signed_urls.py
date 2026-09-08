"""Unit tests for GCS Signed URL generation."""

import pytest
from app.rag.signed_urls import generate_gcs_signed_url, parse_gcs_uri


def test_parse_gcs_uri_valid():
    bucket, blob = parse_gcs_uri("gs://my-bucket/folder/document.pdf")
    assert bucket == "my-bucket"
    assert blob == "folder/document.pdf"


def test_parse_gcs_uri_invalid():
    with pytest.raises(ValueError):
        parse_gcs_uri("https://storage.googleapis.com/bucket/doc.pdf")


def test_generate_signed_url_fallback():
    # In test environment without active GCP credentials, should fallback to Google Cloud Console URL gracefully
    url = generate_gcs_signed_url("gs://demo-bucket/reports/q1.pdf")
    assert "demo-bucket" in url
    assert "reports/q1.pdf" in url

