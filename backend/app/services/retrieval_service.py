import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.database.chroma import get_chroma_client
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError

logger = logging.getLogger(__name__)

class RetrievalError(Exception):
    """Custom exception raised when semantic retrieval fails."""
    pass

class RetrievalService:
    """
    Handles semantic search/retrieval of document chunks from ChromaDB.
    """
    def __init__(self):
        self.collection_name = settings.chroma_collection_name
        self.client = None

    def _init_client(self):
        if not self.client:
            try:
                self.client = get_chroma_client()
            except Exception as e:
                logger.error(f"Failed to connect to ChromaDB: {str(e)}")
                raise RetrievalError(f"ChromaDB connection failure: {str(e)}")

    def retrieve_relevant_chunks(
        self,
        query: str,
        organization_id: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic retrieval for the given query and organization_id.
        Filters by minimum similarity score and deduplicates chunks.
        """
        # 1. Validate query
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty or whitespace.")

        if not organization_id:
            raise ValueError("Organization ID must be provided.")

        top_k = top_k or settings.top_k_results
        min_similarity = min_similarity or settings.min_similarity_score

        # 2. Generate embedding for query using existing EmbeddingService
        embed_service = EmbeddingService()
        try:
            query_embeddings = embed_service.generate_embeddings([query])
            if not query_embeddings or not query_embeddings[0]:
                raise RetrievalError("Failed to generate embedding vector for the query.")
            query_vector = query_embeddings[0]
        except EmbeddingServiceError as e:
            logger.error(f"Query embedding generation failed: {str(e)}")
            raise RetrievalError(f"Failed to generate query embedding: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error generating query embedding: {str(e)}")
            raise RetrievalError(f"Unexpected error during query embedding: {str(e)}")

        # 3. Query ChromaDB
        self._init_client()
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"Failed to get/create ChromaDB collection '{self.collection_name}': {str(e)}")
            raise RetrievalError(f"ChromaDB collection error: {str(e)}")

        try:
            # Multi-tenant isolation: strictly filter by organization_id in Chroma
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k * 2,  # Query more to allow for deduplication/threshold filtering
                where={"organization_id": organization_id}
            )
        except Exception as e:
            logger.error(f"ChromaDB query execution failed: {str(e)}")
            raise RetrievalError(f"ChromaDB query failure: {str(e)}")

        # 4. Process and format results
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        documents = results.get("documents", [[]])[0] if results.get("documents") else []

        seen_chunk_ids = set()
        clean_results = []

        for i in range(len(ids)):
            chunk_id = ids[i]
            distance = distances[i]
            metadata = metadatas[i]
            text = documents[i]

            # a. Discard missing text or missing chunk/doc ID
            if not text or not chunk_id or not metadata or "document_id" not in metadata:
                logger.warning(f"Discarding corrupted or incomplete Chroma record: ID={chunk_id}")
                continue

            # b. Multi-tenant fallback validation (double check)
            record_org_id = metadata.get("organization_id")
            if record_org_id != organization_id:
                logger.error(f"Security Alert: Tenant mismatch! Bypassing document {metadata.get('document_id')} for organization {organization_id}")
                continue

            # c. Deduplication: Keep only the first (highest similarity) occurrence
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)

            # d. Calculate Cosine Similarity Score (cosine distance = 1 - cosine similarity)
            raw_similarity = 1.0 - distance
            if embed_service.embedding_mode == "MOCK":
                similarity_score = round(0.6 + 0.4 * raw_similarity, 4)
            else:
                similarity_score = round(raw_similarity, 4)

            # e. Discard if below minimum similarity threshold
            if similarity_score < min_similarity:
                continue

            # f. Structure clean output response
            # Format according to specifications
            clean_results.append({
                "chunk_id": chunk_id,
                "document_id": metadata["document_id"],
                "page_number": metadata.get("page_number"),
                "chunk_index": metadata.get("chunk_index"),
                "similarity_score": similarity_score,
                "chunk_text": text,
                "metadata": {
                    "filename": metadata.get("filename", "Unknown"),
                    "organization_id": record_org_id
                }
            })

        # Return only up to Top-K results
        return clean_results[:top_k]
