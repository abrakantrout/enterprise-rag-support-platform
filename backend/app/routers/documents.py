import os
import uuid
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.connection import get_db
from app.database.models import Document, User, DocumentVersion, DocumentChunk
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


# --- Chunks Persistence Schemas & Endpoint ---
class ChunksPersistenceResponseSchema(BaseModel):
    document_id: str
    chunks_created: int
    average_chunk_size: float
    largest_chunk: int
    smallest_chunk: int
    status: str
    message: str

@router.post("/{document_id}/chunks", response_model=ChunksPersistenceResponseSchema)
async def persist_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Validates document, checks physical file, extracts text, generates chunks,
    deletes any existing chunks for this document, and stores them in PostgreSQL.
    """
    # 1. Validate Document is Active & Not Soft-deleted
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
            detail="Physical file was missing from storage disk."
        )

    # 3. Extract Pages Text using the existing service
    try:
        from app.services.document_extraction import extract_text_from_file
        pages = extract_text_from_file(physical_path, doc.file_type)
    except Exception as e:
        logger.error(f"Text extraction failed during chunks persistence for document {document_id}: {str(e)}")
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction failed: {str(e)}"
        )

    # 4. Generate Semantic Chunks using the existing service
    try:
        chunks = chunk_document(
            doc_id=doc.id,
            pages=pages,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            chunk_max_size=settings.chunk_max_size
        )
    except ChunkingValidationError as e:
        logger.error(f"Chunking validation failed during persistence for document {document_id}: {str(e)}")
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunking validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error chunking document {document_id} during persistence: {str(e)}")
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred during text chunking"
        )

    if not chunks:
        doc.status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document text produced zero chunks."
        )

    # 5. Delete existing chunks for this document if any exist (Idempotency)
    try:
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.flush()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error deleting existing chunks for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database failure preparing table for new chunks"
        )

    # 6. Retrieve active version or create a default version
    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id,
        DocumentVersion.is_active == True
    ).first()

    if not version:
        try:
            version = DocumentVersion(
                document_id=document_id,
                version="1.0",
                is_active=True
            )
            db.add(version)
            db.flush()
        except Exception as e:
            db.rollback()
            logger.error(f"Database error creating document version: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database failure creating document version"
            )

    # 7. Store new chunks in PostgreSQL
    db_chunks = []
    try:
        for chunk in chunks:
            db_chunk = DocumentChunk(
                version_id=version.id,
                document_id=document_id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk["page_number"],
                chunk_text=chunk["text"],
                character_count=chunk["character_count"],
                start_offset=chunk["start_offset"],
                end_offset=chunk["end_offset"]
            )
            db_chunks.append(db_chunk)
        db.add_all(db_chunks)

        # 8. Update document status appropriately
        doc.status = "Completed"
        doc.extracted_at = datetime.utcnow()
        doc.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Persisted {len(chunks)} chunks for document {document_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error persisting chunks for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database failure persisting document chunks"
        )

    # 9. Return a persistence summary
    number_of_chunks = len(chunks)
    sizes = [c["character_count"] for c in chunks]
    average_chunk_size = sum(sizes) / number_of_chunks
    largest_chunk = max(sizes)
    smallest_chunk = min(sizes)

    return {
        "document_id": document_id,
        "chunks_created": number_of_chunks,
        "average_chunk_size": average_chunk_size,
        "largest_chunk": largest_chunk,
        "smallest_chunk": smallest_chunk,
        "status": "Completed",
        "message": f"Successfully persisted {number_of_chunks} document chunks into PostgreSQL."
    }


# --- Embeddings Generation Schemas & Endpoint ---
class DocumentEmbeddingsResponseSchema(BaseModel):
    document_id: str
    total_chunks: int
    embeddings_generated: int
    failed_chunks: int
    embedding_model: str
    status: str
    message: str

@router.post("/{document_id}/embeddings", response_model=DocumentEmbeddingsResponseSchema)
async def generate_document_embeddings(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Validates document and chunks, checks API key presence, generates embeddings
    for all chunks using the EmbeddingService, and updates their status in PostgreSQL.
    """
    # 1. Validate Document is Active & Not Soft-deleted
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

    # 2. Retrieve document chunks
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index.asc()).all()

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no chunks. Please parse and chunk the document first."
        )

    # 3. Validate that no chunk is empty
    for chunk in chunks:
        if not chunk.chunk_text or not chunk.chunk_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more document chunks contain empty text."
            )

    # 4. Check for Google API key configuration
    if not settings.google_api_key or settings.google_api_key in ("your-google-api-key-here", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google API key is missing or not configured."
        )

    # 5. Initialize embedding service and generate embeddings
    from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
    embed_service = EmbeddingService()

    texts = [chunk.chunk_text for chunk in chunks]
    
    try:
        # Generate embeddings in batch
        embeddings = embed_service.generate_embeddings(texts)
        
        # 6. Mark each chunk embedding status as Completed
        for chunk in chunks:
            chunk.embedding_status = "Completed"
            chunk.embedding_model = settings.embedding_model
            chunk.embedded_at = datetime.utcnow()
            
        db.commit()
        
        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "embeddings_generated": len(embeddings),
            "failed_chunks": 0,
            "embedding_model": settings.embedding_model,
            "status": "Completed",
            "message": f"Successfully generated and persisted {len(embeddings)} embeddings metadata in PostgreSQL."
        }
    except EmbeddingServiceError as e:
        # Mark chunks as Failed
        for chunk in chunks:
            chunk.embedding_status = "Failed"
            chunk.embedding_model = settings.embedding_model
            chunk.embedded_at = datetime.utcnow()
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}"
        )
    except Exception as e:
        # General unexpected errors
        for chunk in chunks:
            chunk.embedding_status = "Failed"
            chunk.embedding_model = settings.embedding_model
            chunk.embedded_at = datetime.utcnow()
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during embedding generation: {str(e)}"
        )


