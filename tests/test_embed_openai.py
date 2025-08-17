from unittest.mock import MagicMock, patch

from codepipeline.rag_core import RAGCore


def test_embed_text_uses_openai():
    with patch('codepipeline.rag_core.OpenAI') as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[1.0, 2.0, 3.0])]
        )
        rag = RAGCore()
        vec = rag._embed_text("hello world")
        MockClient.assert_called()
        mock_instance.embeddings.create.assert_called_once()
        assert vec == [1.0, 2.0, 3.0]
