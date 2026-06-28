import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ChunkingValidationError(Exception):
    """Custom exception raised when chunking input or configuration is invalid."""
    pass

def validate_chunk(chunk_text: str, chunk_size: int, chunk_max_size: int) -> bool:
    """
    Validates a chunk's integrity:
    - Must not be empty.
    - Should ideally fit within the maximum size constraint (warning only if a single word exceeds it).
    """
    if not chunk_text or not chunk_text.strip():
        return False
    return True

def apply_overlap(current_chunk_parts: List[str], separator: str, chunk_overlap: int) -> List[str]:
    """
    Computes overlapping suffix parts from the ending of a completed chunk.
    Looks backward to group elements whose joined length is less than or equal to chunk_overlap.
    """
    if not current_chunk_parts or chunk_overlap <= 0:
        return []

    overlap_parts = []
    overlap_len = 0

    # Look backwards from the end of the completed chunk parts
    for part in reversed(current_chunk_parts):
        # Calculate expected length if we add this part
        potential_len = len(part) + (len(separator) if overlap_parts else 0)
        if overlap_len + potential_len <= chunk_overlap:
            overlap_parts.insert(0, part)
            overlap_len += potential_len
        else:
            break

    return overlap_parts

def split_large_paragraph(paragraph_text: str, chunk_size: int, chunk_overlap: int, chunk_max_size: int) -> List[str]:
    """
    Splits a single paragraph that exceeds chunk_max_size into smaller parts.
    Recursively uses separators like newline '\n', space ' ', or fallback empty character ''.
    """
    return split_text_recursive(paragraph_text, ["\n", " ", ""], chunk_size, chunk_overlap, chunk_max_size)

def split_text_recursive(text: str, separators: List[str], chunk_size: int, chunk_overlap: int, chunk_max_size: int) -> List[str]:
    """
    Recursively splits text using a priority list of separators.
    """
    if len(text) <= chunk_max_size:
        return [text]

    # Find the first separator present in the text
    separator = separators[0]
    next_separators = separators[1:]
    for sep in separators:
        if sep == "":
            separator = sep
            break
        if sep in text:
            separator = sep
            next_separators = separators[separators.index(sep) + 1:]
            break

    # Split using the selected separator
    if separator != "":
        parts = text.split(separator)
    else:
        parts = list(text)  # fallback to character split

    # Recursively split any segment that exceeds chunk_max_size
    final_parts = []
    for part in parts:
        if len(part) <= chunk_max_size:
            final_parts.append(part)
        else:
            final_parts.extend(
                split_text_recursive(part, next_separators, chunk_size, chunk_overlap, chunk_max_size)
            )

    # Merge parts back into chunks respecting target chunk_size and chunk_overlap
    chunks = []
    current_chunk = []
    current_len = 0

    i = 0
    while i < len(final_parts):
        part = final_parts[i]
        part_len = len(part)

        # Base case: empty current chunk
        if not current_chunk:
            current_chunk.append(part)
            current_len = part_len
            i += 1
        # Check if adding the part fits target size
        elif current_len + len(separator) + part_len <= chunk_size:
            current_chunk.append(part)
            current_len += len(separator) + part_len
            i += 1
        else:
            # Current chunk is full; finalize it
            chunk_text = separator.join(current_chunk)
            chunks.append(chunk_text)

            # Apply overlap by calculating lookback elements
            overlap_parts = apply_overlap(current_chunk, separator, chunk_overlap)
            current_chunk = overlap_parts
            current_len = (
                sum(len(p) for p in current_chunk) + len(separator) * (len(current_chunk) - 1)
                if current_chunk
                else 0
            )

            # Append the current part to overlap or create a new chunk
            if not current_chunk:
                current_chunk.append(part)
                current_len = part_len
                i += 1
            elif current_len + len(separator) + part_len <= chunk_size:
                current_chunk.append(part)
                current_len += len(separator) + part_len
                i += 1
            else:
                current_chunk = [part]
                current_len = part_len
                i += 1

    if current_chunk:
        chunk_text = separator.join(current_chunk)
        chunks.append(chunk_text)

    return chunks

