import logging
from typing import List
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingServiceError(Exception):
    """Custom exception raised when embedding generation fails."""
    pass

class EmbeddingService:
    """
    Handles generating numerical vector embeddings for text chunks using Google Gemini API.
    """
    def __init__(self):
        self.api_key = settings.google_api_key
        self.model_name = settings.embedding_model
        self._configured = False
        self._check_configuration()

    def _check_configuration(self):
        # Refresh configuration values from settings
        self.api_key = settings.google_api_key
        self.model_name = settings.embedding_model
        if self.api_key and self.api_key not in ("your-google-api-key-here", ""):
            # Only configure the real SDK if not running in mock/fail test mode
            if not self.api_key.startswith("mock-") and not self.api_key.startswith("fail-") and self.api_key != "mock-key":
                genai.configure(api_key=self.api_key)
            self._configured = True
        else:
            self._configured = False

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a vector embedding for a single text string.
        """
        if not text:
            raise EmbeddingServiceError("Cannot generate embedding for empty text.")
            
        self._check_configuration()
        if not self._configured:
            raise EmbeddingServiceError("Google API key is missing or not configured.")

        # Handle simulated failure for testing
        if self.api_key.startswith("fail-"):
            raise EmbeddingServiceError("Simulated embedding provider failure.")

        # Handle mock embedding generation for testing
        if self.api_key.startswith("mock-") or self.api_key == "mock-key":
            return [0.1] * 768

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            
            if not response or 'embedding' not in response:
                raise EmbeddingServiceError("Empty or invalid response from embedding provider.")
                
            return response['embedding']
        except Exception as e:
            # Avoid logging raw keys or sensitive chunk text
            logger.error(f"Failed to generate embedding for text chunk (length: {len(text)}): {str(e)}")
            raise EmbeddingServiceError(f"Embedding provider failure: {str(e)}")

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates vector embeddings for a list of text strings.
        """
        if not texts:
            return []
            
        for i, text in enumerate(texts):
            if not text:
                raise EmbeddingServiceError(f"Cannot generate embedding for empty text at index {i}.")

        self._check_configuration()
        if not self._configured:
            raise EmbeddingServiceError("Google API key is missing or not configured.")

        # Handle simulated failure for testing
        if self.api_key.startswith("fail-"):
            raise EmbeddingServiceError("Simulated embedding provider failure.")

        # Handle mock embedding generation for testing
        if self.api_key.startswith("mock-") or self.api_key == "mock-key":
            return [[0.1] * 768 for _ in texts]

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document"
            )
            
            if not response or 'embedding' not in response:
                raise EmbeddingServiceError("Empty or invalid response from embedding provider.")
                
            return response['embedding']
        except Exception as e:
            # Avoid logging raw keys or sensitive chunk text
            total_len = sum(len(t) for t in texts)
            logger.error(f"Failed to generate batch embeddings for {len(texts)} chunks (total length: {total_len}): {str(e)}")
            raise EmbeddingServiceError(f"Embedding provider failure: {str(e)}")
