import os
import sys
import tempfile
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=== STARTING SPRINT 3 DOCUMENT UPLOAD API INTEGRATION TESTS ===")

    # 1. SETUP - Authenticate Admin
    admin_email = "admin@enterprise.com"
    password = "SecurePassword123"

    print("\n[Setup] Authenticating Administrator...")
    login_data = {"username": admin_email, "password": password}
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    if resp.status_code == 401:
        # If user doesn't exist, bootstrap the first administrator
        print("[Setup] Admin user not found. Bootstrapping first Administrator...")
        register_payload = {
            "email": admin_email,
            "password": password,
            "first_name": "System",
            "last_name": "Admin",
            "role": "Administrator"
        }
        resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_payload)
        assert resp.status_code == 201, f"Failed to bootstrap Admin: {resp.text}"
        resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)

    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    admin_token = resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[Setup] Administrator authenticated successfully")

    # 2. SETUP - Authenticate Support Agent
    agent_email = "agent@enterprise.com"
    print("\n[Setup] Authenticating Support Agent...")
    agent_login_data = {"username": agent_email, "password": password}
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=agent_login_data)
    if resp.status_code == 401:
        print("[Setup] Agent user not found. Registering Support Agent...")
        register_payload = {
            "email": agent_email,
            "password": password,
            "first_name": "Support",
            "last_name": "Agent",
            "role": "Support Agent"
        }
        resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_payload, headers=admin_headers)
        assert resp.status_code == 201, f"Failed to register Support Agent: {resp.text}"
        resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=agent_login_data)

    assert resp.status_code == 200, f"Support Agent login failed: {resp.text}"
    agent_token = resp.json()["access_token"]
    agent_headers = {"Authorization": f"Bearer {agent_token}"}
    print("[Setup] Support Agent authenticated successfully")

    # --- TEST CASES ---

    # Test 1: Upload without authentication
    print("\n[Test 1] Upload file without authentication...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"Hello World")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("test.txt", file_bytes, "text/plain")}
            resp = requests.post(f"{BASE_URL}/api/v1/documents/upload", files=files, data={"category": "Test"})
        print(f"Status Code: {resp.status_code}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("[OK] Unauthenticated upload correctly rejected with HTTP 401")
    finally:
        os.remove(f_name)

    # Test 2: Upload unsupported file type
    print("\n[Test 2] Upload file with unsupported extension (.png)...")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake png content")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("test.png", file_bytes, "image/png")}
            resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("[OK] Unsupported file extension correctly rejected with HTTP 400")
    finally:
        os.remove(f_name)

    # Test 2b: Upload disguised file (MIME type mismatch)
    print("\n[Test 2b] Upload disguised file (.pdf with text/plain)...")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n%mock content\n%%EOF")
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("disguised.pdf", file_bytes, "text/plain")}
            resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "MIME type" in resp.text, "Expected MIME mismatch detail"
        print("[OK] Disguised file with mismatched MIME type correctly rejected with HTTP 400")
    finally:
        os.remove(f_name)

    # Test 2c: Upload empty file
    print("\n[Test 2c] Upload empty file (0 bytes)...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("empty.txt", file_bytes, "text/plain")}
            resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test"},
                headers=admin_headers
            )
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "Empty" in resp.text, "Expected empty file detail"
        print("[OK] Empty file correctly rejected with HTTP 400")
    finally:
        os.remove(f_name)

    # Test 3: Upload valid TXT file (as Support Agent)
    print("\n[Test 3] Upload valid TXT file as Support Agent...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        txt_content = b"This is a valid text document content for testing Sprint 3."
        f.write(txt_content)
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("manual_policy.txt", file_bytes, "text/plain")}
            resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Policy", "visibility": "internal"},
                headers=agent_headers
            )
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.json()}")
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        doc_data = resp.json()
        assert doc_data["filename"] == "manual_policy.txt", "Filename mismatch"
        assert doc_data["file_type"] == "txt", "File type mismatch"
        assert doc_data["file_size"] == len(txt_content), "File size mismatch"
        assert doc_data["status"] == "Processing", "Status mismatch"
        assert doc_data["visibility"] == "internal", "Visibility mismatch"
        print("[OK] Support Agent uploaded valid TXT file successfully (HTTP 201)")
    finally:
        os.remove(f_name)

    # Test 4: Upload valid PDF file (as Administrator)
    print("\n[Test 4] Upload valid PDF file as Administrator...")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_content = b"%PDF-1.4\n%mock pdf content\n%%EOF"
        f.write(pdf_content)
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("guide.pdf", file_bytes, "application/pdf")}
            resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Guide", "visibility": "public"},
                headers=admin_headers
            )
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.json()}")
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        pdf_doc_data = resp.json()
        pdf_document_id = pdf_doc_data["id"]
        stored_path = pdf_doc_data["stored_path"]
        assert pdf_doc_data["filename"] == "guide.pdf", "Filename mismatch"
        assert pdf_doc_data["file_type"] == "pdf", "File type mismatch"
        assert pdf_doc_data["file_size"] == len(pdf_content), "File size mismatch"
        print("[OK] Administrator uploaded valid PDF file successfully (HTTP 201)")
    finally:
        os.remove(f_name)

    # Test 5: List uploaded documents (as Support Agent)
    print("\n[Test 5] List uploaded documents as Support Agent...")
    resp = requests.get(f"{BASE_URL}/api/v1/documents", params={"page": 1, "size": 10}, headers=agent_headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    list_data = resp.json()
    assert "items" in list_data, "Missing items list"
    assert "pagination" in list_data, "Missing pagination data"
    assert list_data["pagination"]["total_items"] >= 2, "Should find at least 2 uploaded documents"
    print("[OK] Listed documents and verified pagination metadata successfully")

    # Test 6: Get document details (as Support Agent)
    print(f"\n[Test 6] Get document details for ID {pdf_document_id}...")
    resp = requests.get(f"{BASE_URL}/api/v1/documents/{pdf_document_id}", headers=agent_headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    details = resp.json()
    assert details["id"] == pdf_document_id, "ID mismatch"
    assert details["filename"] == "guide.pdf", "Filename mismatch"
    print("[OK] Retrieved document details successfully")

    # Test 7: Delete document without Admin role should fail (as Support Agent)
    print(f"\n[Test 7] Attempting to delete document as Support Agent (should fail)...")
    resp = requests.delete(f"{BASE_URL}/api/v1/documents/{pdf_document_id}", headers=agent_headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    print("[OK] Unauthorized deletion rejected correctly with HTTP 403")

    # Test 8: Delete document as Admin (should succeed)
    print(f"\n[Test 8] Deleting document as Administrator...")
    resp = requests.delete(f"{BASE_URL}/api/v1/documents/{pdf_document_id}", headers=admin_headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # 8.1 Verify soft delete metadata state (should return 404 now)
    resp = requests.get(f"{BASE_URL}/api/v1/documents/{pdf_document_id}", headers=admin_headers)
    assert resp.status_code == 404, f"Expected 404 for deleted document, got {resp.status_code}"
    print("[OK] Document successfully soft-deleted (GET details returns HTTP 404)")

    # 8.2 Verify physical disk path cleanup
    # We check if file is removed inside the Docker container
    print("[Verification] Verifying physical file removal from storage volume...")
    filename_part = os.path.basename(stored_path)
    if os.path.exists("/workspace"):
        uploads_list = os.listdir("/workspace/uploads")
        print(f"Uploads listing:\n{uploads_list}")
        assert filename_part not in uploads_list, f"Physical file {filename_part} was not removed from server storage"
    else:
        # Run command on host to check container uploads directory listing
        result = subprocess.run(
            ["docker", "compose", "exec", "backend", "ls", "/workspace/uploads"],
            capture_output=True,
            text=True,
            cwd="c:\\Users\\Abrakant\\OneDrive\\Documents\\Projects\\AI Customer Support using RAG"
        )
        print(f"Uploads listing:\n{result.stdout}")
        assert filename_part not in result.stdout, f"Physical file {filename_part} was not removed from server storage"
    print("[OK] Physical file was successfully deleted from uploads/ volume on disk")

    print("\n=== ALL SPRINT 3 DOCUMENT UPLOAD API INTEGRATION TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] INTEGRATION TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)
