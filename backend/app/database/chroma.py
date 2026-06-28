import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_chroma_client() -> chromadb.HttpClient:
    """
    Returns an initialized instance of the ChromaDB HTTP client
    using properties specified in application settings.
    """
    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=str(settings.chroma_port),
        settings=ChromaSettings(anonymized_telemetry=False)
    )


def check_chroma_connection() -> bool:
    """
    Performs a simple heartbeat check against ChromaDB to verify connectivity.

    Returns:
        bool: True if the server responds, False otherwise.
    """
    try:
        client = get_chroma_client()
        client.heartbeat()
        return True
    except Exception as e:
        logger.error(f"ChromaDB connection check failed: {str(e)}")
        return False
