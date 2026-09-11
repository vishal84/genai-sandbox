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


def test_synthesize_node_citations_and_excerpts(monkeypatch):
    from unittest.mock import MagicMock
    from app.agent import synthesize_node

    class MockResponse:
        text = "Span-based masking masks contiguous spans of tokens [1]."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse()

    monkeypatch.setattr("app.agent.GenAiClient", lambda **kwargs: mock_client)

    state = DocWorkflowState(
        query="What is span masking?",
        filtered_chunks=[
            {
                "text": "Span-based masking replaces sequences of words with mask tokens.",
                "score": 0.15,
                "document_name": "11.pdf",
                "source_uri": "gs://bucket/11.pdf",
                "page_number": 7,
                "page_range": "6-7",
            }
        ],
    )
    answer = synthesize_node(state)
    assert "[1]" in answer
    assert len(state.citations) == 1
    assert state.citations[0]["citation_index"] == 1
    assert state.citations[0]["page_range"] == "6-7"
    assert state.citations[0]["page_number"] == 7
    assert "Span-based masking" in state.citations[0]["snippet"]
    assert state.is_grounded is True


def test_filter_node_no_relevant_chunks():
    state = DocWorkflowState(
        query="What is the tuition at Stanford?",
        retrieved_chunks=[
            {
                "text": "The cafeteria serves sandwiches on Tuesdays.",
                "score": 0.92,
                "document_name": "menu.pdf",
            },
            {
                "text": "Parking permits cost $50 per quarter.",
                "score": 0.89,
                "document_name": "parking.pdf",
            },
        ],
    )
    filtered = filter_node(state)
    assert len(filtered) == 0
    assert state.is_grounded is False


def test_synthesize_node_empty_filtered_chunks():
    from app.agent import synthesize_node

    state = DocWorkflowState(
        query="What is the tuition at Stanford?",
        filtered_chunks=[],
    )
    answer = synthesize_node(state)
    assert "could not find any relevant information" in answer
    assert len(state.citations) == 0
    assert state.is_grounded is False


def test_synthesize_node_no_data_response(monkeypatch):
    from unittest.mock import MagicMock
    from app.agent import synthesize_node

    class MockResponse:
        text = "Based on the provided documents, there is no mention or information regarding the course \"CS224 taught at stanford.\" The ingested documents do not contain this information."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse()
    monkeypatch.setattr("app.agent.GenAiClient", lambda **kwargs: mock_client)

    state = DocWorkflowState(
        query="CS224 taught at stanford.",
        filtered_chunks=[
            {
                "text": "Efficient Estimation of Word Representations in Vector Space...",
                "score": 0.65,
                "document_name": "1301.3781.pdf",
                "source_uri": "gs://bucket/1301.3781.pdf",
                "page_number": 11,
            },
            {
                "text": "Improving neural networks by preventing co-adaptation of feature detectors...",
                "score": 0.70,
                "document_name": "1207.0580.pdf",
                "source_uri": "gs://bucket/1207.0580.pdf",
                "page_number": 18,
            },
        ],
    )
    answer = synthesize_node(state)
    assert "no mention or information regarding" in answer
    assert len(state.citations) == 0
    assert state.is_grounded is False


def test_synthesize_node_no_data_response_strips_spurious_brackets(monkeypatch):
    from unittest.mock import MagicMock
    from app.agent import synthesize_node

    class MockResponse:
        text = "Based on the provided documents [1][2], there is no information regarding CS224."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse()
    monkeypatch.setattr("app.agent.GenAiClient", lambda **kwargs: mock_client)

    state = DocWorkflowState(
        query="CS224 taught at stanford.",
        filtered_chunks=[
            {
                "text": "Word representations in vector space...",
                "score": 0.65,
                "document_name": "1301.3781.pdf",
                "source_uri": "gs://bucket/1301.3781.pdf",
                "page_number": 1,
            }
        ],
    )
    answer = synthesize_node(state)
    assert "[1]" not in answer
    assert "[2]" not in answer
    assert len(state.citations) == 0
    assert state.is_grounded is False


