import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.database.models import User, Document, DocumentChunk, ChatSession, Message, Feedback
from app.middleware.auth import RoleChecker

logger = logging.getLogger(__name__)
admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# --- Response Schemas ---

class OverviewResponseSchema(BaseModel):
    total_documents: int
    processed_documents: int
    failed_documents: int
    total_chunks: int
    total_chat_sessions: int
    total_messages: int
    total_feedback: int
    thumbs_up_count: int
    thumbs_down_count: int

class RecentQuestionSchema(BaseModel):
    message_id: str
    session_id: str
    content: str
    created_at: datetime

class LowRatedAnswerSchema(BaseModel):
    feedback_id: str
    message_id: str
    session_id: str
    answer: str
    comment: Optional[str]
    score: int
    rating: str
    created_at: datetime


# --- Endpoint Implementations ---

@router.get("/overview", response_model=OverviewResponseSchema)
async def get_overview(
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Returns high-level RAG usage and feedback metrics for the user's organization.
    Restricted to Administrator and Support Agent roles.
    """
    org_id = current_user.organization_id

    total_documents = db.query(Document).filter(
        Document.organization_id == org_id,
        Document.is_deleted == False
    ).count()

    processed_documents = db.query(Document).filter(
        Document.organization_id == org_id,
        Document.status == "Completed",
        Document.is_deleted == False
    ).count()

    failed_documents = db.query(Document).filter(
        Document.organization_id == org_id,
        Document.status == "Failed",
        Document.is_deleted == False
    ).count()

    total_chunks = db.query(DocumentChunk).join(Document).filter(
        Document.organization_id == org_id,
        Document.is_deleted == False
    ).count()

    total_chat_sessions = db.query(ChatSession).filter(
        ChatSession.organization_id == org_id,
        ChatSession.is_deleted == False
    ).count()

    total_messages = db.query(Message).join(ChatSession).filter(
        ChatSession.organization_id == org_id,
        ChatSession.is_deleted == False
    ).count()

    total_feedback = db.query(Feedback).filter(
        Feedback.organization_id == org_id
    ).count()

    thumbs_up_count = db.query(Feedback).filter(
        Feedback.organization_id == org_id,
        (Feedback.rating == "thumbs_up") | (Feedback.score == 1)
    ).count()

    thumbs_down_count = db.query(Feedback).filter(
        Feedback.organization_id == org_id,
        (Feedback.rating == "thumbs_down") | (Feedback.score == -1)
    ).count()

    return {
        "total_documents": total_documents,
        "processed_documents": processed_documents,
        "failed_documents": failed_documents,
        "total_chunks": total_chunks,
        "total_chat_sessions": total_chat_sessions,
        "total_messages": total_messages,
        "total_feedback": total_feedback,
        "thumbs_up_count": thumbs_up_count,
        "thumbs_down_count": thumbs_down_count
    }


@router.get("/recent-questions", response_model=List[RecentQuestionSchema])
async def get_recent_questions(
    limit: int = 10,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Returns recent user questions.
    Restricted to Administrator and Support Agent roles.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit parameter must be between 1 and 50."
        )

    org_id = current_user.organization_id

    questions = db.query(Message).join(ChatSession).filter(
        ChatSession.organization_id == org_id,
        ChatSession.is_deleted == False,
        (Message.role == "user") | (Message.sender == "user")
    ).order_by(Message.created_at.desc()).limit(limit).all()

    return [
        {
            "message_id": q.id,
            "session_id": q.session_id,
            "content": q.content,
            "created_at": q.created_at
        } for q in questions
    ]


@router.get("/low-rated-answers", response_model=List[LowRatedAnswerSchema])
async def get_low_rated_answers(
    limit: int = 10,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Returns recent assistant responses that received thumbs_down feedback.
    Restricted to Administrator and Support Agent roles.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit parameter must be between 1 and 50."
        )

    org_id = current_user.organization_id

    low_rated = db.query(Message, Feedback).join(
        Feedback, Feedback.message_id == Message.id
    ).filter(
        Feedback.organization_id == org_id,
        (Feedback.rating == "thumbs_down") | (Feedback.score == -1)
    ).order_by(Feedback.created_at.desc()).limit(limit).all()

    return [
        {
            "feedback_id": f.id,
            "message_id": m.id,
            "session_id": m.session_id,
            "answer": m.content,
            "comment": f.comment,
            "score": f.score,
            "rating": f.rating or "thumbs_down",
            "created_at": f.created_at
        } for m, f in low_rated
    ]


@router.get("/document-status", response_model=Dict[str, int])
async def get_document_status(
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Returns document counts grouped by processing status.
    Restricted to Administrator and Support Agent roles.
    """
    org_id = current_user.organization_id

    results = db.query(
        Document.status, func.count(Document.id)
    ).filter(
        Document.organization_id == org_id,
        Document.is_deleted == False
    ).group_by(Document.status).all()

    status_counts = {r[0]: r[1] for r in results}

    # Ensure baseline keys are present for predictable client consumption
    for s in ("Processing", "Completed", "Failed"):
        if s not in status_counts:
            status_counts[s] = 0

    return status_counts
