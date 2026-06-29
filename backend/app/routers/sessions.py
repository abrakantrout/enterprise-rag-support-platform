import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, ChatSession, Message
from app.middleware.auth import RoleChecker
from app.services.answer_generation_service import AnswerGenerationService
from app.routers.answer import AnswerRequestSchema, AnswerSourceSchema, VerificationSchema

logger = logging.getLogger(__name__)
admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

router = APIRouter(prefix="/api/v1/chat/sessions", tags=["chat-sessions"])

# --- Response Schemas ---

class SessionCreateResponseSchema(BaseModel):
    session_id: str
    organization_id: str
    user_id: Optional[str]
    created_at: datetime

class SessionListItemSchema(BaseModel):
    session_id: str
    organization_id: str
    user_id: Optional[str]
    created_at: datetime

class SessionMessageResponseSchema(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[List[AnswerSourceSchema]] = None
    verification: Optional[VerificationSchema] = None
    created_at: datetime

class SessionDetailResponseSchema(BaseModel):
    session_id: str
    organization_id: str
    user_id: Optional[str]
    created_at: datetime
    messages: List[SessionMessageResponseSchema]

class SessionAnswerResponseSchema(BaseModel):
    question: str
    answer: str
    sources: List[AnswerSourceSchema]
    retrieval_count: int
    model: str
    status: str
    verification: VerificationSchema


# --- Endpoint Implementations ---

@router.post("", response_model=SessionCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Creates a new persistent chat session.
    Restricted to Administrator and Support Agent roles.
    """
    session = ChatSession(
        organization_id=current_user.organization_id,
        user_id=current_user.id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "session_id": session.id,
        "organization_id": session.organization_id,
        "user_id": session.user_id,
        "created_at": session.created_at
    }


@router.get("", response_model=List[SessionListItemSchema])
async def list_chat_sessions(
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Lists all non-deleted sessions belonging to the current user's organization.
    Restricted to Administrator and Support Agent roles.
    """
    sessions = db.query(ChatSession).filter(
        ChatSession.organization_id == current_user.organization_id,
        ChatSession.is_deleted == False
    ).order_by(ChatSession.created_at.desc()).all()

    return [
        {
            "session_id": s.id,
            "organization_id": s.organization_id,
            "user_id": s.user_id,
            "created_at": s.created_at
        } for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionDetailResponseSchema)
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Retrieves the detailed session structure and message history.
    Restricted to user's organization.
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.is_deleted == False
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or has been deleted."
        )

    if session.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to chat session of another organization."
        )

    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()

    formatted_messages = []
    for m in messages:
        # Resolve role mapping (role field is nullable; fallback to sender)
        role_val = m.role or m.sender or "user"
        formatted_messages.append({
            "id": m.id,
            "role": role_val,
            "content": m.content,
            "citations": m.citations or [],
            "verification": m.verification,
            "created_at": m.created_at
        })

    return {
        "session_id": session.id,
        "organization_id": session.organization_id,
        "user_id": session.user_id,
        "created_at": session.created_at,
        "messages": formatted_messages
    }


@router.delete("/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Soft-deletes a chat session.
    Restricted to user's organization.
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.is_deleted == False
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or already deleted."
        )

    if session.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to chat session of another organization."
        )

    session.is_deleted = True
    db.commit()
    return {"message": "Chat session deleted successfully."}


@router.post("/{session_id}/answer", response_model=SessionAnswerResponseSchema)
async def generate_session_answer(
    session_id: str,
    body: AnswerRequestSchema,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Executes answer generation pipeline and records messages to history.
    Restricted to user's organization.
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.is_deleted == False
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or has been deleted."
        )

    if session.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to chat session of another organization."
        )

    question_str = body.question
    if not question_str or not question_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question string cannot be empty or contain only whitespace."
        )

    # 1. Save user question message
    user_msg = Message(
        session_id=session.id,
        sender="user",
        role="user",
        content=question_str,
        citations=None,
        verification=None
    )
    db.add(user_msg)
    db.commit()

    # 2. Execute RAG answer generator
    answer_service = AnswerGenerationService()
    try:
        result = answer_service.generate_grounded_answer(
            question=question_str,
            organization_id=current_user.organization_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Grounded answer generation failed in session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grounded answer generation failed: {str(e)}"
        )

    # 3. Save assistant answer message
    assistant_msg = Message(
        session_id=session.id,
        sender="assistant",
        role="assistant",
        content=result["answer"],
        citations=result["sources"],
        verification=result["verification"]
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "question": question_str,
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieval_count": result["retrieval_count"],
        "model": result["model"],
        "status": "success",
        "verification": result["verification"]
    }
