import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.database.models import User
from app.middleware.auth import RoleChecker
from app.routers.retrieval import RetrievalResultItemSchema
from app.services.citation_service import CitationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/citations", tags=["citations"])
admin_or_agent = RoleChecker(["Administrator", "Support Agent"])

class CitationResponseSchema(BaseModel):
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

@router.post("/build", response_model=List[CitationResponseSchema])
async def build_citations_endpoint(
    body: List[RetrievalResultItemSchema],
    current_user: User = Depends(admin_or_agent)
):
    """
    Developer debug endpoint that parses retrieval results and builds citations.
    Restricted to Administrator and Support Agent roles.
    """
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
        citation_service = CitationService()
        citations = citation_service.build_citations(input_chunks)
        return citations
    except Exception as e:
        logger.error(f"Citation building failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Citation building failed: {str(e)}"
        )
