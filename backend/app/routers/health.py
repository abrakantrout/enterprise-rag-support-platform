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

    # The application status is unhealthy if any critical system is offline
    overall_status = "healthy" if (db_ok and chroma_ok) else "unhealthy"

    return {
        "status": overall_status,
        "database": "connected" if db_ok else "disconnected",
        "chromadb": "connected" if chroma_ok else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version
    }
