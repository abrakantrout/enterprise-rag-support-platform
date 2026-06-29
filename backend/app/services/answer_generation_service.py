import logging
from typing import List, Dict, Any
from app.core.config import settings
from app.services.retrieval_service import RetrievalService, RetrievalError
from app.services.prompt_builder_service import PromptBuilderService
from app.services.gemini_service import GeminiService, GeminiServiceError
from app.services.context_optimizer_service import ContextOptimizerService

logger = logging.getLogger(__name__)

class AnswerGenerationError(Exception):
    """Exception raised when grounded answer generation fails."""
    pass

class AnswerGenerationService:
    """
    Orchestrator service that chains Retrieval, Context Optimization, Prompt Builder, and Gemini services
    to produce grounded answers based on uploaded organization documents.
    """
    def __init__(self):
        self.retrieval_service = RetrievalService()
        self.context_optimizer_service = ContextOptimizerService()
        self.prompt_builder_service = PromptBuilderService()
        self.gemini_service = GeminiService()

    def generate_grounded_answer(
        self,
        question: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Executes the full RAG pipeline:
        Retrieval -> Context Optimization -> Prompt Generation -> Gemini Execution -> Response formatting.
        Enforces tenant isolation and prevents LLM calls when context is empty.
        """
        # 1. Validation
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or contain only whitespace.")
        if not organization_id:
            raise ValueError("Organization ID must be provided.")

        # 2. Retrieve document chunks
        try:
            retrieved_chunks = self.retrieval_service.retrieve_relevant_chunks(
                query=question,
                organization_id=organization_id
            )
        except Exception as e:
            logger.error(f"Retrieval step failed during answer generation: {str(e)}")
            raise AnswerGenerationError(f"Failed to retrieve context documents: {str(e)}")

        # 3. Optimize context
        try:
            optimized_chunks, summary = self.context_optimizer_service.optimize_context(retrieved_chunks)
        except Exception as e:
            logger.error(f"Context optimization failed during answer generation: {str(e)}")
            raise AnswerGenerationError(f"Failed to optimize context: {str(e)}")

        optimized_count = len(optimized_chunks)

        # 4. Optimization: If no chunks retrieved or optimized, bypass Gemini API calls to save costs
        if optimized_count == 0:
            logger.info("No relevant chunks retrieved or kept after optimization. Bypassing Gemini API.")
            return {
                "answer": "I could not find relevant information in the uploaded documents.",
                "sources": [],
                "retrieval_count": 0,
                "model": settings.gemini_model
            }

        # 5. Build the grounded prompt
        try:
            prompt_data = self.prompt_builder_service.build_prompt(
                query=question,
                retrieval_results=optimized_chunks
            )
            prompt_text = prompt_data["prompt"]
            context_sources = prompt_data["context_sources"]
        except Exception as e:
            logger.error(f"Prompt building step failed during answer generation: {str(e)}")
            raise AnswerGenerationError(f"Failed to construct prompt context: {str(e)}")

        # 6. Call Gemini to generate the answer
        try:
            answer_text = self.gemini_service.generate_answer(prompt=prompt_text)
        except Exception as e:
            logger.error(f"Gemini execution step failed during answer generation: {str(e)}")
            raise AnswerGenerationError(f"Failed to generate answer from Gemini provider: {str(e)}")

        # 7. Build the final structured response (excluding sensitive metadata or raw chunks)
        # Map source fields as requested: document, page, chunk_id
        formatted_sources = []
        for src in context_sources:
            formatted_sources.append({
                "document": src.get("filename", "Unknown"),
                "page": src.get("page_number"),
                "chunk_id": src.get("chunk_id")
            })

        return {
            "answer": answer_text,
            "sources": formatted_sources,
            "retrieval_count": optimized_count,
            "model": settings.gemini_model
        }
