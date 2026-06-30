from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.database.chroma import check_chroma_connection
from app.database.connection import check_db_connection

router = APIRouter()


@router.get("/health", tags=["System Diagnostics"])
def get_health_status() -> dict:
    """
    Performs system diagnostics checking the status of database connections.

    Returns:
        dict: Detailed health diagnostics report.
    """
    db_ok = check_db_connection()
    chroma_ok = check_chroma_connection()

    # Get embedding mode diagnostics safely
    try:
        from app.services.embedding_service import EmbeddingService
        embed_service = EmbeddingService()
        embedding_mode = embed_service.embedding_mode
        embedding_model = embed_service.model_name
    except Exception:
        embedding_mode = "UNKNOWN"
        embedding_model = "UNKNOWN"

    # The application status is unhealthy if any critical system is offline
    overall_status = "healthy" if (db_ok and chroma_ok) else "unhealthy"

    return {
        "status": overall_status,
        "database": "connected" if db_ok else "disconnected",
        "chromadb": "connected" if chroma_ok else "disconnected",
        "embedding_mode": embedding_mode,
        "embedding_model": embedding_model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version
    }
