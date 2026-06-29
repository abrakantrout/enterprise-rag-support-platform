import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
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

class AnswerResponseSchema(BaseModel):
    question: str
    answer: str
    sources: List[AnswerSourceSchema]
    retrieval_count: int
    model: str
    status: str

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
            "status": "success"
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
