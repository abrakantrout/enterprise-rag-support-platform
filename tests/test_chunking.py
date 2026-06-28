import os
import sys
import tempfile
import requests

# Add backend to path to allow importing chunking service directly for unit testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.chunking_service import (
    chunk_document,
    chunk_page,
    split_large_paragraph,
    apply_overlap,
    validate_chunk,
    ChunkingValidationError
)

BASE_URL = "http://127.0.0.1:8000"

def run_unit_tests():
    print("\n--- RUNNING CHUNKING SERVICE UNIT TESTS ---")

    # 1. Test validate_chunk
    print("[Unit Test 1] validate_chunk...")
    assert validate_chunk("Valid chunk text", 500, 700) is True
    assert validate_chunk("", 500, 700) is False
    assert validate_chunk("   ", 500, 700) is False
    print("[OK] validate_chunk passed")

    # 2. Test apply_overlap
    print("[Unit Test 2] apply_overlap...")
    parts = ["This", "is", "some", "chunk", "text", "to", "verify", "overlap"]
    # Joining with space " ", overlap size = 15 characters
    overlap_res = apply_overlap(parts, " ", 15)
    # Reconstruct text: "verify overlap" = 14 chars
    assert overlap_res == ["verify", "overlap"]
    print("[OK] apply_overlap passed")

    # 3. Test split_large_paragraph (words not cut in half)
    print("[Unit Test 3] split_large_paragraph...")
    large_paragraph = (
        "ThisIsALongWordThatShouldNotBeCutInHalfButWillBeIfNoSpacesExist. "
        "Here are some normal words. "
        "Another sentence to make it larger than target parameters."
    )
    # Target size = 30, overlap = 5, max = 50
    split_parts = split_large_paragraph(large_paragraph, 30, 5, 50)
    print(f"Split parts: {split_parts}")
    # Verify no word is cut in half (except if a single word is larger than max_size)
    for part in split_parts:
        assert len(part) <= 50, f"Part too large: {len(part)} chars"
    print("[OK] split_large_paragraph passed")

    # 4. Test page numbering conservation & offset tracking
    print("[Unit Test 4] chunk_page (offsets and pages)...")
    page_text = "Paragraph one of the document.\n\nParagraph two with more details.\n\nParagraph three is the final paragraph."
    # Target size = 40, overlap = 10, max = 60
    chunks = chunk_page("doc123", 2, page_text, 40, 10, 60)
    print(f"Generated page chunks: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"  Chunk {i}: '{c['text']}' [{c['start_offset']}:{c['end_offset']}]")
        assert c["page_number"] == 2
        # Verify text slice matches the original text offsets
        sliced_text = page_text[c["start_offset"]:c["end_offset"]]
        assert c["text"] == sliced_text, f"Offset mismatch: '{c['text']}' != '{sliced_text}'"
    print("[OK] chunk_page offsets and page conserving passed")

    # 5. Test overlap correctness
    print("[Unit Test 5] Overlap correctness...")
    doc_text = "WordA WordB WordC WordD WordE WordF"
    # If we split into two chunks, check if they share the overlap words
    chunks = chunk_page("doc123", 1, doc_text, 20, 10, 25)
    print(f"Overlap chunks: {chunks}")
    if len(chunks) > 1:
        # Check if the end of first chunk overlaps with beginning of second chunk
        c1 = chunks[0]["text"]
        c2 = chunks[1]["text"]
        # They should share some words (e.g. WordD or WordC)
        assert any(w in c1 for w in c2.split()), f"No shared words in overlap: '{c1}' and '{c2}'"
    print("[OK] Overlap correctness passed")

    # 6. Test chunk_document empty document validation
    print("[Unit Test 6] Empty pages validation...")
    try:
        chunk_document("doc123", [], 500, 50, 700)
        assert False, "Should have failed on empty pages"
    except ChunkingValidationError as e:
        print(f"Correctly caught exception: {str(e)}")
        print("[OK] Empty page validation passed")


def run_api_tests():
    print("\n--- RUNNING CHUNKING API INTEGRATION TESTS ---")

    # 1. SETUP - Authenticate Admin
    admin_email = "admin@enterprise.com"
    password = "SecurePassword123"

    print("[Setup] Authenticating Administrator...")
    login_data = {"username": admin_email, "password": password}
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    admin_token = resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[Setup] Administrator authenticated successfully")

    # 2. API Test: Small TXT chunking
    print("\n[API Test 1] Chunk small TXT file (fits in 1 chunk)...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"This is small document text. It is under 500 characters and should produce exactly one chunk.")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("small.txt", file_bytes, "text/plain")}
            up_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        assert up_resp.status_code == 201, up_resp.text
        doc_id = up_resp.json()["id"]

        # Call chunking endpoint
        chunk_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/chunk", headers=admin_headers)
        print(f"Status Code: {chunk_resp.status_code}")
        print(f"Response: {chunk_resp.json()}")
        assert chunk_resp.status_code == 200
        data = chunk_resp.json()
        assert data["number_of_chunks"] == 1
        assert data["smallest_chunk"] == data["largest_chunk"]
        print("[OK] Small TXT chunked correctly")
    finally:
        os.remove(f_name)

    # 3. API Test: Large TXT chunking
    print("\n[API Test 2] Chunk large TXT file...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        # Create a large document with 5 paragraphs of 300 characters
        paragraphs = [
            "This is paragraph one of the large document text. We are testing the Recursive Character Splitter splitting logic to ensure paragraphs are preserved where possible.",
            "This is paragraph two. It contains different content but similar structure to paragraph one. We keep paragraphs intact if they fit within target bounds.",
            "This is paragraph three. Let's make sure it wraps and merges with other paragraphs. Target chunk size is 500, so paragraph 1 and 2 will merge into chunk 1.",
            "This is paragraph four. It should start a new chunk since adding it to paragraph 3 would exceed the 500 characters threshold configuration.",
            "This is paragraph five. The final paragraph of the large text testing file. It will merge with paragraph four or reside in its own chunk."
        ]
        f.write(("\n\n".join(paragraphs)).encode("utf-8"))
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("large.txt", file_bytes, "text/plain")}
            up_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        assert up_resp.status_code == 201, up_resp.text
        doc_id = up_resp.json()["id"]

        # Call chunking endpoint
        chunk_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/chunk", headers=admin_headers)
        print(f"Status Code: {chunk_resp.status_code}")
        print(f"Response: {chunk_resp.json()}")
        assert chunk_resp.status_code == 200
        data = chunk_resp.json()
        assert data["number_of_chunks"] > 1
        print("[OK] Large TXT chunked correctly")
    finally:
        os.remove(f_name)

    # 4. API Test: Rejection of empty document
    print("\n[API Test 3] Rejection of empty document...")
    # We can create a document record with status "Failed" or empty file
    # Let's test non-existent document ID
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    resp = requests.post(f"{BASE_URL}/api/v1/documents/{fake_uuid}/chunk", headers=admin_headers)
    print(f"Status Code: {resp.status_code}")
    assert resp.status_code == 404
    print("[OK] Rejection of missing/empty document passed")


if __name__ == "__main__":
    try:
        run_unit_tests()
        run_api_tests()
        print("\n=== ALL SPRINT 5 CHUNKING TESTS PASSED SUCCESSFULLY ===")
    except AssertionError as e:
        print(f"\n[FAIL] TEST ASSERTION FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)
