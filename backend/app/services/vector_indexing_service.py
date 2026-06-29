import logging
from typing import List, Dict, Any
from app.core.config import settings
from app.database.chroma import get_chroma_client

logger = logging.getLogger(__name__)

class VectorIndexingError(Exception):
    """Custom exception raised when vector indexing fails."""
    pass

class VectorIndexingService:
    """
    Handles indexing of document chunk embeddings into ChromaDB.
    """
    def __init__(self):
        self.collection_name = settings.chroma_collection_name
        self.client = None

    def _init_client(self):
        if not self.client:
            try:
                self.client = get_chroma_client()
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB client: {str(e)}")
                raise VectorIndexingError(f"ChromaDB connectivity error: {str(e)}")

    def get_or_create_collection(self):
        """
        Gets or creates the ChromaDB collection with Cosine similarity space.
        """
        self._init_client()
        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"Failed to get or create collection '{self.collection_name}': {str(e)}")
            raise VectorIndexingError(f"ChromaDB collection error: {str(e)}")

    def delete_document_vectors(self, document_id: str) -> None:
        """
        Deletes all vector records in ChromaDB matching the document_id.
        """
        self._init_client()
        try:
            collection = self.get_or_create_collection()
            # Delete where document_id matches
            collection.delete(where={"document_id": document_id})
            logger.info(f"Deleted existing vectors for document_id '{document_id}' from ChromaDB.")
        except Exception as e:
            logger.error(f"Failed to delete existing vectors for document '{document_id}': {str(e)}")
            raise VectorIndexingError(f"ChromaDB delete error: {str(e)}")

    def index_chunks(
        self,
        document_id: str,
        chunks_data: List[Dict[str, Any]]
    ) -> int:
        """
        Indexes a list of chunks with their pre-generated embeddings and metadata into ChromaDB.
        Re-running this method deletes old records for the same document to ensure idempotency.
        
        Each dictionary in chunks_data must contain:
          - chunk_id: str
          - text: str
          - embedding: List[float]
          - metadata: Dict[str, Any]
        """
        if not chunks_data:
            return 0

        self._init_client()
        for idx, item in enumerate(chunks_data):
            if not item.get("embedding"):
                raise VectorIndexingError(f"Missing embedding for chunk {item.get('chunk_id')} at index {idx}.")

        try:
            # 1. Delete existing vectors for this document first
            self.delete_document_vectors(document_id)

            # 2. Get the collection
            collection = self.get_or_create_collection()

            # 3. Batch insert/upsert
            ids = [item["chunk_id"] for item in chunks_data]
            embeddings = [item["embedding"] for item in chunks_data]
            documents = [item["text"] for item in chunks_data]
            metadatas = [item["metadata"] for item in chunks_data]

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )

            logger.info(f"Successfully indexed {len(ids)} chunks for document '{document_id}' into ChromaDB collection '{self.collection_name}'.")
            return len(ids)
        except Exception as e:
            logger.error(f"Failed to index chunks for document '{document_id}' in ChromaDB: {str(e)}")
            raise VectorIndexingError(f"ChromaDB indexing error: {str(e)}")
