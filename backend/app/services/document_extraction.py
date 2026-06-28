import os
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class DocumentExtractionError(Exception):
    """Custom exception raised when document text extraction fails."""
    pass

def clean_text(text: str) -> str:
    """
    Performs lightweight cleaning of the extracted text:
    - Normalizes inline whitespace (tabs/spaces reduced to a single space)
    - Trims leading/trailing spaces on each line
    - Removes repeated blank lines (reduces multiple empty lines to a single empty line)
    - Trims leading/trailing spaces of the entire document
    """
    if not text:
        return ""
    
    # 1. Normalize line-by-line spaces
    lines = []
    for line in text.split("\n"):
        # Replace multiple spaces/tabs with a single space and strip line ends
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned_line)
        
    # 2. Collapse consecutive empty lines
    collapsed_lines = []
    prev_was_empty = False
    for line in lines:
        if line == "":
            if not prev_was_empty:
                collapsed_lines.append(line)
                prev_was_empty = True
        else:
            collapsed_lines.append(line)
            prev_was_empty = False
            
    # 3. Join and return trimmed document
    return "\n".join(collapsed_lines).strip()

def extract_pdf(file_path: str) -> List[Dict]:
    """
    Extracts text page-by-page from a PDF file using PyMuPDF (fitz).
    Returns a list of dictionaries with 'page_number' and 'page_text'.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed in the environment.")
        raise DocumentExtractionError("PDF parser library is unavailable on the server.")

    if not os.path.exists(file_path):
        raise DocumentExtractionError(f"Physical file not found on path: {file_path}")

    pages = []
    try:
        with fitz.open(file_path) as doc:
            if doc.page_count == 0:
                raise DocumentExtractionError("PDF document has no pages.")

            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                text = page.get_text()
                cleaned = clean_text(text)
                pages.append({
                    "page_number": page_num + 1,
                    "page_text": cleaned
                })
    except DocumentExtractionError:
        raise
    except Exception as e:
        logger.error(f"Error reading PDF file {file_path}: {str(e)}")
        raise DocumentExtractionError(f"Failed to parse PDF document structure: {str(e)}")

    # Check if we extracted any text at all
    all_text = "".join(p["page_text"] for p in pages)
    if not all_text.strip():
        raise DocumentExtractionError("PDF document contains no extractable text.")

    return pages

def extract_txt(file_path: str) -> List[Dict]:
    """
    Reads plain text document and normalizes line endings.
    Returns a single logical page.
    """
    if not os.path.exists(file_path):
        raise DocumentExtractionError(f"Physical file not found on path: {file_path}")

    # Try UTF-8 first, fallback to Latin-1
    text = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        logger.warning(f"UTF-8 decoding failed for {file_path}. Retrying with latin-1 fallback.")
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
        except Exception as e:
            logger.error(f"Failed to read text file with latin-1 fallback: {str(e)}")
            raise DocumentExtractionError(f"Unreadable text encoding: {str(e)}")
    except Exception as e:
        logger.error(f"Error reading text file {file_path}: {str(e)}")
        raise DocumentExtractionError(f"Failed to read text file: {str(e)}")

    if not text.strip():
        raise DocumentExtractionError("Text document is empty.")

    # Normalize line endings
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = clean_text(normalized_text)

    return [{
        "page_number": 1,
        "page_text": cleaned
    }]

def extract_docx(file_path: str) -> List[Dict]:
    """
    Extracts text paragraph-by-paragraph from a DOCX file using python-docx.
    Returns a single logical page containing the full text.
    """
    try:
        import docx
    except ImportError:
        logger.error("python-docx is not installed in the environment.")
        raise DocumentExtractionError("DOCX parser library is unavailable on the server.")

    if not os.path.exists(file_path):
        raise DocumentExtractionError(f"Physical file not found on path: {file_path}")

    try:
        doc = docx.Document(file_path)
    except Exception as e:
        logger.error(f"Failed to open DOCX package at {file_path}: {str(e)}")
        raise DocumentExtractionError(f"Corrupted or invalid DOCX document package: {str(e)}")

    paragraphs = []
    for paragraph in doc.paragraphs:
        paragraphs.append(paragraph.text)

    full_text = "\n".join(paragraphs)
    cleaned = clean_text(full_text)

    if not cleaned.strip():
        raise DocumentExtractionError("DOCX document has no extractable text content.")

    return [{
        "page_number": 1,
        "page_text": cleaned
    }]

def extract_text_from_file(file_path: str, ext: str) -> List[Dict]:
    """
    Detects document extension and extracts text accordingly.
    Supported extensions: 'pdf', 'txt', 'docx'.
    """
    ext_lower = ext.lower().strip().lstrip(".")
    if ext_lower == "pdf":
        return extract_pdf(file_path)
    elif ext_lower == "txt":
        return extract_txt(file_path)
    elif ext_lower == "docx":
        return extract_docx(file_path)
    else:
        raise DocumentExtractionError(f"Unsupported document file extension: '.{ext_lower}'")
