import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path to allow importing app and models
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app
from app.core.config import settings
from app.database.models import Document, DocumentChunk, User, Role
from app.database.connection import get_db

client = TestClient(app)

def get_db_session():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
    if "db:5432" in db_url and not os.path.exists("/workspace"):
        db_url = db_url.replace("db:5432", "localhost:5432")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

class TestSprint7Embeddings(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.bootstrap_email = "admin@enterprise.com"
        cls.admin_email = "sprint7_admin@enterprise.com"
        cls.agent_email = "sprint7_agent@enterprise.com"
        cls.customer_email = "sprint7_customer@enterprise.com"

        # 1. Login as bootstrap admin or register them if clean DB
        login_resp = client.post("/api/v1/auth/login", data={"username": cls.bootstrap_email, "password": cls.password})
        if login_resp.status_code == 401:
            client.post("/api/v1/auth/register", json={
                "email": cls.bootstrap_email,
                "password": cls.password,
                "first_name": "System",
                "last_name": "Admin",
                "role": "Administrator"
            })
            login_resp = client.post("/api/v1/auth/login", data={"username": cls.bootstrap_email, "password": cls.password})

        bootstrap_token = login_resp.json()["access_token"]
        bootstrap_headers = {"Authorization": f"Bearer {bootstrap_token}"}

        # 2. Register Sprint 7 Admin using bootstrap admin headers
        client.post("/api/v1/auth/register", json={
            "email": cls.admin_email,
            "password": cls.password,
            "first_name": "Sprint7",
            "last_name": "Admin",
            "role": "Administrator"
        }, headers=bootstrap_headers)
        
        # Login Sprint 7 Admin to get headers
        login_resp = client.post("/api/v1/auth/login", data={"username": cls.admin_email, "password": cls.password})
        cls.admin_token = login_resp.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 3. Register Agent via API
        client.post("/api/v1/auth/register", json={
            "email": cls.agent_email,
            "password": cls.password,
            "first_name": "Sprint7",
            "last_name": "Agent",
            "role": "Support Agent"
        }, headers=cls.admin_headers)

        # Login Agent to get headers
        login_resp = client.post("/api/v1/auth/login", data={"username": cls.agent_email, "password": cls.password})
        cls.agent_token = login_resp.json()["access_token"]
        cls.agent_headers = {"Authorization": f"Bearer {cls.agent_token}"}

        # 4. Register Customer via API as Support Agent first
        client.post("/api/v1/auth/register", json={
            "email": cls.customer_email,
            "password": cls.password,
            "first_name": "Sprint7",
            "last_name": "Customer",
            "role": "Support Agent"
        }, headers=cls.admin_headers)

        # 5. Retrieve Customer user from DB and modify their role to "Customer"
        cls.customer_user_record = cls.db.query(User).filter(User.email == cls.customer_email).first()
        assert cls.customer_user_record is not None

        cls.customer_role = cls.db.query(Role).filter(Role.name == "Customer").first()
        if not cls.customer_role:
            import uuid
            cls.customer_role = Role(id=str(uuid.uuid4()), name="Customer")
            cls.db.add(cls.customer_role)
            cls.db.flush()

        cls.customer_user_record.role_id = cls.customer_role.id
        cls.db.commit()

        # Login Customer to get headers
        login_resp = client.post("/api/v1/auth/login", data={"username": cls.customer_email, "password": cls.password})
        cls.customer_token = login_resp.json()["access_token"]
        cls.customer_headers = {"Authorization": f"Bearer {cls.customer_token}"}

    @classmethod
    def tearDownClass(cls):
        # Delete documents uploaded by test users first to avoid NotNullViolation on uploader_id
        admin_u = cls.db.query(User).filter(User.email == cls.admin_email).first()
        agent_u = cls.db.query(User).filter(User.email == cls.agent_email).first()
        cust_u = cls.db.query(User).filter(User.email == cls.customer_email).first()
        
        user_ids = []
        if admin_u: user_ids.append(admin_u.id)
        if agent_u: user_ids.append(agent_u.id)
        if cust_u: user_ids.append(cust_u.id)
        
        if user_ids:
            cls.db.query(Document).filter(Document.uploader_id.in_(user_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # Now safely delete test users
        if admin_u:
            cls.db.delete(admin_u)
        if agent_u:
            cls.db.delete(agent_u)
        if cust_u:
            cls.db.delete(cust_u)
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        # Save original API key
        self.original_api_key = settings.google_api_key

    def tearDown(self):
        # Restore original API key
        settings.google_api_key = self.original_api_key

    def test_unauthorized_request(self):
        """Test unauthorized request returns 401."""
        resp = client.post("/api/v1/documents/some-uuid/embeddings")
        self.assertEqual(resp.status_code, 401)

    def test_forbidden_role(self):
        """Test forbidden role (e.g. Customer) returns 403."""
        resp = client.post("/api/v1/documents/some-uuid/embeddings", headers=self.customer_headers)
        self.assertEqual(resp.status_code, 403)

    def test_missing_document(self):
        """Test missing document ID returns 404."""
        resp = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000000/embeddings", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Document not found", resp.json()["detail"])

    def test_document_with_no_chunks(self):
        """Test document with no chunks returns 400."""
        # Create a document without chunks
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"No chunks yet")
            f_name = f.name
        
        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("no_chunks.txt", file_bytes, "text/plain")},
                    data={"category": "Test", "visibility": "public"},
                    headers=self.admin_headers
                )
            self.assertEqual(upload_resp.status_code, 201)
            doc_id = upload_resp.json()["id"]

            # Try generating embeddings immediately (before chunking)
            settings.google_api_key = "mock-google-key"
            resp = client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Document has no chunks", resp.json()["detail"])
        finally:
            os.remove(f_name)

    def test_missing_api_key(self):
        """Test missing API key behavior returns 400."""
        # Create doc and chunk it
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Sample chunkable content")
            f_name = f.name
        
        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test_missing_key.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]
            
            # Chunk the document to persist chunks in DB
            chunk_resp = client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)
            self.assertEqual(chunk_resp.status_code, 200)

            # Now set API key to empty and call embedding endpoint
            settings.google_api_key = ""
            resp = client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Google API key is missing or not configured", resp.json()["detail"])
        finally:
            os.remove(f_name)

    def test_successful_mocked_embedding_generation(self):
        """Test successful mocked embedding generation and database verification."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Valid paragraph content for chunking. This will generate chunks.\n\nSecond paragraph content.")
            f_name = f.name

        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("mocked_success.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]

            # Chunk it
            chunk_resp = client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)
            self.assertEqual(chunk_resp.status_code, 200)

            # Set mock API key
            settings.google_api_key = "mock-google-key"
            resp = client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 200)

            data = resp.json()
            self.assertEqual(data["document_id"], doc_id)
            self.assertEqual(data["total_chunks"], 1)
            self.assertEqual(data["embeddings_generated"], 1)
            self.assertEqual(data["failed_chunks"], 0)
            self.assertEqual(data["status"], "Completed")

            # Verify PostgreSQL database columns directly
            db = get_db_session()
            chunks_in_db = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
            self.assertEqual(len(chunks_in_db), 1)
            for chunk in chunks_in_db:
                self.assertEqual(chunk.embedding_status, "Completed")
                self.assertEqual(chunk.embedding_model, settings.embedding_model)
                self.assertIsNotNone(chunk.embedded_at)
            db.close()
        finally:
            os.remove(f_name)

    def test_provider_failure_handling(self):
        """Test provider failure handling (marked as Failed, returns 500)."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Content for failure test.")
            f_name = f.name

        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("mocked_failure.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]

            # Chunk it
            client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)

            # Set fail API key
            settings.google_api_key = "fail-google-key"
            resp = client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 500)
            self.assertIn("Embedding generation failed", resp.json()["detail"])

            # Verify status is updated to Failed in database
            db = get_db_session()
            chunks_in_db = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
            for chunk in chunks_in_db:
                self.assertEqual(chunk.embedding_status, "Failed")
            db.close()
        finally:
            os.remove(f_name)

    def test_real_provider_conditional(self):
        """Optional manual test path for real API verification if a valid GOOGLE_API_KEY is configured."""
        real_key = os.getenv("REAL_GOOGLE_API_KEY", "")
        if not real_key or real_key.startswith("mock-") or real_key.startswith("fail-"):
            print("\n[Skipped] Real Gemini API test skipped (REAL_GOOGLE_API_KEY not set).")
            return

        print("\n[Run] Executing optional real Gemini API test...")
        settings.google_api_key = real_key

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Real API embedding test content.")
            f_name = f.name

        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("real_api_test.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]
            client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)

            resp = client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 200)
            print("[OK] Real Gemini API embedding verification succeeded.")
        finally:
            os.remove(f_name)

if __name__ == "__main__":
    unittest.main()
