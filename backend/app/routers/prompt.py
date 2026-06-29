import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.database.models import User
from app.middleware.auth import RoleChecker
from app.services.prompt_builder_service import PromptBuilderService

admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prompt", tags=["prompt"])

# --- Request / Response Schemas ---

class RetrievalMetadataInputSchema(BaseModel):
    filename: str
    organization_id: str

class RetrievalResultInputItemSchema(BaseModel):
    chunk_id: str
    document_id: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    similarity_score: float
    chunk_text: Optional[str] = None
    metadata: RetrievalMetadataInputSchema

class PromptBuildRequestSchema(BaseModel):
    query: str = Field(..., description="The query string to incorporate into the prompt.")
    retrieval_results: List[RetrievalResultInputItemSchema] = Field(
        ..., description="The matching document chunks retrieved from database/indexing."
    )

class ContextSourceSchema(BaseModel):
    chunk_id: str
    document_id: str
    page_number: Optional[int] = None
    filename: str

class PromptBuildResponseSchema(BaseModel):
    query: str
    prompt: str
    context_sources: List[ContextSourceSchema]
    context_chunk_count: int
    estimated_prompt_characters: int
    status: str

# --- Build Prompt Endpoint ---

@router.post("/build", response_model=PromptBuildResponseSchema)
async def build_prompt_endpoint(
    body: PromptBuildRequestSchema,
    current_user: User = Depends(admin_or_agent)
):
    """
    Temporary developer/test endpoint to verify prompt construction.
    Restricted to Administrator and Support Agent roles.
    """
    query_str = body.query
    if not query_str or not query_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty or contain only whitespace."
        )

    # Convert pydantic models to dict for prompt builder service
    results_list = []
    for item in body.retrieval_results:
        item_dict = item.model_dump()
        results_list.append(item_dict)

    prompt_service = PromptBuilderService()
    try:
        output = prompt_service.build_prompt(
            query=query_str,
            retrieval_results=results_list
        )
        return {
            "query": query_str,
            "prompt": output["prompt"],
            "context_sources": output["context_sources"],
            "context_chunk_count": output["context_chunk_count"],
            "estimated_prompt_characters": output["estimated_prompt_characters"],
            "status": "success"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during prompt building: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during prompt construction: {str(e)}"
        )
