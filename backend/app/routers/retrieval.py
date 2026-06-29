import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.database.models import User
from app.middleware.auth import RoleChecker
from app.services.retrieval_service import RetrievalService, RetrievalError

admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])

# --- Request / Response Schemas ---

class RetrievalRequestSchema(BaseModel):
    query: str = Field(..., description="The query string to search for.")

class RetrievalMetadataSchema(BaseModel):
    filename: str
    organization_id: str

class RetrievalResultItemSchema(BaseModel):
    chunk_id: str
    document_id: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    similarity_score: float
    chunk_text: str
    metadata: RetrievalMetadataSchema

class RetrievalResponseSchema(BaseModel):
    query: str
    results: List[RetrievalResultItemSchema]


# --- Search Endpoint ---

@router.post("/search", response_model=RetrievalResponseSchema)
async def semantic_search(
    body: RetrievalRequestSchema,
    current_user: User = Depends(admin_or_agent)
):
    """
    Retrieves the Top-K matching document chunks for a given query.
    Restricted to Administrators and Support Agents. Filters results strictly
    by the user's organization to prevent cross-tenant data leaks.
    """
    query_str = body.query
    if not query_str or not query_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty or contain only whitespace."
        )

    retrieval_service = RetrievalService()
    try:
        results = retrieval_service.retrieve_relevant_chunks(
            query=query_str,
            organization_id=current_user.organization_id
        )
        return {
            "query": query_str,
            "results": results
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RetrievalError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic retrieval failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during semantic search: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during search: {str(e)}"
        )


# --- Debug Optimization Endpoint ---

class OptimizationSummarySchema(BaseModel):
    original_chunks: int
    optimized_chunks: int
    duplicates_removed: int
    near_duplicates_removed: int
    discarded_empty: int
    estimated_characters: int

class OptimizeResponseSchema(BaseModel):
    optimized_chunks: List[RetrievalResultItemSchema]
    optimization_summary: OptimizationSummarySchema

@router.post("/optimize", response_model=OptimizeResponseSchema)
async def optimize_retrieval_endpoint(
    body: List[RetrievalResultItemSchema],
    current_user: User = Depends(admin_or_agent)
):
    """
    Developer debug endpoint that runs context optimization over a set of input chunks.
    Restricted to Administrators and Support Agents.
    """
    from app.services.context_optimizer_service import ContextOptimizerService
    optimizer = ContextOptimizerService()
    
    # Convert input pydantic schemas to standard dicts
    input_chunks = []
    for item in body:
        input_chunks.append({
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "page_number": item.page_number,
            "chunk_index": item.chunk_index,
            "similarity_score": item.similarity_score,
            "chunk_text": item.chunk_text,
            "metadata": {
                "filename": item.metadata.filename,
                "organization_id": item.metadata.organization_id
            }
        })
        
    try:
        optimized, summary = optimizer.optimize_context(input_chunks)
        return {
            "optimized_chunks": optimized,
            "optimization_summary": summary
        }
    except Exception as e:
        logger.error(f"Context optimization failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Context optimization failed: {str(e)}"
        )
