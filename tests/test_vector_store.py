import os
from unittest.mock import MagicMock, patch
from codepipeline.rag_core import RAGCore

def test_backend_selection_qdrant(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE", "qdrant")
    with patch("codepipeline.rag_core.QdrantClient") as MockClient:
        inst = MockClient.return_value
        inst.get_collection.side_effect = Exception("nope")
        RAGCore(collection_name="test")
        MockClient.assert_called()

def test_backend_selection_chroma(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE", "chroma")
    with patch("codepipeline.rag_core.chromadb.HttpClient") as MockClient:
        RAGCore(collection_name="test2")
        MockClient.assert_called()