import os
import sys
import tempfile
import requests
import subprocess

BASE_URL = "http://127.0.0.1:8000"

def generate_docx(path, text):
    try:
        import docx
    except ImportError:
        print("[Setup] python-docx not found on host. Installing on host virtual environment...")
        subprocess.run([sys.executable, "-m", "pip", "install", "python-docx"])
        import docx

    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(path)

def generate_pdf(path, pages_text):
    try:
        import fitz
    except ImportError:
        print("[Setup] PyMuPDF not found on host. Installing on host virtual environment...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"])
        import fitz

    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()

def run_tests():
    print("=== STARTING SPRINT 4 DOCUMENT TEXT EXTRACTION API INTEGRATION TESTS ===")

    # 1. SETUP - Authenticate Admin
    admin_email = "admin@enterprise.com"
    password = "SecurePassword123"

    print("\n[Setup] Authenticating Administrator...")
    login_data = {"username": admin_email, "password": password}
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    admin_token = resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[Setup] Administrator authenticated successfully")

    # 2. Test valid TXT extraction
    print("\n[Test 1] Extract text from valid TXT document...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        txt_content = "Line 1: Text file content.\n\nLine 2: Normalizing whitespace.\n"
        f.write(txt_content.encode("utf-8"))
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("test_doc.txt", file_bytes, "text/plain")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test", "visibility": "public"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201, f"TXT Upload failed: {upload_resp.text}"
        doc_id = upload_resp.json()["id"]

        # Call extraction endpoint
        extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/extract", headers=admin_headers)
        print(f"Status Code: {extract_resp.status_code}")
        print(f"Response: {extract_resp.json()}")
        assert extract_resp.status_code == 200, f"Expected 200, got {extract_resp.status_code}"
        res = extract_resp.json()
        assert res["page_count"] == 1
        assert res["extraction_status"] == "Completed"
        assert "Normalizing whitespace." in res["preview"]

        # Verify DB status
        details_resp = requests.get(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=admin_headers)
        assert details_resp.json()["status"] == "Completed"
        assert details_resp.json()["extracted_at"] is not None
        print("[OK] TXT extraction succeeded and metadata saved to DB")
    finally:
        os.remove(f_name)

    # 3. Test valid PDF extraction
    print("\n[Test 2] Extract text from valid PDF document...")
    pdf_path = os.path.join(tempfile.gettempdir(), "test_doc.pdf")
    pages_data = [
        "First page content of the PDF document.",
        "Second page text details."
    ]
    generate_pdf(pdf_path, pages_data)

    try:
        with open(pdf_path, "rb") as file_bytes:
            files = {"file": ("test_doc.pdf", file_bytes, "application/pdf")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test", "visibility": "public"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201, f"PDF Upload failed: {upload_resp.text}"
        doc_id = upload_resp.json()["id"]

        # Call extraction endpoint
        extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/extract", headers=admin_headers)
        print(f"Status Code: {extract_resp.status_code}")
        print(f"Response: {extract_resp.json()}")
        assert extract_resp.status_code == 200, f"Expected 200, got {extract_resp.status_code}"
        res = extract_resp.json()
        assert res["page_count"] == 2
        assert res["extraction_status"] == "Completed"
        assert "First page" in res["preview"]

        # Verify DB status
        details_resp = requests.get(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=admin_headers)
        assert details_resp.json()["status"] == "Completed"
        print("[OK] PDF extraction succeeded and metadata saved to DB")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    # 4. Test valid DOCX extraction
    print("\n[Test 3] Extract text from valid DOCX document...")
    docx_path = os.path.join(tempfile.gettempdir(), "test_doc.docx")
    generate_docx(docx_path, "Hello this is paragraph text in a DOCX document.")

    try:
        with open(docx_path, "rb") as file_bytes:
            files = {"file": ("test_doc.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test", "visibility": "public"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201, f"DOCX Upload failed: {upload_resp.text}"
        doc_id = upload_resp.json()["id"]

        # Call extraction endpoint
        extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/extract", headers=admin_headers)
        print(f"Status Code: {extract_resp.status_code}")
        print(f"Response: {extract_resp.json()}")
        assert extract_resp.status_code == 200, f"Expected 200, got {extract_resp.status_code}"
        res = extract_resp.json()
        assert res["page_count"] == 1
        assert res["extraction_status"] == "Completed"
        assert "Hello this is paragraph text" in res["preview"]
        print("[OK] DOCX extraction succeeded and metadata saved to DB")
    finally:
        if os.path.exists(docx_path):
            os.remove(docx_path)

    # 5. Test corrupted PDF file
    print("\n[Test 4] Extract text from corrupted PDF file...")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # Write corrupted pdf (missing PDF headers)
        f.write(b"corrupted raw data that is not a valid pdf format")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("corrupt.pdf", file_bytes, "application/pdf")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        doc_id = upload_resp.json()["id"]

        # Call extraction endpoint (should fail and map to HTTP 400)
        extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/extract", headers=admin_headers)
        print(f"Status Code: {extract_resp.status_code}")
        print(f"Response: {extract_resp.text}")
        assert extract_resp.status_code == 400, f"Expected 400, got {extract_resp.status_code}"
        assert "Failed to parse PDF" in extract_resp.text or "Extraction failed" in extract_resp.text
        
        # Verify status set to Failed in DB
        details_resp = requests.get(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=admin_headers)
        assert details_resp.json()["status"] == "Failed"
        print("[OK] Corrupted PDF file correctly rejected with HTTP 400 and status set to Failed")
    finally:
        os.remove(f_name)

    # 6. Test missing physical file
    print("\n[Test 5] Extract text from document with missing file on disk...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"some content")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("missing.txt", file_bytes, "text/plain")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        doc_id = doc_data["id"]
        stored_path = doc_data["stored_path"]

        # Delete the file inside backend container
        filename_part = os.path.basename(stored_path)
        print(f"[Setup] Deleting container file {filename_part}...")
        if os.path.exists("/workspace"):
            os.remove(f"/workspace/uploads/{filename_part}")
        else:
            subprocess.run(
                ["docker", "compose", "exec", "backend", "rm", f"/workspace/uploads/{filename_part}"],
                cwd="c:\\Users\\Abrakant\\OneDrive\\Documents\\Projects\\AI Customer Support using RAG"
            )

        # Call extraction endpoint (should fail with HTTP 404)
        extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/extract", headers=admin_headers)
        print(f"Status Code: {extract_resp.status_code}")
        print(f"Response: {extract_resp.text}")
        assert extract_resp.status_code == 404, f"Expected 404, got {extract_resp.status_code}"
        assert "missing from storage" in extract_resp.text or "missing" in extract_resp.text
        print("[OK] Missing file on disk correctly rejected with HTTP 404")
    finally:
        os.remove(f_name)

    # 7. Test soft-deleted document
    print("\n[Test 6] Extract text from soft-deleted document...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"soft delete test content")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("deleted_test.txt", file_bytes, "text/plain")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                headers=admin_headers
            )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # Delete document metadata (soft-delete)
        delete_resp = requests.delete(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=admin_headers)
        assert delete_resp.status_code == 200

        # Call extraction endpoint (should fail with HTTP 404)
        extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{doc_id}/extract", headers=admin_headers)
        print(f"Status Code: {extract_resp.status_code}")
        print(f"Response: {extract_resp.text}")
        assert extract_resp.status_code == 404, f"Expected 404, got {extract_resp.status_code}"
        print("[OK] Soft-deleted document correctly rejected with HTTP 404")
    finally:
        os.remove(f_name)

    # 8. Test missing database document
    print("\n[Test 7] Extract text from non-existent document ID...")
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    extract_resp = requests.post(f"{BASE_URL}/api/v1/documents/{fake_uuid}/extract", headers=admin_headers)
    print(f"Status Code: {extract_resp.status_code}")
    assert extract_resp.status_code == 404, f"Expected 404, got {extract_resp.status_code}"
    print("[OK] Non-existent document correctly rejected with HTTP 404")

    print("\n=== ALL SPRINT 4 EXTRACTION INTEGRATION TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] EXTRACTION INTEGRATION TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)
