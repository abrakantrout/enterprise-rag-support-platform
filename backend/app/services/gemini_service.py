import logging
import time
from typing import Optional
import google.generativeai as genai
import httpx
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted, InvalidArgument
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiServiceError(Exception):
    """Base exception for Gemini service failures."""
    pass

class GeminiTimeoutError(GeminiServiceError):
    """Exception raised when a request to Gemini times out."""
    pass

class GeminiService:
    """
    Handles communications with the Google Gemini API.
    """
    def __init__(self):
        self.api_key = settings.google_api_key or settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.temperature = settings.temperature
        self.max_output_tokens = settings.max_output_tokens
        self.timeout_seconds = settings.request_timeout_seconds
        self._configured = False
        self._check_configuration()

    def _check_configuration(self):
        self.api_key = settings.google_api_key or settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.temperature = settings.temperature
        self.max_output_tokens = settings.max_output_tokens
        self.timeout_seconds = settings.request_timeout_seconds

        if self.api_key and self.api_key not in ("your-google-api-key-here", "your-gemini-api-key-here", ""):
            if not self.api_key.startswith("mock-") and not self.api_key.startswith("fail-") and not self.api_key.startswith("timeout-"):
                genai.configure(api_key=self.api_key)
            self._configured = True
        else:
            self._configured = False

    def generate_answer(self, prompt: str) -> str:
        """
        Sends the prompt to Gemini and retrieves the generated answer.
        Implements retries for transient errors (rate limits/network issues) and timeouts.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        self._check_configuration()
        if not self._configured:
            raise GeminiServiceError("Google/Gemini API key is missing or not configured.")

        # Handle simulated failure modes for testing
        if self.api_key.startswith("fail-"):
            raise GeminiServiceError("Simulated Gemini API provider failure.")
        if self.api_key.startswith("timeout-"):
            raise GeminiTimeoutError(f"Simulated Gemini request timeout after {self.timeout_seconds} seconds.")

        # Handle mock output for testing
        if self.api_key.startswith("mock-") or self.api_key == "mock-key":
            if "No relevant context found." in prompt:
                return "I could not find relevant information in the uploaded documents."
            
            # Extract document and query fields to make response look realistic
            return (
                "Based on the provided documents, the refund policy allows you to request a full refund "
                "within 30 days of purchase. Shipping fees are non-refundable. "
                "[Document: RefundPolicy.pdf, Page: 1, Chunk ID: c1]"
            )

        # Real API Execution with Transient Error Retries
        model = genai.GenerativeModel(model_name=self.model_name)
        generation_config = genai.types.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens
        )

        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options={"timeout": float(self.timeout_seconds)}
                )
                if not response or not response.text:
                    raise GeminiServiceError("Gemini returned an empty or invalid response.")
                return response.text
            except (ResourceExhausted, httpx.NetworkError) as e:
                if attempt == max_retries - 1:
                    logger.error(f"Gemini call failed after {max_retries} attempts due to transient error: {str(e)}")
                    raise GeminiServiceError(f"Gemini API rate limit or network failure: {str(e)}")
                logger.warning(f"Transient error on attempt {attempt + 1}: {str(e)}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2.0
            except (httpx.TimeoutException, TimeoutError) as e:
                logger.error(f"Gemini API call timed out: {str(e)}")
                raise GeminiTimeoutError(f"Gemini API call timed out: {str(e)}")
            except GoogleAPICallError as e:
                logger.error(f"Gemini API call error: {str(e)}")
                raise GeminiServiceError(f"Gemini API call error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error during Gemini generation: {str(e)}")
                raise GeminiServiceError(f"Unexpected error: {str(e)}")

        raise GeminiServiceError("Failed to generate answer from Gemini.")

    def generate_answer_stream(self, prompt: str):
        """
        Sends the prompt to Gemini and yields text chunks as they arrive.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        self._check_configuration()
        if not self._configured:
            raise GeminiServiceError("Google/Gemini API key is missing or not configured.")

        # Handle simulated failure modes for testing
        if self.api_key.startswith("fail-"):
            raise GeminiServiceError("Simulated Gemini API provider failure.")
        if self.api_key.startswith("timeout-"):
            raise GeminiTimeoutError(f"Simulated Gemini request timeout after {self.timeout_seconds} seconds.")

        # Handle mock output for testing
        if self.api_key.startswith("mock-") or self.api_key == "mock-key":
            if "No relevant context found." in prompt:
                mock_text = "I could not find relevant information in the uploaded documents."
            else:
                mock_text = (
                    "Based on the provided documents, the refund policy allows you to request a full refund "
                    "within 30 days of purchase. Shipping fees are non-refundable. "
                    "[Document: RefundPolicy.pdf, Page: 1, Chunk ID: c1]"
                )
            
            # Yield in small chunks simulating network streaming
            words = mock_text.split(" ")
            for i, word in enumerate(words):
                chunk_to_yield = word + (" " if i < len(words) - 1 else "")
                yield chunk_to_yield
                time.sleep(0.01)
            return

        # Real API Execution with streaming
        model = genai.GenerativeModel(model_name=self.model_name)
        generation_config = genai.types.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens
        )

        try:
            response = model.generate_content_stream(
                prompt,
                generation_config=generation_config,
                request_options={"timeout": float(self.timeout_seconds)}
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except (httpx.TimeoutException, TimeoutError) as e:
            logger.error(f"Gemini API call timed out: {str(e)}")
            raise GeminiTimeoutError(f"Gemini API call timed out: {str(e)}")
        except Exception as e:
            logger.error(f"Error during Gemini stream generation: {str(e)}")
            raise GeminiServiceError(f"Streaming failed: {str(e)}")
