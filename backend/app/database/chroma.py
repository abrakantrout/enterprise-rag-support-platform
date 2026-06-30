import os
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global client cache
_chroma_client = None


def get_chroma_client():
    """
    Returns an initialized instance of the ChromaDB client.
    Automatically falls back to PersistentClient if HttpClient connection fails
    or if host is 'local'.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    if settings.chroma_host in ("local", "", None):
        logger.info("Using ChromaDB PersistentClient")
        _chroma_client = chromadb.PersistentClient(
            path=os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db"),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        return _chroma_client

    try:
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=str(settings.chroma_port),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        client.heartbeat()
        _chroma_client = client
        return _chroma_client
    except Exception as e:
        logger.warning(
            f"Failed to connect to ChromaDB at {settings.chroma_host}:{settings.chroma_port}. "
            f"Falling back to local PersistentClient. Error: {str(e)}"
        )
        _chroma_client = chromadb.PersistentClient(
            path=os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db"),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        return _chroma_client


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
