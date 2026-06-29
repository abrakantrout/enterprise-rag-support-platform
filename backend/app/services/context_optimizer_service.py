import logging
import difflib
from typing import List, Dict, Any, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

class ContextOptimizerService:
    """
    Service responsible for optimizing retrieval contexts by removing duplicates,
    near-duplicates, enforcing document/page diversity, and applying character budgets.
    """
    def __init__(self):
        self.max_characters = settings.max_context_characters

    def _are_near_duplicates(self, text1: str, text2: str) -> bool:
        """
        Fast near-duplicate detector. Filters out comparisons using length difference
        and Jaccard token overlap before invoking difflib.SequenceMatcher.
        """
        len1 = len(text1)
        len2 = len(text2)
        if len1 == 0 or len2 == 0:
            return False

        # If length difference is greater than 10%, they cannot share >90% identical text
        if abs(len1 - len2) / max(len1, len2) > 0.10:
            return False

        # Quick Jaccard token overlap check (removing punctuation)
        import string
        translator = str.maketrans("", "", string.punctuation)
        words1 = set(text1.lower().translate(translator).split())
        words2 = set(text2.lower().translate(translator).split())
        
        union_len = len(words1.union(words2))
        jaccard = len(words1.intersection(words2)) / union_len if union_len > 0 else 0.0
        if jaccard < 0.80:
            return False

        # Fine-grained SequenceMatcher check
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        return ratio > 0.90

    def optimize_context(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Processes chunks through the optimization pipeline:
        1. Discard empty / invalid chunks.
        2. Deduplicate exact and near-duplicates (preserving highest similarity).
        3. Select chunks to maximize document and page diversity.
        4. Apply maximum character token budget.
        5. Sort final results by similarity score descending.
        6. Calculate and return optimization summary.
        """
        original_count = len(chunks)
        discarded_empty = 0
        duplicates_removed = 0
        near_duplicates_removed = 0

        # Sort by similarity score descending to ensure we keep the highest similarity chunks during deduplication
        sorted_chunks = sorted(chunks, key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        unique_chunks = []

        # 1 & 2. Discard empty/invalid and remove exact/near duplicates
        for chunk in sorted_chunks:
            text = chunk.get("chunk_text")
            metadata = chunk.get("metadata")
            chunk_id = chunk.get("chunk_id")
            doc_id = chunk.get("document_id")

            # Check for empty, whitespace, missing text, or missing critical metadata
            if text is None or not str(text).strip() or not metadata or not chunk_id or not doc_id:
                discarded_empty += 1
                continue

            text_str = str(text).strip()

            # Check exact duplicates
            is_duplicate = False
            for uc in unique_chunks:
                if uc["chunk_text"].strip() == text_str:
                    is_duplicate = True
                    break
            if is_duplicate:
                duplicates_removed += 1
                continue

            # Check near duplicates
            is_near_duplicate = False
            for uc in unique_chunks:
                if self._are_near_duplicates(uc["chunk_text"], text_str):
                    is_near_duplicate = True
                    break
            if is_near_duplicate:
                near_duplicates_removed += 1
                continue

            # Chunk is valid and unique
            unique_chunks.append(chunk)

        # 3. Document and Page Diversity Selection
        # Select chunks one-by-one, penalizing already selected documents and pages
        selected_chunks = []
        remaining_chunks = list(unique_chunks)
        doc_counts: Dict[str, int] = {}
        page_counts: Dict[Tuple[str, Any], int] = {}

        while remaining_chunks:
            best_idx = -1
            best_doc_count = float('inf')
            best_page_count = float('inf')
            best_score = -1.0

            for idx, chunk in enumerate(remaining_chunks):
                doc_id = chunk.get("document_id") or "unknown"
                page = chunk.get("page_number")
                page_key = (doc_id, page)

                d_count = doc_counts.get(doc_id, 0)
                p_count = page_counts.get(page_key, 0)
                score = chunk.get("similarity_score", 0.0)

                # Prioritize:
                # 1. Broader document coverage (lower doc count)
                # 2. Broader page coverage within document (lower page count)
                # 3. Higher similarity score
                if (d_count < best_doc_count) or \
                   (d_count == best_doc_count and p_count < best_page_count) or \
                   (d_count == best_doc_count and p_count == best_page_count and score > best_score):
                    best_idx = idx
                    best_doc_count = d_count
                    best_page_count = p_count
                    best_score = score

            if best_idx == -1:
                break

            chosen = remaining_chunks.pop(best_idx)
            selected_chunks.append(chosen)

            # Update selected counts
            doc_id = chosen.get("document_id") or "unknown"
            page = chosen.get("page_number")
            page_key = (doc_id, page)
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
            page_counts[page_key] = page_counts.get(page_key, 0) + 1

        # 4. Apply Token / Character Budget
        budget_chunks = []
        total_estimated_chars = 0

        for chunk in selected_chunks:
            metadata = chunk.get("metadata") or {}
            filename = metadata.get("filename") or "Unknown"
            page = chunk.get("page_number")
            page_str = str(page) if page is not None else "N/A"
            chunk_id = chunk.get("chunk_id") or "N/A"
            text = chunk.get("chunk_text") or ""

            # Estimate formatted block size
            block_len = len(f"[Source 99]\nDocument: {filename}\nPage: {page_str}\nChunk ID: {chunk_id}\nContent:\n{text}\n\n")

            if total_estimated_chars + block_len <= self.max_characters:
                budget_chunks.append(chunk)
                total_estimated_chars += block_len
            else:
                # Always ensure at least one chunk is included (even if it exceeds the budget, it will get truncated)
                if not budget_chunks:
                    budget_chunks.append(chunk)
                    total_estimated_chars += block_len
                break

        # 5. Sort final optimized chunks by similarity descending
        optimized_chunks = sorted(budget_chunks, key=lambda x: x.get("similarity_score", 0.0), reverse=True)

        # 6. Calculate summary
        summary = {
            "original_chunks": original_count,
            "optimized_chunks": len(optimized_chunks),
            "duplicates_removed": duplicates_removed,
            "near_duplicates_removed": near_duplicates_removed,
            "discarded_empty": discarded_empty,
            "estimated_characters": total_estimated_chars
        }

        return optimized_chunks, summary