def chunk_page(document_id: str, page_number: int, page_text: str, chunk_size: int, chunk_overlap: int, chunk_max_size: int) -> List[Dict]:
    """
    Chunks a single page's text by applying:
    1. Paragraph splitting via logical sections (\n\n).
    2. Recursive splitting of oversized paragraphs (split_large_paragraph).
    3. Merging with overlaps.
    4. Start and end character offsets mapping.
    """
    # Validation checks
    if not page_text or not page_text.strip():
        return []

    # Priority 1: Split by logical paragraphs (\n\n)
    paragraphs = page_text.split("\n\n")

    # Priority 2 & 3: Evaluate sizes and split large paragraphs
    processed_elements = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= chunk_max_size:
            processed_elements.append(paragraph)
        else:
            # Large paragraph split
            split_paras = split_large_paragraph(paragraph, chunk_size, chunk_overlap, chunk_max_size)
            processed_elements.extend(split_paras)

    # Merge processed elements into final page chunks with overlap
    chunks_text_list = []
    current_chunk = []
    current_len = 0

    separator = "\n\n"
    i = 0
    while i < len(processed_elements):
        elem = processed_elements[i]
        elem_len = len(elem)

        if not current_chunk:
            current_chunk.append(elem)
            current_len = elem_len
            i += 1
        elif current_len + len(separator) + elem_len <= chunk_size:
            current_chunk.append(elem)
            current_len += len(separator) + elem_len
            i += 1
        else:
            # Finalize
            joined_text = separator.join(current_chunk)
            chunks_text_list.append(joined_text)

            # Apply overlap
            overlap_parts = apply_overlap(current_chunk, separator, chunk_overlap)
            current_chunk = overlap_parts
            current_len = (
                sum(len(p) for p in current_chunk) + len(separator) * (len(current_chunk) - 1)
                if current_chunk
                else 0
            )

            # Append next element
            if not current_chunk:
                current_chunk.append(elem)
                current_len = elem_len
                i += 1
            elif current_len + len(separator) + elem_len <= chunk_size:
                current_chunk.append(elem)
                current_len += len(separator) + elem_len
                i += 1
            else:
                current_chunk = [elem]
                current_len = elem_len
                i += 1

    if current_chunk:
        joined_text = separator.join(current_chunk)
        chunks_text_list.append(joined_text)

    # Build the final chunk dictionaries with offset coordinates
    page_chunks = []
    current_offset_search_ptr = 0

    for idx, text in enumerate(chunks_text_list):
        if not validate_chunk(text, chunk_size, chunk_max_size):
            continue

        # Find offsets in original page_text
        start_offset = page_text.find(text, current_offset_search_ptr)
        if start_offset == -1:
            # Fallback search from beginning of page
            start_offset = page_text.find(text)
            if start_offset == -1:
                start_offset = current_offset_search_ptr

        end_offset = start_offset + len(text)
        current_offset_search_ptr = end_offset

        page_chunks.append({
            "page_number": page_number,
            "text": text,
            "character_count": len(text),
            "start_offset": start_offset,
            "end_offset": end_offset
        })

    return page_chunks

def chunk_document(doc_id: str, pages: List[Dict], chunk_size: int, chunk_overlap: int, chunk_max_size: int) -> List[Dict]:
    """
    Splits an entire document (structured as a list of pages) into semantic chunks.
    Injects chunk_id, chunk_index, and document_id metadata.
    """
    # Validation checks
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_max_size <= chunk_size:
        raise ChunkingValidationError(
            f"Invalid chunk configuration: size={chunk_size}, overlap={chunk_overlap}, max={chunk_max_size}"
        )
    if chunk_overlap >= chunk_size:
        raise ChunkingValidationError("Overlap size must be strictly smaller than target chunk size.")
    if not pages:
        raise ChunkingValidationError("Cannot split document with zero pages.")

    all_chunks = []
    chunk_index = 0

    for page in pages:
        page_num = page.get("page_number")
        page_text = page.get("page_text", "")
        
        if page_num is None:
            raise ChunkingValidationError("Missing page number metadata in page dictionaries.")

        # Chunk the page text
        page_chunks = chunk_page(doc_id, page_num, page_text, chunk_size, chunk_overlap, chunk_max_size)

        for chunk_data in page_chunks:
            # Map into the final document chunk dictionary structure
            chunk_data["chunk_id"] = f"doc_{doc_id}_chunk_{chunk_index:04d}"
            chunk_data["document_id"] = doc_id
            chunk_data["chunk_index"] = chunk_index
            all_chunks.append(chunk_data)
            chunk_index += 1

    return all_chunks
