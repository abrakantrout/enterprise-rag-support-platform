import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class CitationService:
    """
    Service responsible for converting optimized retrieval results into structured,
    secure, deduplicated, and relevance-ordered citation objects.
    """
    def build_citations(self, retrieval_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Accepts a list of retrieval chunks and converts them into validated citations.
        
        Args:
            retrieval_results (List[Dict[str, Any]]): List of chunk objects.
            
        Returns:
            List[Dict[str, Any]]: Structured and validated citation dicts.
        """
        if not retrieval_results:
            return []

        citations = []
        seen_chunks = set()
        
        # Ensure relevance ordering: sort input by similarity score descending
        sorted_results = sorted(
            retrieval_results,
            key=lambda x: float(x.get("similarity_score") if x.get("similarity_score") is not None else 0.0),
            reverse=True
        )

        citation_counter = 1

        for item in sorted_results:
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                chunk_id = "N/A"
                
            # If we've already cited this exact chunk, skip it (deduplication)
            if chunk_id != "N/A" and chunk_id in seen_chunks:
                continue
                
            document_id = item.get("document_id") or "Unknown"
            
            metadata = item.get("metadata") or {}
            document_name = metadata.get("filename") or "Unknown Document"
            
            page_number = item.get("page_number")
            if page_number is None:
                page_number = metadata.get("page_number")
            
            try:
                if page_number is not None:
                    page_number = int(page_number)
            except (ValueError, TypeError):
                page_number = None

            chunk_index = item.get("chunk_index")
            if chunk_index is None:
                chunk_index = metadata.get("chunk_index")
            try:
                if chunk_index is not None:
                    chunk_index = int(chunk_index)
                else:
                    chunk_index = 0
            except (ValueError, TypeError):
                chunk_index = 0

            similarity_score = item.get("similarity_score")
            try:
                if similarity_score is not None:
                    similarity_score = float(similarity_score)
                    # Safe normalization bounds
                    if similarity_score < 0.0 or similarity_score > 1.0:
                        similarity_score = max(0.0, min(1.0, similarity_score))
                else:
                    similarity_score = 0.0
            except (ValueError, TypeError):
                similarity_score = 0.0

            # Build source label
            if page_number is not None:
                source_label = f"{document_name}, page {page_number}"
            else:
                source_label = document_name

            # Text preview (first 200 characters)
            chunk_text = item.get("chunk_text") or ""
            text_preview = chunk_text[:200]

            # Build Citation
            citation = {
                "citation_id": f"S{citation_counter}",
                "document_id": document_id,
                "document_name": document_name,
                "page_number": page_number,
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "similarity_score": similarity_score,
                "source_label": source_label,
                "text_preview": text_preview,
                # Backward compatibility
                "document": document_name,
                "page": page_number
            }

            citations.append(citation)
            if chunk_id != "N/A":
                seen_chunks.add(chunk_id)
            citation_counter += 1

        return citations
