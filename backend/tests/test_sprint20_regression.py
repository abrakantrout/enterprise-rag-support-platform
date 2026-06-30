import os
import sys
import unittest
from unittest.mock import patch

# Add backend to path to allow importing app and models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService
from app.services.vector_indexing_service import VectorIndexingService
from app.database.chroma import get_chroma_client

class TestSprint20Regression(unittest.TestCase):

    def setUp(self):
        self.original_google_api_key = settings.google_api_key
        self.original_gemini_api_key = settings.gemini_api_key
        self.original_collection = settings.chroma_collection_name
        self.original_min_similarity = settings.min_similarity_score

        # Force mock settings for local test stability
        settings.google_api_key = "mock-key"
        settings.gemini_api_key = "mock-key"
        settings.chroma_collection_name = "test_regression_collection"
        settings.min_similarity_score = 0.70

        # Clean collection
        self.chroma_client = get_chroma_client()
        try:
            self.chroma_client.delete_collection(name=settings.chroma_collection_name)
        except Exception:
            pass

    def tearDown(self):
        settings.google_api_key = self.original_google_api_key
        settings.gemini_api_key = self.original_gemini_api_key
        settings.chroma_collection_name = self.original_collection
        settings.min_similarity_score = self.original_min_similarity

        try:
            self.chroma_client.delete_collection(name="test_regression_collection")
        except Exception:
            pass

    def test_real_key_config_does_not_enter_mock_mode(self):
        """Test that a valid, real-looking API key initializes REAL embedding mode."""
        # Case 1: Real key is in GEMINI_API_KEY but not GOOGLE_API_KEY
        settings.google_api_key = ""
        settings.gemini_api_key = "AIzaSyRealGeminiKeyHere"
        
        service = EmbeddingService()
        self.assertEqual(service.embedding_mode, "REAL")
        self.assertTrue(service._configured)

        # Case 2: Real key is in GOOGLE_API_KEY
        settings.google_api_key = "AIzaSyRealGoogleKeyHere"
        settings.gemini_api_key = ""
        
        service2 = EmbeddingService()
        self.assertEqual(service2.embedding_mode, "REAL")
        self.assertTrue(service2._configured)

    def test_mock_key_enters_mock_mode(self):
        """Test that a key beginning with mock- or matching mock-key enters MOCK mode."""
        # Case 1: mock-key
        settings.google_api_key = "mock-key"
        settings.gemini_api_key = ""
        service = EmbeddingService()
        self.assertEqual(service.embedding_mode, "MOCK")

        # Case 2: mock-prefix
        settings.google_api_key = "mock-api-key-value"
        settings.gemini_api_key = ""
        service2 = EmbeddingService()
        self.assertEqual(service2.embedding_mode, "MOCK")

    def test_empty_or_placeholder_key_enters_mock_mode(self):
        """Test that missing or placeholder keys enter MOCK mode instead of crashing initialization."""
        # Case 1: Empty string
        settings.google_api_key = ""
        settings.gemini_api_key = ""
        service = EmbeddingService()
        self.assertEqual(service.embedding_mode, "MOCK")

        # Case 2: Placeholder values
        settings.google_api_key = "your-google-api-key-here"
        settings.gemini_api_key = "your-gemini-api-key-here"
        service2 = EmbeddingService()
        self.assertEqual(service2.embedding_mode, "MOCK")

    def test_mock_only_semantic_retrieval_works(self):
        """[MOCK ONLY] Test that semantic questions correctly retrieve their corresponding handbook chunks in mock mode."""
        # 1. Index the mock sections of the handbook
        handbook_sections = [
            ("Working Hours", "Employees are expected to work from 9:00 AM to 6:00 PM, Monday through Friday."),
            ("Remote Work", "Employees may work remotely for up to 3 days per week with manager approval."),
            ("Leave Policy", "Employees receive 24 paid leave days each calendar year. Unused leave cannot be carried forward to the next year."),
            ("Laptop Policy", "Every employee receives one company laptop. Personal software installation is prohibited unless approved by IT."),
            ("IT Support", "Employees should contact the IT Help Desk by emailing helpdesk@company.com."),
            ("Password Policy", "Passwords must contain at least 12 characters. Passwords must be changed every 90 days. Multi-factor authentication is mandatory.")
        ]

        embed_service = EmbeddingService()
        indexing_service = VectorIndexingService()

        chunks_data = []
        for idx, (title, content) in enumerate(handbook_sections):
            chunk_text = f"{title}\n{content}"
            embedding = embed_service.generate_embedding(chunk_text)
            
            chunks_data.append({
                "chunk_id": f"reg_chunk_{idx}",
                "text": chunk_text,
                "embedding": embedding,
                "metadata": {
                    "document_id": "handbook_doc",
                    "organization_id": "test_org",
                    "filename": "Employee_Handbook.txt"
                }
            })

        # Index chunks into Chroma
        indexed = indexing_service.index_chunks(document_id="handbook_doc", chunks_data=chunks_data)
        self.assertEqual(indexed, len(handbook_sections))

        # 2. Test semantic queries
        retrieval_service = RetrievalService()

        queries = [
            ("Can I work from home?", "Remote Work"),
            ("How many vacation days do employees get?", "Leave Policy"),
            ("How long should passwords be?", "Password Policy"),
            ("Can I install my own software?", "Laptop Policy"),
            ("How do I contact IT support?", "IT Support")
        ]

        for query, expected_title in queries:
            results = retrieval_service.retrieve_relevant_chunks(
                query=query,
                organization_id="test_org",
                top_k=3
            )
            self.assertTrue(len(results) > 0, f"Query '{query}' returned no results")
            best_match = results[0]
            self.assertIn(expected_title, best_match["chunk_text"])
            self.assertTrue(best_match["similarity_score"] >= 0.70)

    def test_stale_vectors_deleted_on_document_cleanup(self):
        """Test that soft-deletion of document triggers clean up of vectors in ChromaDB."""
        embed_service = EmbeddingService()
        indexing_service = VectorIndexingService()
        retrieval_service = RetrievalService()

        # 1. Index document
        chunk_text = "This is a secret document containing confidential refund guidelines."
        embedding = embed_service.generate_embedding(chunk_text)
        chunks_data = [{
            "chunk_id": "refund_c1",
            "text": chunk_text,
            "embedding": embedding,
            "metadata": {
                "document_id": "old_refund_doc",
                "organization_id": "test_org",
                "filename": "Old_Refund_Policy.txt"
            }
        }]

        indexing_service.index_chunks(document_id="old_refund_doc", chunks_data=chunks_data)

        # Verify it is retrieved
        results = retrieval_service.retrieve_relevant_chunks(
            query="confidential refund guidelines",
            organization_id="test_org"
        )
        self.assertEqual(len(results), 1)

        # 2. Perform cleanup/deletion
        indexing_service.delete_document_vectors(document_id="old_refund_doc")

        # Verify it is no longer retrieved
        results_after = retrieval_service.retrieve_relevant_chunks(
            query="confidential refund guidelines",
            organization_id="test_org"
        )
        self.assertEqual(len(results_after), 0)

    def test_mock_only_ungrounded_queries_are_filtered_out(self):
        """[MOCK ONLY] Test that queries with no relevant information in context are filtered out by similarity score threshold in mock mode."""
        # Index Laptop Policy
        embed_service = EmbeddingService()
        indexing_service = VectorIndexingService()
        retrieval_service = RetrievalService()

        chunk_text = "Laptop Policy\nEvery employee receives one company laptop."
        embedding = embed_service.generate_embedding(chunk_text)
        chunks_data = [{
            "chunk_id": "laptop_c1",
            "text": chunk_text,
            "embedding": embedding,
            "metadata": {
                "document_id": "laptop_doc",
                "organization_id": "test_org",
                "filename": "Laptop_Policy.txt"
            }
        }]
        indexing_service.index_chunks(document_id="laptop_doc", chunks_data=chunks_data)

        # Query completely unrelated text
        results = retrieval_service.retrieve_relevant_chunks(
            query="Do employees receive annual performance bonuses?",
            organization_id="test_org"
        )
        # Should be empty because similarity score is below the 0.70 threshold
        self.assertEqual(len(results), 0)

if __name__ == "__main__":
    unittest.main()
