"""Unit tests for ADK 2.0 Graph Workflow nodes and state."""

from app.agent import (
    DocWorkflowState,
    filter_node,
    ingest_node,
    router_node,
)


def test_router_node_query():
    state = DocWorkflowState(query="What is the net income?")
    route = router_node(state)
    assert route == "query"


def test_router_node_ingest():
    state = DocWorkflowState(query="ingest: gs://bucket/doc.pdf", gcs_uris=["gs://bucket/doc.pdf"])
    route = router_node(state)
    assert route == "ingest"


def test_filter_node_relevance():
    state = DocWorkflowState(
        query="What is the interest rate?",
        retrieved_chunks=[
            {
                "text": "The interest rate is fixed at 4.5% per annum.",
                "score": 0.15,
                "document_name": "loan_agreement.pdf",
                "source_uri": "gs://docs/loan_agreement.pdf",
                "page_number": 3,
            },
            {
                "text": "The cafeteria menu includes pizza on Thursdays.",
                "score": 0.95,
                "document_name": "handbook.pdf",
                "source_uri": "gs://docs/handbook.pdf",
                "page_number": 1,
            },
        ],
    )
    filtered = filter_node(state)
    assert len(filtered) == 1
    assert "interest rate" in filtered[0]["text"]
    assert state.is_grounded is True


def test_ingest_node_validation():
    state = DocWorkflowState(intent="ingest", gcs_uris=[])
    result = ingest_node(state)
    assert result["status"] == "error"
    assert "No valid gs:// PDF URIs" in result["message"]


def test_function_nodes_are_callable():
    from google.adk.workflow import FunctionNode

    assert isinstance(router_node, FunctionNode)
    assert isinstance(ingest_node, FunctionNode)
    assert isinstance(filter_node, FunctionNode)
    assert callable(router_node)
    assert callable(ingest_node)
    assert callable(filter_node)


def test_ingest_node_success(monkeypatch):
    from app.agent import rag_manager

    monkeypatch.setattr(
        rag_manager,
        "import_gcs_documents",
        lambda gcs_uris: {
            "status": "success",
            "corpus": "test-corpus",
            "imported_files_count": len(gcs_uris),
            "paths": gcs_uris,
        },
    )

    state = DocWorkflowState(intent="ingest", gcs_uris=["gs://bucket/sample.pdf"])
    result = ingest_node(state)
    assert result["status"] == "success"
    assert result["imported_files_count"] == 1
    assert "Successfully submitted 1 document(s)" in state.answer


def test_ingest_node_error(monkeypatch):
    from app.agent import rag_manager

    monkeypatch.setattr(
        rag_manager,
        "import_gcs_documents",
        lambda gcs_uris: {
            "status": "error",
            "corpus": "test-corpus",
            "error": "Permission denied accessing bucket",
            "paths": gcs_uris,
        },
    )

    state = DocWorkflowState(intent="ingest", gcs_uris=["gs://bucket/sample.pdf"])
    result = ingest_node(state)
    assert result["status"] == "error"
    assert result["imported_files_count"] == 0
    assert "Ingestion failed: Permission denied accessing bucket" in state.answer


