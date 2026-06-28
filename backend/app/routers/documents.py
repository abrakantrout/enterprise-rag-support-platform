import os
import uuid
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.connection import get_db
from app.database.models import Document, User
from app.middleware.auth import get_current_user, RoleChecker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents Management"])

# --- Role Authorizations ---
admin_or_agent = RoleChecker(["Administrator", "Support Agent"])
admin_only = RoleChecker(["Administrator"])

# --- Supported Extensions & MIME Types ---
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}
EXTENSION_TO_MIME = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}

# --- Pydantic Schemas ---
from pydantic import BaseModel

class DocumentResponseSchema(BaseModel):
    id: str
    filename: str
    stored_path: str
    file_type: str
    file_size: int
    status: str
    visibility: str
    category: Optional[str]
    uploader_id: str
    organization_id: str
    extracted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaginationMetadataSchema(BaseModel):
    total_items: int
    page_size: int
    current_page: int
    total_pages: int

class DocumentListResponseSchema(BaseModel):
    items: list[DocumentResponseSchema]
    pagination: PaginationMetadataSchema

# --- Endpoints ---

@router.post("/upload", response_model=DocumentResponseSchema, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    visibility: str = Form("public"),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Allows authenticated Administrators and Support Agents to upload documents (.pdf, .txt, .docx)
    up to 25MB, store them on disk, and write metadata to PostgreSQL.
    """
    # 1. Validate File Presence
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded or file field is missing"
        )

    # 2. Validate Extension
    filename = file.filename
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Only .pdf, .txt, and .docx are allowed."
        )

    # 3. Validate MIME type matches Extension (Strict Content-Type verification)
    content_type = file.content_type
    expected_mime = EXTENSION_TO_MIME.get(ext)
    if content_type != expected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type '{content_type}' does not match expected MIME type '{expected_mime}' for extension '{ext}'."
        )

    # 4. Read File Content & Validate Size
    try:
        content = await file.read()
        file_size = len(content)
    except Exception as e:
        logger.error(f"Failed to read upload file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error reading file contents"
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty files are not allowed"
        )

    max_size = 25 * 1024 * 1024  # 25MB in bytes
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the maximum limit of 25MB. Detected: {file_size} bytes."
        )

    # 5. Save File Safely
    stored_filename = f"{uuid.uuid4()}{ext}"
    uploads_directory = settings.uploads_dir
    os.makedirs(uploads_directory, exist_ok=True)
    stored_path = os.path.join(uploads_directory, stored_filename)

    try:
        with open(stored_path, "wb") as buffer:
            buffer.write(content)
    except Exception as e:
        logger.error(f"Error persisting uploaded file to disk: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store raw file on server storage"
        )

    # Store relative path in database to keep references clean
    relative_stored_path = os.path.join("uploads", stored_filename).replace("\\", "/")

    # 6. Save Metadata in PostgreSQL
    new_doc = Document(
        filename=filename,
        stored_path=relative_stored_path,
        file_type=ext.lstrip("."),
        file_size=file_size,
        status="Processing",
        visibility=visibility,
        category=category,
        uploader_id=current_user.id,
        organization_id=current_user.organization_id
    )

    try:
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        logger.info(f"Successfully uploaded document {new_doc.id} ({filename}) by user {current_user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error saving document metadata: {str(e)}")
        # Attempt disk cleanup
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist document metadata in database"
        )

    return new_doc

@router.get("", response_model=DocumentListResponseSchema)
def list_documents(
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    List uploaded metadata records with pagination and optional status filter.
    Visible only to Administrator and Support Agent roles.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 20
    if size > 100:
        size = 100

    query = db.query(Document).filter(
        Document.is_deleted == False,
        Document.organization_id == current_user.organization_id
    )

    if status:
        query = query.filter(Document.status == status)

    total_items = query.count()
    total_pages = (total_items + size - 1) // size if total_items > 0 else 1

    offset = (page - 1) * size
    items = query.order_by(Document.created_at.desc()).offset(offset).limit(size).all()

    return {
        "items": items,
        "pagination": {
            "total_items": total_items,
            "page_size": size,
            "current_page": page,
            "total_pages": total_pages
        }
    }

@router.get("/{document_id}", response_model=DocumentResponseSchema)
def get_document_details(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Retrieve metadata for a specific document by UUID.
    Visible only to Administrator and Support Agent roles.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.is_deleted == False,
        Document.organization_id == current_user.organization_id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return doc

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """
    Soft-deletes document metadata record and removes the physical file from server disk.
    Accessible only to Administrator role.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.is_deleted == False,
        Document.organization_id == current_user.organization_id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Resolve physical disk path to delete the file
    # If the stored_path is stored relative, e.g. "uploads/abc.pdf", we join it with workdir
    filename_part = os.path.basename(doc.stored_path)
    physical_path = os.path.join(settings.uploads_dir, filename_part)

    # Perform soft-delete in database
    doc.is_deleted = True
    doc.updated_at = datetime.utcnow()

    try:
        db.commit()
        logger.info(f"Soft-deleted document metadata for {document_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error soft-deleting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update database metadata during deletion"
        )

    # Remove physical file
    try:
        if os.path.exists(physical_path):
            os.remove(physical_path)
            logger.info(f"Successfully deleted physical file at {physical_path}")
        else:
            logger.warning(f"Physical file for document {document_id} was missing at {physical_path}")
    except Exception as e:
        logger.error(f"Failed to delete physical file {physical_path}: {str(e)}")
        # We don't fail the request since metadata was successfully updated, but we log the issue.

    return {"message": "Document successfully deleted"}


# --- Extraction Models & Endpoint ---
from app.services.document_extraction import extract_text_from_file, DocumentExtractionError

class ExtractionResponseSchema(BaseModel):
    page_count: int
    character_count: int
    preview: str
    extraction_status: str

@router.post("/{document_id}/extract", response_model=ExtractionResponseSchema)
async def extract_document_text(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Validates document existence, checks local disk storage, triggers
    text extraction loader, updates metadata, and returns extraction summary.
    """
    # 1. Validate Document is Active
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.is_deleted == False,
        Document.organization_id == current_user.organization_id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # 2. Locate File on Disk
    filename_part = os.path.basename(doc.stored_path)
    physical_path = os.path.join(settings.uploads_dir, filename_part)

    if not os.path.exists(physical_path):
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physical file was missing from storage disk."
        )

    # 3. Process Text Extraction
    try:
        pages = extract_text_from_file(physical_path, doc.file_type)
    except DocumentExtractionError as e:
        logger.error(f"Text extraction error for document {document_id}: {str(e)}")
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected extraction error for document {document_id}: {str(e)}")
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred during text extraction"
        )

    # 4. Generate Metadata Metrics
    page_count = len(pages)
    full_text = "\n".join(p["page_text"] for p in pages)
    character_count = len(full_text)
    preview = full_text[:500]

    # 5. Save Status & Timestamp
    doc.status = "Completed"
    doc.extracted_at = datetime.utcnow()
    doc.updated_at = datetime.utcnow()

    try:
        db.commit()
        logger.info(f"Text extraction completed for document {document_id}. Characters: {character_count}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error writing extraction timestamp for {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save extraction metrics to database"
        )

    return {
        "page_count": page_count,
        "character_count": character_count,
        "preview": preview,
        "extraction_status": "Completed"
    }


# --- Chunking Models & Endpoint ---
from app.services.chunking_service import chunk_document, ChunkingValidationError

class ChunkingResponseSchema(BaseModel):
    number_of_chunks: int
    average_chunk_size: float
    largest_chunk: int
    smallest_chunk: int
    first_chunk_preview: str

@router.post("/{document_id}/chunk", response_model=ChunkingResponseSchema)
async def chunk_document_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Loads document metadata, parses page content (if needed), runs the semantic
    text chunking engine, and returns summary metrics of generated chunks.
    """
    # 1. Validate Document is Active
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.is_deleted == False,
        Document.organization_id == current_user.organization_id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # 2. Resolve Physical Path
    filename_part = os.path.basename(doc.stored_path)
    physical_path = os.path.join(settings.uploads_dir, filename_part)

    if not os.path.exists(physical_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file was missing from storage disk."
        )

    # 3. Extract Pages Text
    try:
        from app.services.document_extraction import extract_text_from_file
        pages = extract_text_from_file(physical_path, doc.file_type)
    except Exception as e:
        logger.error(f"Text extraction failed during chunking workflow for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Text extraction failed for chunking: {str(e)}"
        )

    # 4. Generate Semantic Chunks
    try:
        chunks = chunk_document(
            doc_id=doc.id,
            pages=pages,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            chunk_max_size=settings.chunk_max_size
        )
    except ChunkingValidationError as e:
        logger.error(f"Chunking validation failed for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunking validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error chunking document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred during text chunking"
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document text produced zero chunks."
        )

    # 5. Compile Summary Statistics
    number_of_chunks = len(chunks)
    sizes = [c["character_count"] for c in chunks]
    average_chunk_size = sum(sizes) / number_of_chunks
    largest_chunk = max(sizes)
    smallest_chunk = min(sizes)
    first_chunk_preview = chunks[0]["text"][:200]

    return {
        "number_of_chunks": number_of_chunks,
        "average_chunk_size": average_chunk_size,
        "largest_chunk": largest_chunk,
        "smallest_chunk": smallest_chunk,
        "first_chunk_preview": first_chunk_preview
    }