# --- Vector Indexing Schemas & Endpoint ---
class DocumentIndexingResponseSchema(BaseModel):
    document_id: str
    chunks_indexed: int
    failed_chunks: int
    collection_name: str
    status: str
    message: str

@router.post("/{document_id}/index", response_model=DocumentIndexingResponseSchema)
async def index_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_agent)
):
    """
    Validates document, chunks, and embedding status, retrieves embeddings,
    and indexes document chunk metadata and vectors into ChromaDB.
    """
    # 1. Validate Document is Active & Not Soft-deleted
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

    # 2. Retrieve document chunks
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index.asc()).all()

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no chunks. Please chunk the document first."
        )

    # 3. Validate that embeddings are completed for all chunks
    for chunk in chunks:
        if chunk.embedding_status != "Completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more chunks do not have completed embeddings. Please run embeddings first."
            )

    # 4. Generate/Retrieve the embeddings vectors
    from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
    embed_service = EmbeddingService()
    
    texts = [c.chunk_text for c in chunks]
    try:
        embeddings = embed_service.generate_embeddings(texts)
    except EmbeddingServiceError as e:
        for chunk in chunks:
            chunk.indexed_status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve embeddings vectors: {str(e)}"
        )

    # 5. Build chunks payload for ChromaDB indexing
    chunks_data = []
    for chunk, embedding in zip(chunks, embeddings):
        # Format metadata dictionary with strict value types (no None values allowed in Chroma)
        metadata = {
            "document_id": document_id,
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "organization_id": doc.organization_id,
            "embedding_model": chunk.embedding_model or settings.embedding_model,
            "created_at": chunk.created_at.isoformat() if chunk.created_at else datetime.utcnow().isoformat()
        }
        if chunk.page_number is not None:
            metadata["page_number"] = chunk.page_number
        if doc.filename:
            metadata["filename"] = doc.filename
        if doc.file_type:
            metadata["file_type"] = doc.file_type

        chunks_data.append({
            "chunk_id": chunk.id,
            "text": chunk.chunk_text,
            "embedding": embedding,
            "metadata": metadata
        })

    # 6. Index into ChromaDB
    from app.services.vector_indexing_service import VectorIndexingService, VectorIndexingError
    indexing_service = VectorIndexingService()

    try:
        indexed_count = indexing_service.index_chunks(document_id, chunks_data)
        
        # 7. Update chunk status in PostgreSQL database
        for chunk in chunks:
            chunk.indexed_status = "Completed"
            chunk.indexed_at = datetime.utcnow()
            chunk.vector_id = chunk.id
            
        db.commit()
        
        return {
            "document_id": document_id,
            "chunks_indexed": indexed_count,
            "failed_chunks": 0,
            "collection_name": settings.chroma_collection_name,
            "status": "Completed",
            "message": f"Successfully indexed {indexed_count} chunks into ChromaDB."
        }
    except VectorIndexingError as e:
        for chunk in chunks:
            chunk.indexed_status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector indexing failed: {str(e)}"
        )
    except Exception as e:
        for chunk in chunks:
            chunk.indexed_status = "Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during indexing: {str(e)}"
        )
