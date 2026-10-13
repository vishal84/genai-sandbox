"""Unit tests for ADK 2.0 10-K workflow nodes and agent tools."""

from __future__ import annotations

from app.agent import (
    Account10KWorkflowState,
    analyze_10k_account_tool,
    analyze_10k_node,
    filter_node,
    list_indexed_10k_documents_tool,
    query_10k_filings_tool,
    rag_manager,
    retrieve_node,
    router_node,
    synthesize_node,
)


def test_router_node_branches() -> None:
    s_ingest = Account10KWorkflowState(action="ingest", gcs_uris=["gs://b/10k.pdf"])
    assert router_node(s_ingest) == {"action": "ingest"}

    s_analyze = Account10KWorkflowState(action="analyze", document_name="test.pdf")
    assert router_node(s_analyze) == {"action": "analyze"}

    s_query = Account10KWorkflowState(action="query", query="What is revenue?")
    assert router_node(s_query) == {"action": "query"}


def test_analyze_10k_node_and_tool() -> None:
    doc_meta = rag_manager.load_sample_10k("apex_cloud_retail_2025_10k.txt")
    report = analyze_10k_account_tool(
        document_name=doc_meta["display_name"],
        company_name=doc_meta["company_name"],
        ticker=doc_meta["ticker"],
        fiscal_year=doc_meta["fiscal_year"],
        custom_focus="Mainframe Exit & GenAI FinOps",
    )

    assert report["ticker"] == "APXC"
    assert report["company_name"] == "Apex OmniRetail & Cloud Holdings Inc."
    assert report["account_health_score"] >= 70
    assert len(report["financial_metrics"]) >= 3
    assert len(report["strategic_initiatives"]) >= 2
    assert len(report["risk_factors"]) >= 2
    assert len(report["recommendations"]) >= 3
    assert len(report["citations"]) >= 3

    first_rec = report["recommendations"][0]
    assert "title" in first_rec
    assert "target_stakeholder" in first_rec
    assert len(first_rec["recommended_actions"]) > 0
    assert len(first_rec["talking_points"]) > 0


def test_query_10k_workflow_and_tool() -> None:
    doc_meta = rag_manager.load_sample_10k("vanguard_industrial_fintech_2025_10k.txt")
    res = query_10k_filings_tool(
        query="What are the ERP fragmentation and cybersecurity risks in Item 1A?",
        document_name=doc_meta["display_name"],
        top_k=3,
    )
    assert res["answer"]
    assert len(res["citations"]) > 0
    assert res["citations"][0]["document_name"] == doc_meta["display_name"]

    listed = list_indexed_10k_documents_tool()
    assert listed["count"] >= 1


