import os
import sys
import tempfile
import requests
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path to allow importing models for direct DB verification
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database.models import DocumentChunk, DocumentVersion, Document

BASE_URL = "http://127.0.0.1:8000"

def get_db_session():
    # Use DATABASE_URL from env or default to container url
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
    # If running from host, we might need to map "db" to localhost if resolving is local
    if "db:5432" in db_url and not os.path.exists("/workspace"):
        db_url = db_url.replace("db:5432", "localhost:5432")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def run_tests():
    print("=== STARTING SPRINT 6 CHUNK PERSISTENCE API INTEGRATION TESTS ===")

    # 1. SETUP - Authenticate Admin and Agent
    admin_email = "admin@enterprise.com"
    password = "SecurePassword123"

    print("\n[Setup] Authenticating Administrator...")
    login_data = {"username": admin_email, "password": password}
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    if resp.status_code == 401:
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

    db_session = get_db_session()

    # --- TEST CASE 1: Persist chunks for valid TXT document ---
    print("\n[Test 1] Persist chunks for valid TXT document...")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        txt_content = (
            "Paragraph one text in TXT format. This fits inside chunking parameters.\n\n"
            "Paragraph two text has more details and will follow paragraph one in the chunking result."
        )
        f.write(txt_content.encode("utf-8"))
        f_name = f.name

    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("sprint6_test.txt", file_bytes, "text/plain")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test", "visibility": "public"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201, f"TXT Upload failed: {upload_resp.text}"
        txt_doc_id = upload_resp.json()["id"]

        # Call the chunks persistence endpoint
        chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{txt_doc_id}/chunks", headers=agent_headers)
        print(f"Status Code: {chunks_resp.status_code}")
        print(f"Response: {chunks_resp.json()}")
        assert chunks_resp.status_code == 200
        
        data = chunks_resp.json()
        assert data["document_id"] == txt_doc_id
        assert data["chunks_created"] > 0
        assert data["status"] == "Completed"
        print("[OK] TXT document chunks persistence succeeded")
    finally:
        os.remove(f_name)

    # --- TEST CASE 2: Persist chunks for valid PDF document ---
    print("\n[Test 2] Persist chunks for valid PDF document...")
    # Generate PDF using PyMuPDF helper if available
    pdf_path = os.path.join(tempfile.gettempdir(), "sprint6_test.pdf")
    try:
        import fitz
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"])
        import fitz
    
    doc_fitz = fitz.open()
    page = doc_fitz.new_page()
    page.insert_text((50, 50), "PDF text page 1. This contains documentation content for testing.")
    page2 = doc_fitz.new_page()
    page2.insert_text((50, 50), "PDF text page 2. Additional data on this second page.")
    doc_fitz.save(pdf_path)
    doc_fitz.close()

    try:
        with open(pdf_path, "rb") as file_bytes:
            files = {"file": ("sprint6_test.pdf", file_bytes, "application/pdf")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                data={"category": "Test", "visibility": "public"},
                headers=admin_headers
            )
        assert upload_resp.status_code == 201, f"PDF Upload failed: {upload_resp.text}"
        pdf_doc_id = upload_resp.json()["id"]

        # Call the chunks persistence endpoint
        chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{pdf_doc_id}/chunks", headers=admin_headers)
        print(f"Status Code: {chunks_resp.status_code}")
        print(f"Response: {chunks_resp.json()}")
        assert chunks_resp.status_code == 200
        
        data = chunks_resp.json()
        assert data["document_id"] == pdf_doc_id
        assert data["chunks_created"] > 0
        print("[OK] PDF document chunks persistence succeeded")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    # --- TEST CASE 3: Chunk rows exist in PostgreSQL ---
    print("\n[Test 3] Verify chunk rows exist in PostgreSQL database...")
    # Query database directly using SQLAlchemy
    chunks_in_db = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == txt_doc_id).all()
    print(f"Found {len(chunks_in_db)} chunks in DB for document {txt_doc_id}")
    assert len(chunks_in_db) > 0, "No chunks found in DB"
    
    # Check fields are populated
    for chunk in chunks_in_db:
        assert chunk.id is not None
        assert chunk.document_id == txt_doc_id
        assert chunk.version_id is not None
        assert chunk.chunk_text is not None and len(chunk.chunk_text) > 0
        assert chunk.character_count == len(chunk.chunk_text)
        assert chunk.chunk_index is not None
        assert chunk.page_number is not None
        assert chunk.start_offset is not None
        assert chunk.end_offset is not None
        assert chunk.created_at is not None
    print("[OK] Chunk rows correctly verify in PostgreSQL with complete data schema")

    # --- TEST CASE 4: Re-running chunk persistence does not duplicate chunks ---
    print("\n[Test 4] Verify re-running chunk persistence does not duplicate chunks...")
    initial_count = len(chunks_in_db)
    
    # Re-run persistence
    chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{txt_doc_id}/chunks", headers=admin_headers)
    assert chunks_resp.status_code == 200
    
    # Query DB again
    post_count = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == txt_doc_id).count()
    print(f"Initial count: {initial_count}, post count: {post_count}")
    assert post_count == initial_count, f"Duplicate chunks detected! Expected {initial_count}, found {post_count}"
    print("[OK] Idempotency rule verified: old chunks deleted and fresh count remains correct")

    # --- TEST CASE 5: Deleted document cannot be chunked ---
    print("\n[Test 5] Verify deleted document cannot be chunked...")
    # Soft delete the TXT document
    delete_resp = requests.delete(f"{BASE_URL}/api/v1/documents/{txt_doc_id}", headers=admin_headers)
    assert delete_resp.status_code == 200
    
    # Try chunking it
    chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{txt_doc_id}/chunks", headers=admin_headers)
    print(f"Status Code: {chunks_resp.status_code}")
    print(f"Response: {chunks_resp.text}")
    assert chunks_resp.status_code == 404, f"Expected 404, got {chunks_resp.status_code}"
    print("[OK] Deleted document chunking correctly rejected with HTTP 404")

    # --- TEST CASE 6: Missing physical file returns proper error ---
    print("\n[Test 6] Verify missing physical file returns proper error...")
    # Create document
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"file content")
        f_name = f.name
    try:
        with open(f_name, "rb") as file_bytes:
            files = {"file": ("missing_physical.txt", file_bytes, "text/plain")}
            upload_resp = requests.post(
                f"{BASE_URL}/api/v1/documents/upload",
                files=files,
                headers=admin_headers
            )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        missing_doc_id = doc_data["id"]
        stored_path = doc_data["stored_path"]

        # Delete physical file directly
        filename_part = os.path.basename(stored_path)
        print(f"[Setup] Deleting container file {filename_part}...")
        if os.path.exists("/workspace"):
            os.remove(f"/workspace/uploads/{filename_part}")
        else:
            # Fallback if run on host
            uploads_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "uploads")
            os.remove(os.path.join(uploads_dir, filename_part))

        # Call chunking persistence endpoint
        chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{missing_doc_id}/chunks", headers=admin_headers)
        print(f"Status Code: {chunks_resp.status_code}")
        print(f"Response: {chunks_resp.text}")
        assert chunks_resp.status_code == 404
        
        # Verify status set to Failed in DB
        db_doc = db_session.query(Document).filter(Document.id == missing_doc_id).first()
        assert db_doc.status == "Failed"
        print("[OK] Missing file correctly rejected with HTTP 404 and status set to Failed")
    finally:
        if os.path.exists(f_name):
            os.remove(f_name)

    # --- TEST CASE 7: Unauthorized request returns 401 ---
    print("\n[Test 7] Verify unauthorized request returns 401...")
    chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{pdf_doc_id}/chunks") # no auth headers
    print(f"Status Code: {chunks_resp.status_code}")
    assert chunks_resp.status_code == 401
    print("[OK] Unauthenticated request correctly rejected with HTTP 401")

    # --- TEST CASE 8: Forbidden role returns 403 if applicable ---
    print("\n[Test 8] Verify forbidden role returns 403...")
    temp_email = "customer@enterprise.com"
    print("[Setup] Creating temporary user to modify role in DB...")
    # First register user as agent
    reg_payload = {
        "email": temp_email,
        "password": password,
        "first_name": "Test",
        "last_name": "Customer",
        "role": "Support Agent"
    }
    requests.post(f"{BASE_URL}/api/v1/auth/register", json=reg_payload, headers=admin_headers)
    
    # Get user and update role to something else
    from app.database.models import User, Role
    user_record = db_session.query(User).filter(User.email == temp_email).first()
    assert user_record is not None
    
    # Create or find a Customer role
    customer_role = db_session.query(Role).filter(Role.name == "Customer").first()
    if not customer_role:
        import uuid
        customer_role = Role(id=str(uuid.uuid4()), name="Customer")
        db_session.add(customer_role)
        db_session.flush()
    
    user_record.role_id = customer_role.id
    db_session.commit()
    print("[Setup] Temporary user updated to 'Customer' role")
    
    # Now log in as Customer
    temp_login = {"username": temp_email, "password": password}
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=temp_login)
    assert resp.status_code == 200
    customer_token = resp.json()["access_token"]
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    
    # Call chunking endpoint
    chunks_resp = requests.post(f"{BASE_URL}/api/v1/documents/{pdf_doc_id}/chunks", headers=customer_headers)
    print(f"Status Code: {chunks_resp.status_code}")
    print(f"Response: {chunks_resp.text}")
    assert chunks_resp.status_code == 403
    print("[OK] Forbidden role correctly rejected with HTTP 403")

    # Clean up customer user
    db_session.delete(user_record)
    db_session.commit()

    db_session.close()
    print("\n=== ALL SPRINT 6 CHUNK PERSISTENCE TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] TEST ASSERTION FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)
