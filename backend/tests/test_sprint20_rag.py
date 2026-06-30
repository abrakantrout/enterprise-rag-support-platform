import os
import sys
import unittest

# Add backend to path to allow importing app and models
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.gemini_service import GeminiService
from app.services.prompt_builder_service import PromptBuilderService

class TestSprint20RAGVerification(unittest.TestCase):

    def setUp(self):
        self.gemini_service = GeminiService()
        self.prompt_builder_service = PromptBuilderService()

    def test_mock_does_not_output_30_days_for_14_days_context(self):
        """Test that mock Gemini response reflects context and query instead of hardcoded 30 days refund statement."""
        query = "How many days do I have to request a refund?"
        retrieval_results = [{
            "chunk_id": "c1",
            "document_id": "doc1",
            "page_number": 1,
            "chunk_text": "Customers can request refunds within 14 days.",
            "metadata": {"filename": "Refund_Policy.txt"}
        }]
        
        prompt_data = self.prompt_builder_service.build_prompt(
            query=query,
            retrieval_results=retrieval_results
        )
        
        answer = self.gemini_service.generate_answer(prompt_data["prompt"])
        
        # Verify it includes the correct context text and not the old 30 days mock
        self.assertIn("14 days", answer)
        self.assertNotIn("30 days", answer)
        self.assertIn("Refund_Policy.txt", answer)
        self.assertIn("c1", answer)

    def test_different_questions_return_different_grounded_responses(self):
        """Test that different questions yield distinct mock responses based on the context provided."""
        # Query 1: Water damage
        query_water = "Is water damage covered?"
        context_water = [{
            "chunk_id": "c2",
            "document_id": "doc2",
            "page_number": 1,
            "chunk_text": "Water damage is not covered under the standard warranty.",
            "metadata": {"filename": "Warranty.txt"}
        }]
        prompt_data_water = self.prompt_builder_service.build_prompt(query=query_water, retrieval_results=context_water)
        answer_water = self.gemini_service.generate_answer(prompt_data_water["prompt"])
        
        # Query 2: Shipping duration
        query_shipping = "How long does standard shipping take?"
        context_shipping = [{
            "chunk_id": "c3",
            "document_id": "doc3",
            "page_number": 1,
            "chunk_text": "Standard shipping takes 3-7 business days.",
            "metadata": {"filename": "Shipping.txt"}
        }]
        prompt_data_shipping = self.prompt_builder_service.build_prompt(query=query_shipping, retrieval_results=context_shipping)
        answer_shipping = self.gemini_service.generate_answer(prompt_data_shipping["prompt"])

        # Check distinctions
        self.assertIn("not covered", answer_water.lower())
        self.assertIn("3-7 business days", answer_shipping.lower())
        self.assertNotEqual(answer_water, answer_shipping)

    def test_refusal_when_no_matching_info(self):
        """Test that query is safely refused when context doesn't match."""
        query = "Do you provide student discounts?"
        context = [{
            "chunk_id": "c1",
            "document_id": "doc1",
            "page_number": 1,
            "chunk_text": "Customers can request refunds within 14 days.",
            "metadata": {"filename": "Refund_Policy.txt"}
        }]
        prompt_data = self.prompt_builder_service.build_prompt(query=query, retrieval_results=context)
        answer = self.gemini_service.generate_answer(prompt_data["prompt"])
        
        self.assertEqual(answer, "I could not find relevant information in the uploaded documents.")

if __name__ == "__main__":
    unittest.main()