def test_synthesize_node_ungrounded_answer_intercepted(monkeypatch):
    from unittest.mock import MagicMock
    from app.agent import synthesize_node

    class MockResponse:
        # LLM hallucinated without citing any document chunk
        text = "CS224 is Stanford University's Natural Language Processing with Deep Learning course."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse()
    monkeypatch.setattr("app.agent.GenAiClient", lambda **kwargs: mock_client)

    state = DocWorkflowState(
        query="What is CS224 at Stanford?",
        filtered_chunks=[
            {
                "text": "Word embeddings with Word2Vec skip-gram models...",
                "score": 0.65,
                "document_name": "1301.3781.pdf",
                "source_uri": "gs://bucket/1301.3781.pdf",
                "page_number": 1,
            }
        ],
    )
    answer = synthesize_node(state)
    assert "no mention or information regarding" in answer
    assert len(state.citations) == 0
    assert state.is_grounded is False


def test_query_tool_no_sources_when_unmatched(monkeypatch):
    from unittest.mock import MagicMock
    from app.agent import query_doc_intelligence_tool, rag_manager

    class MockResponse:
        text = "Based on the provided documents, there is no mention of Stanford course CS224."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockResponse()
    monkeypatch.setattr("app.agent.GenAiClient", lambda **kwargs: mock_client)

    from app.rag.corpus_manager import RagChunk
    monkeypatch.setattr(
        rag_manager,
        "query_corpus",
        lambda query_text, top_k=5: [
            RagChunk(text="Skip-gram models", score=0.6, document_name="word2vec.pdf", source_uri="gs://bucket/word2vec.pdf")
        ],
    )

    result = query_doc_intelligence_tool("Stanford CS224")
    assert "no mention of Stanford course CS224" in result
    assert "Sources:" not in result


def test_router_node_folder_ingest():
    # Via folder_uri state
    state1 = DocWorkflowState(folder_uri="gs://my-bucket/contracts/")
    assert router_node(state1) == "ingest"

    # Via ingest_folder query prefix
    state2 = DocWorkflowState(query="ingest_folder: gs://my-bucket/contracts/")
    assert router_node(state2) == "ingest"

    # Via ingest_all query prefix
    state3 = DocWorkflowState(query="ingest_all: gs://my-bucket/contracts/")
    assert router_node(state3) == "ingest"


def test_ingest_node_folder_success(monkeypatch):
    from app.agent import rag_manager

    monkeypatch.setattr(
        rag_manager,
        "import_gcs_folder",
        lambda folder_uri: {
            "status": "success",
            "corpus": "projects/test/locations/us-central1/ragCorpora/1",
            "imported_files_count": 4,
            "paths": [f"{folder_uri}doc{i}.pdf" for i in range(4)],
            "folder_uri": folder_uri,
            "message": f"Successfully submitted 4 document(s) from folder '{folder_uri}' for ingestion into Vertex AI RAG.",
        },
    )

    state = DocWorkflowState(intent="ingest", folder_uri="gs://my-bucket/contracts/")
    res = ingest_node(state)

    assert res["status"] == "success"
    assert res["imported_files_count"] == 4
    assert "Successfully submitted 4 document(s)" in state.answer


def test_ingest_node_folder_missing_folder_path():
    state = DocWorkflowState(intent="ingest", folder_uri="gs://my-bucket")
    res = ingest_node(state)
    assert res["status"] == "error"
    assert "When ingesting all, a folder path must be provided" in res["message"]
    assert "Ingestion failed:" in state.answer


def test_ingest_node_folder_single_file_rejected():
    state = DocWorkflowState(intent="ingest", folder_uri="gs://my-bucket/folder/report.pdf")
    res = ingest_node(state)
    assert res["status"] == "error"
    assert "not a single file URI" in res["message"]


def test_ingest_bucket_folder_tool(monkeypatch):
    from app.agent import ingest_bucket_folder_tool, rag_manager

    monkeypatch.setattr(
        rag_manager,
        "import_gcs_folder",
        lambda folder_uri: {
            "status": "success",
            "corpus": "projects/test/locations/us-central1/ragCorpora/1",
            "imported_files_count": 2,
            "paths": [f"{folder_uri}a.pdf", f"{folder_uri}b.pdf"],
            "folder_uri": folder_uri,
            "message": f"Successfully submitted 2 document(s) from folder '{folder_uri}' for ingestion into Vertex AI RAG.",
        },
    )

    msg = ingest_bucket_folder_tool("gs://my-bucket/contracts/")
    assert "Successfully submitted 2 document(s)" in msg

