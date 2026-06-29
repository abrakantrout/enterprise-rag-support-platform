import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AnswerVerificationService:
    """
    Service responsible for deterministically verifying generated answers
    by assessing retrieval results, similarity metrics, and citation counts.
    Does NOT call any LLMs.
    """
    def verify_answer(
        self,
        answer: str,
        retrieved_chunks: List[Dict[str, Any]],
        optimization_summary: Dict[str, Any],
        citation_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Runs deterministic verification on the answer and returns a validation summary.
        
        Args:
            answer (str): The generated grounded text.
            retrieved_chunks (List[Dict[str, Any]]): Optimized list of chunks.
            optimization_summary (Dict[str, Any]): Optimization summary dictionary.
            citation_list (List[Dict[str, Any]]): Built citations list.
            
        Returns:
            Dict[str, Any]: Verification summary metrics and status.
        """
        retrieval_count = len(retrieved_chunks)
        citations_count = len(citation_list)

        # 1. Calculate Average Similarity
        if citations_count > 0:
            total_similarity = sum(float(c.get("similarity_score", 0.0)) for c in citation_list)
            average_similarity = total_similarity / citations_count
        else:
            average_similarity = 0.0

        # Round average similarity for clean output
        average_similarity = round(average_similarity, 4)

        # 2. Refusal check
        is_refusal = (
            "I could not find relevant information in the uploaded documents." in answer
            or retrieval_count == 0
            or citations_count == 0
        )

        if is_refusal:
            confidence = 0.0
            status_val = "unsupported"
            reason = "No relevant documents retrieved to back the response."
        else:
            # 3. Calculate Confidence Score
            # Weighted combo of similarity (60%) and citation count density (40%)
            citation_factor = min(1.0, citations_count / 4.0)
            raw_confidence = (average_similarity * 0.60) + (citation_factor * 0.40)
            confidence = max(0.0, min(1.0, round(float(raw_confidence), 4)))

            # Determine Status Values
            if confidence >= 0.80:
                status_val = "supported"
                reason = "Multiple high similarity chunks support the response."
            elif confidence >= 0.50:
                status_val = "moderate"
                reason = "Moderate support. Source documents are available but similarity or citation depth is moderate."
            elif confidence >= 0.15:
                status_val = "low_confidence"
                reason = "Low confidence. Source documents have low similarity or limited citations."
            else:
                status_val = "unsupported"
                reason = "Unsupported. Confidence score falls below the baseline support threshold."

        return {
            "confidence": confidence,
            "verification_status": status_val,
            "reason": reason,
            "retrieval_count": retrieval_count,
            "average_similarity": average_similarity,
            "citations_count": citations_count
        }
