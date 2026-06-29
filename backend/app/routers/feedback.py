import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, Message, Feedback
from app.middleware.auth import RoleChecker

logger = logging.getLogger(__name__)
admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

# --- Request / Response Schemas ---

class FeedbackCreateRequestSchema(BaseModel):
    message_id: str
    rating: str = Field(..., description="Must be 'thumbs_up' or 'thumbs_down'")
    comment: Optional[str] = None

class FeedbackResponseSchema(BaseModel):
    id: str
    message_id: str
    user_id: str
    organization_id: str
    rating: str
    comment: Optional[str]
    created_at: datetime


# --- Endpoint Implementations ---

@router.post("", response_model=FeedbackResponseSchema, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackCreateRequestSchema,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Submits feedback for an assistant message.
    Restricted to Administrator and Support Agent roles.
    """
    # 1. Validate rating value
    if body.rating not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid rating. Must be 'thumbs_up' or 'thumbs_down'."
        )

    # 2. Retrieve referenced message
    message = db.query(Message).filter(Message.id == body.message_id).first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referenced message not found."
        )

    # 3. Cross-organization access validation
    session = message.session
    if not session or session.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized. Message belongs to another organization."
        )

    # 4. Reject feedback on user questions
    role_val = message.role or message.sender
    if role_val == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit feedback on a user message."
        )

    # Map rating to score (thumbs_up -> 1, thumbs_down -> -1)
    score_val = 1 if body.rating == "thumbs_up" else -1

    # 5. Check duplicate feedback by same user on same message
    existing_feedback = db.query(Feedback).filter(
        Feedback.message_id == body.message_id,
        Feedback.user_id == current_user.id
    ).first()

    if existing_feedback:
        # Update existing feedback (override behavior)
        existing_feedback.rating = body.rating
        existing_feedback.score = score_val
        existing_feedback.comment = body.comment
        existing_feedback.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_feedback)
        return {
            "id": existing_feedback.id,
            "message_id": existing_feedback.message_id,
            "user_id": existing_feedback.user_id,
            "organization_id": existing_feedback.organization_id,
            "rating": existing_feedback.rating,
            "comment": existing_feedback.comment,
            "created_at": existing_feedback.created_at
        }

    # Create new feedback
    new_feedback = Feedback(
        message_id=body.message_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        score=score_val,
        rating=body.rating,
        comment=body.comment
    )
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    return {
        "id": new_feedback.id,
        "message_id": new_feedback.message_id,
        "user_id": new_feedback.user_id,
        "organization_id": new_feedback.organization_id,
        "rating": new_feedback.rating,
        "comment": new_feedback.comment,
        "created_at": new_feedback.created_at
    }


@router.get("", response_model=List[FeedbackResponseSchema])
async def list_feedback(
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Lists feedback submitted in the current user's organization.
    Restricted to Administrator and Support Agent roles.
    """
    feedbacks = db.query(Feedback).filter(
        Feedback.organization_id == current_user.organization_id
    ).order_by(Feedback.created_at.desc()).all()

    return [
        {
            "id": f.id,
            "message_id": f.message_id,
            "user_id": f.user_id,
            "organization_id": f.organization_id,
            "rating": f.rating or ("thumbs_up" if f.score == 1 else "thumbs_down"),
            "comment": f.comment,
            "created_at": f.created_at
        } for f in feedbacks
    ]


@router.get("/{feedback_id}", response_model=FeedbackResponseSchema)
async def get_feedback_detail(
    feedback_id: str,
    current_user: User = Depends(admin_or_agent),
    db: Session = Depends(get_db)
):
    """
    Retrieves feedback details.
    Restricted to user's organization.
    """
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found."
        )

    if feedback.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to feedback of another organization."
        )

    return {
        "id": feedback.id,
        "message_id": feedback.message_id,
        "user_id": feedback.user_id,
        "organization_id": feedback.organization_id,
        "rating": feedback.rating or ("thumbs_up" if feedback.score == 1 else "thumbs_down"),
        "comment": feedback.comment,
        "created_at": feedback.created_at
    }
