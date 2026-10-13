"""Unit tests for FastAPI endpoints in app/fast_api_app.py."""

from __future__ import annotations

import io
from fastapi.testclient import TestClient

from app.fast_api_app import app

client = TestClient(app)


def test_status_and_samples_endpoints() -> None:
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["agent"] == "account_10k_agent"
    assert data["model"] == "gemini-3.8-flash"

    samples_res = client.get("/api/samples")
    assert samples_res.status_code == 200
    assert len(samples_res.json()["samples"]) >= 2


def test_load_sample_and_list_accounts() -> None:
    res = client.post(
        "/api/sample",
        json={"sample_key": "voltgrid_industrial_2025_10k.txt"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
    report = payload["account_report"]
    assert report["ticker"] == "VLTX"
    assert len(report["recommendations"]) >= 2

    accts_res = client.get("/api/accounts")
    assert accts_res.status_code == 200
    accounts = accts_res.json()["accounts"]
    assert any(a["ticker"] == "VLTX" for a in accounts)

    detail_res = client.get(f"/api/accounts/{report['account_id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["company_name"] == "VoltGrid Industrial Technologies Inc."


def test_upload_custom_10k_and_chat() -> None:
    custom_10k_text = (
        "--- PAGE 1 ---\n"
        "ITEM 1. BUSINESS\n"
        "Company Name: Stratosphere BioCloud Inc.\n"
        "Ticker Symbol: SBIO\n"
        "Fiscal Year Ended: FY2025\n"
        "We are modernizing genomics data pipelines on cloud infrastructure.\n"
        "--- PAGE 2 ---\n"
        "ITEM 1A. RISK FACTORS\n"
        "Rising GPU compute expenses and HIPAA compliance risks.\n"
        "--- PAGE 3 ---\n"
        "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\n"
        "Total Revenue: $3.20 billion (+15.4% YoY)\n"
        "Operating Income: $480 million (+18.0% YoY)\n"
        "Free Cash Flow: $390 million (+21.0% YoY)\n"
    )
    files = {
        "file": ("stratosphere_2025_10k.txt", io.BytesIO(custom_10k_text.encode("utf-8")), "text/plain"),
    }
    data = {
        "company_name": "Stratosphere BioCloud Inc.",
        "ticker": "SBIO",
        "fiscal_year": "FY2025",
        "custom_focus": "Genomics Data Lakehouse & HIPAA Security",
        "auto_analyze": "true",
    }
    up_res = client.post("/api/upload", files=files, data=data)
    assert up_res.status_code == 200
    up_json = up_res.json()
    assert up_json["status"] == "success"
    assert up_json["account_report"]["ticker"] == "SBIO"
    assert up_json["account_report"]["financial_metrics"][0]["value"] == "$3.20 billion"

    chat_res = client.post(
        "/api/chat",
        json={
            "message": "What are the HIPAA and GPU compute risks in Item 1A?",
            "account_id": up_json["account_report"]["account_id"],
        },
    )
    assert chat_res.status_code == 200
    chat_json = chat_res.json()
    assert chat_json["answer"]
    assert len(chat_json["citations"]) >= 1

