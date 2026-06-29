import logging
import json
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.database.models import User
from app.middleware.auth import RoleChecker
from app.services.answer_generation_service import AnswerGenerationService, AnswerGenerationError

admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# --- Request / Response Schemas ---

class AnswerRequestSchema(BaseModel):
    question: str = Field(..., description="The query/question to answer.")

class AnswerSourceSchema(BaseModel):
    citation_id: str
    document_id: str
    document_name: str
    page_number: Optional[int] = None
    chunk_id: str
    chunk_index: Optional[int] = None
    similarity_score: float
    source_label: str
    text_preview: str
    # Backward compatibility keys
    document: str
    page: Optional[int] = None

class VerificationSchema(BaseModel):
    confidence: float
    verification_status: str
    reason: str
    retrieval_count: int
    average_similarity: float
    citations_count: int

class AnswerResponseSchema(BaseModel):
    question: str
    answer: str
    sources: List[AnswerSourceSchema]
    retrieval_count: int
    model: str
    status: str
    verification: VerificationSchema

# --- Chat Answer Endpoint ---

@router.post("/answer", response_model=AnswerResponseSchema)
async def generate_chat_answer(
    body: AnswerRequestSchema,
    current_user: User = Depends(admin_or_agent)
):
    """
    Generates a grounded, multi-tenant separated answer for the user question.
    Restricted to Administrator and Support Agent roles.
    """
    question_str = body.question
    if not question_str or not question_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question string cannot be empty or contain only whitespace."
        )

    answer_service = AnswerGenerationService()
    try:
        result = answer_service.generate_grounded_answer(
            question=question_str,
            organization_id=current_user.organization_id
        )
        return {
            "question": question_str,
            "answer": result["answer"],
            "sources": result["sources"],
            "retrieval_count": result["retrieval_count"],
            "model": result["model"],
            "status": "success",
            "verification": result["verification"]
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AnswerGenerationError as e:
        # Check if root cause was a Gemini Timeout to return correct detail/message
        # We can map it cleanly or return standard HTTP 500.
        # Let's check: "Gemini timeout should be handled gracefully."
        # If it timed out, return HTTP 500 or HTTP 504 depending on preference, but HTTP 500 is fine as long as details specify.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grounded answer generation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in chat answer endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post("/answer/stream")
async def generate_chat_answer_stream(
    body: AnswerRequestSchema,
    current_user: User = Depends(admin_or_agent)
):
    """
    Streams RAG answer generation process and responses to the client using Server-Sent Events (SSE).
    Restricted to Administrator and Support Agent roles.
    """
    question_str = body.question
    if not question_str or not question_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question string cannot be empty or contain only whitespace."
        )

    # Use the async generator to stream events
    async def event_generator():
        from app.services.retrieval_service import RetrievalService
        from app.services.context_optimizer_service import ContextOptimizerService
        from app.services.prompt_builder_service import PromptBuilderService
        from app.services.gemini_service import GeminiService
        from app.services.citation_service import CitationService
        from app.services.answer_verification_service import AnswerVerificationService

        retrieval_service = RetrievalService()
        context_optimizer_service = ContextOptimizerService()
        prompt_builder_service = PromptBuilderService()
        gemini_service = GeminiService()
        citation_service = CitationService()
        verification_service = AnswerVerificationService()

        try:
            # 1. Retrieval started
            yield f"event: retrieval_started\ndata: {json.dumps({'message': 'Retrieval started'})}\n\n"
            await asyncio.sleep(0.01)
            
            try:
                retrieved_chunks = retrieval_service.retrieve_relevant_chunks(
                    query=question_str,
                    organization_id=current_user.organization_id
                )
            except Exception as e:
                logger.error(f"Retrieval step failed during streaming: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'detail': f'Failed to retrieve context documents: {str(e)}'})}\n\n"
                return
                
            original_count = len(retrieved_chunks)
            yield f"event: retrieval_completed\ndata: {json.dumps({'message': 'Retrieval completed', 'count': original_count})}\n\n"
            await asyncio.sleep(0.01)

            # 2. Context Optimization
            try:
                optimized_chunks, summary = context_optimizer_service.optimize_context(retrieved_chunks)
            except Exception as e:
                logger.error(f"Context optimization failed during streaming: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'detail': f'Failed to optimize context: {str(e)}'})}\n\n"
                return
                
            optimized_count = len(optimized_chunks)
            yield f"event: context_optimized\ndata: {json.dumps({'message': 'Context optimized', 'count': optimized_count})}\n\n"
            await asyncio.sleep(0.01)

            # 3. Refusal check
            if optimized_count == 0:
                refusal_ans = "I could not find relevant information in the uploaded documents."
                yield f"event: answer_started\ndata: {json.dumps({'message': 'Answer generation started'})}\n\n"
                await asyncio.sleep(0.01)
                
                words = refusal_ans.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield f"event: answer_delta\ndata: {json.dumps({'text': chunk})}\n\n"
                    await asyncio.sleep(0.01)
                    
                yield f"event: answer_completed\ndata: {json.dumps({'message': 'Answer generation completed'})}\n\n"
                await asyncio.sleep(0.01)
                
                verification = verification_service.verify_answer(
                    answer=refusal_ans,
                    retrieved_chunks=[],
                    optimization_summary=summary,
                    citation_list=[]
                )
                
                yield f"event: citations_ready\ndata: {json.dumps({'citations': []})}\n\n"
                await asyncio.sleep(0.01)
                
                yield f"event: verification_ready\ndata: {json.dumps({'verification': verification})}\n\n"
                await asyncio.sleep(0.01)
                
                yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
                return

            # 4. Prompt Builder
            try:
                prompt_data = prompt_builder_service.build_prompt(
                    query=question_str,
                    retrieval_results=optimized_chunks
                )
                prompt_text = prompt_data["prompt"]
            except Exception as e:
                logger.error(f"Prompt building failed during streaming: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'detail': f'Failed to construct prompt context: {str(e)}'})}\n\n"
                return
                
            yield f"event: prompt_built\ndata: {json.dumps({'message': 'Prompt built successfully'})}\n\n"
            await asyncio.sleep(0.01)

            # 5. Gemini Generation
            yield f"event: answer_started\ndata: {json.dumps({'message': 'Answer generation started'})}\n\n"
            await asyncio.sleep(0.01)

            full_answer = ""
            try:
                for chunk in gemini_service.generate_answer_stream(prompt=prompt_text):
                    full_answer += chunk
                    yield f"event: answer_delta\ndata: {json.dumps({'text': chunk})}\n\n"
                    await asyncio.sleep(0.005)
            except Exception as e:
                logger.error(f"Gemini streaming failed: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'detail': f'Failed to generate answer from Gemini: {str(e)}'})}\n\n"
                return

            yield f"event: answer_completed\ndata: {json.dumps({'message': 'Answer generation completed'})}\n\n"
            await asyncio.sleep(0.01)

            # 6. Citations
            try:
                citations = citation_service.build_citations(optimized_chunks)
            except Exception as e:
                logger.error(f"Citation building failed during streaming: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'detail': f'Failed to build citations: {str(e)}'})}\n\n"
                return
                
            yield f"event: citations_ready\ndata: {json.dumps({'citations': citations})}\n\n"
            await asyncio.sleep(0.01)

            # 7. Verification
            try:
                verification = verification_service.verify_answer(
                    answer=full_answer,
                    retrieved_chunks=optimized_chunks,
                    optimization_summary=summary,
                    citation_list=citations
                )
            except Exception as e:
                logger.error(f"Answer verification failed during streaming: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'detail': f'Failed to verify answer: {str(e)}'})}\n\n"
                return
                
            yield f"event: verification_ready\ndata: {json.dumps({'verification': verification})}\n\n"
            await asyncio.sleep(0.01)

            # 8. Done
            yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"

        except Exception as e:
            logger.error(f"Unhandled exception in answer stream generator: {str(e)}")
            yield f"event: error\ndata: {json.dumps({'detail': f'An unexpected error occurred during streaming: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
