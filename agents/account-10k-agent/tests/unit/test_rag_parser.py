"""Unit tests for 10-K parser, section detector, signed URLs, and VertexRagManager."""

from __future__ import annotations

from app.rag.corpus_manager import (
    VertexRagManager,
    detect_10k_section,
    extract_company_metadata_from_text,
    extract_pages_from_bytes,
)
from app.rag.signed_urls import generate_gcs_signed_url, parse_gcs_uri


def test_detect_10k_section() -> None:
    assert detect_10k_section("ITEM 1A. RISK FACTORS\nOur cloud infrastructure...") == "Item 1A. Risk Factors"
    assert detect_10k_section("Item 7. Management's Discussion and Analysis") == "Item 7. MD&A & Financial Performance"
    assert detect_10k_section("ITEM 1. BUSINESS OVERVIEW") == "Item 1. Business & Strategy"


def test_extract_pages_from_text_bytes() -> None:
    sample_content = (
        "--- PAGE 1 ---\nITEM 1. BUSINESS\nCompany Name: TestCloud Corp.\nTicker Symbol: TSTC\n"
        "--- PAGE 2 ---\nITEM 1A. RISK FACTORS\nLegacy ERP bottlenecks.\n"
        "--- PAGE 3 ---\nITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\nTotal Revenue: $5.4B (+18% YoY)\n"
    ).encode("utf-8")

    pages = extract_pages_from_bytes(sample_content, "testcloud_2025_10k.txt")
    assert len(pages) == 3
    assert pages[0]["page_number"] == 1
    assert pages[0]["section"] == "Item 1. Business & Strategy"
    assert pages[1]["page_number"] == 2
    assert pages[1]["section"] == "Item 1A. Risk Factors"
    assert pages[2]["page_number"] == 3
    assert pages[2]["section"] == "Item 7. MD&A & Financial Performance"


def test_extract_company_metadata_from_text() -> None:
    text = (
        "UNITED STATES SECURITIES AND EXCHANGE COMMISSION\n"
        "Company Name: NovaScale Systems Inc.\n"
        "Ticker Symbol: NVSC\n"
        "Fiscal Year Ended: FY2025\n"
    )
    meta = extract_company_metadata_from_text(text, "novascale_10k.txt")
    assert meta["company_name"] == "NovaScale Systems Inc."
    assert meta["ticker"] == "NVSC"
    assert meta["fiscal_year"] == "FY2025"


def test_signed_url_helpers() -> None:
    bucket, blob = parse_gcs_uri("gs://my-10k-bucket/filings/apex_10k.pdf")
    assert bucket == "my-10k-bucket"
    assert blob == "filings/apex_10k.pdf"

    fallback_url = generate_gcs_signed_url("gs://my-10k-bucket/filings/apex_10k.pdf")
    assert fallback_url.startswith("https://storage.mtls.cloud.google.com/my-10k-bucket/filings/apex_10k.pdf")


def test_rag_manager_load_sample_and_query() -> None:
    manager = VertexRagManager(project_id="")
    doc_meta = manager.load_sample_10k("apex_cloud_retail_2025_10k.txt")
    assert doc_meta["ticker"] == "APXR"
    assert doc_meta["company_name"] == "Apex Cloud & Retail Corp."
    assert doc_meta["pages_count"] >= 3

    chunks = manager.query_corpus(
        "Project Horizon mainframe migration CapEx",
        top_k=3,
        document_name=doc_meta["display_name"],
    )
    assert len(chunks) > 0
    assert chunks[0].document_name == doc_meta["display_name"]
    assert chunks[0].page_number is not None

