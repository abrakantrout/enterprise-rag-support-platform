import logging
from typing import List
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

SYNONYMS = {
    "vacation": ["leave", "holiday"],
    "vacations": ["leave", "holiday"],
    "home": ["remote", "wfh"],
    "wfh": ["remote", "home"],
    "hours": ["workday", "time"],
    "workday": ["hours", "time"],
    "software": ["install", "installation"],
    "helpdesk": ["support", "it", "helpdesk"],
    "help": ["support"],
    "contact": ["support", "helpdesk", "email"],
    "email": ["contact", "support"],
    "passwords": ["password"],
    "refunds": ["refund"]
}

STOPWORDS = {
    "how", "many", "do", "i", "have", "to", "a", "is", "long", "does",
    "you", "the", "in", "of", "and", "or", "for", "with", "on", "at",
    "by", "an", "be", "about", "are", "should", "your", "my", "own", "get",
    "employee", "employees", "company", "policy", "handbook", "document",
    "year", "annual", "annually", "receive", "provided", "provides", "provide",
    "expected", "must", "required", "entitled", "days", "paid", "every", "one",
    "person", "personal", "individual"
}


class EmbeddingServiceError(Exception):
    """Custom exception raised when embedding generation fails."""
    pass

class EmbeddingService:
    """
    Handles generating numerical vector embeddings for text chunks using Google Gemini API.
    """
    def __init__(self):
        self.api_key = settings.google_api_key or settings.gemini_api_key
        self.model_name = settings.embedding_model
        self._configured = False
        self.embedding_mode = "MOCK"
        self._warned_mock = False
        self._check_configuration()

    def _check_configuration(self):
        # Refresh configuration values from settings
        self.api_key = settings.google_api_key or settings.gemini_api_key
        self.model_name = settings.embedding_model
        _placeholders = (
            "your-google-api-key-here",
            "your-gemini-api-key-here",
            "",
            None
        )
        
        is_empty_or_placeholder = (self.api_key in _placeholders)
        is_mock_key = False
        if self.api_key:
            api_key_str = str(self.api_key).strip()
            if api_key_str.startswith("mock-") or api_key_str == "mock-key":
                is_mock_key = True

        if not is_empty_or_placeholder and not is_mock_key:
            # We have a valid key for real embeddings
            if not self.api_key.startswith("fail-"):
                genai.configure(api_key=self.api_key)
            self._configured = True
            self.embedding_mode = "REAL"
        else:
            # We don't have a valid key or we have a mock key
            # Allow mock embedding mode only for local demo/testing
            self._configured = True  # Set to True so it doesn't fail initialization
            self.embedding_mode = "MOCK"
            
            if not self._warned_mock:
                logger.warning(
                    "EMBEDDING MOCK MODE ACTIVE: Google API key is missing, empty, or configured as a mock key. "
                    "The system is using local bag-of-words mock embeddings with similarity scaling. "
                    "THIS MODE IS ONLY FOR LOCAL OFFLINE DEMO/TESTING AND IS NOT PRODUCTION-READY."
                )
                self._warned_mock = True

    def _generate_semantic_mock_vector(self, text: str) -> List[float]:
        import re
        import hashlib
        import math
        
        vec = [0.0] * 768
        
        # Check if text has a title (first line)
        lines = text.strip().split("\n")
        title_words = []
        content_words = []
        
        if len(lines) > 1:
            title_words = re.findall(r'\w+', lines[0].lower())
            content_words = re.findall(r'\w+', "\n".join(lines[1:]).lower())
        else:
            content_words = re.findall(r'\w+', text.lower())
            
        def process_words(words_list, weight):
            res = []
            for w in words_list:
                if w in STOPWORDS:
                    continue
                res.extend([w] * weight)
                if w in SYNONYMS:
                    for syn in SYNONYMS[w]:
                        res.extend([syn] * weight)
            return res
            
        # Weight title words 3x
        expanded_words = process_words(title_words, 3) + process_words(content_words, 1)
                
        features = []
        for w in expanded_words:
            features.append(w)
            if len(w) >= 4:
                for i in range(len(w) - 3):
                    features.append(w[i:i+4])
            if len(w) >= 5:
                for i in range(len(w) - 4):
                    features.append(w[i:i+5])

        for f in features:
            idx = int(hashlib.md5(f.encode('utf-8')).hexdigest(), 16) % 768
            vec[idx] += 1.0
            
        norm = math.sqrt(sum(v*v for v in vec))
        if norm > 0:
            vec = [v/norm for v in vec]
        else:
            vec = [1.0 / math.sqrt(768)] * 768
        return vec

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
        if self.api_key and self.api_key.startswith("fail-"):
            raise EmbeddingServiceError("Simulated embedding provider failure.")
 
        # Handle mock embedding generation for testing
        if self.embedding_mode == "MOCK":
            return self._generate_semantic_mock_vector(text)
 
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
        if self.api_key and self.api_key.startswith("fail-"):
            raise EmbeddingServiceError("Simulated embedding provider failure.")
 
        # Handle mock embedding generation for testing
        if self.embedding_mode == "MOCK":
            return [self._generate_semantic_mock_vector(text) for text in texts]
 
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
