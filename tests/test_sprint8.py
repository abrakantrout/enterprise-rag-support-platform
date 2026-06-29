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
from app.database.chroma import get_chroma_client

client = TestClient(app)

def get_db_session():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
    if "db:5432" in db_url and not os.path.exists("/workspace"):
        db_url = db_url.replace("db:5432", "localhost:5432")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

class TestSprint8Indexing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.bootstrap_email = "admin@enterprise.com"
        cls.admin_email = "sprint8_admin@enterprise.com"
        cls.agent_email = "sprint8_agent@enterprise.com"
        cls.customer_email = "sprint8_customer@enterprise.com"

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

        # 2. Register Sprint 8 Admin using bootstrap admin headers
        client.post("/api/v1/auth/register", json={
            "email": cls.admin_email,
            "password": cls.password,
            "first_name": "Sprint8",
            "last_name": "Admin",
            "role": "Administrator"
        }, headers=bootstrap_headers)
        
        # Login Sprint 8 Admin to get headers
        login_resp = client.post("/api/v1/auth/login", data={"username": cls.admin_email, "password": cls.password})
        cls.admin_token = login_resp.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 3. Register Agent via API
        client.post("/api/v1/auth/register", json={
            "email": cls.agent_email,
            "password": cls.password,
            "first_name": "Sprint8",
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
            "first_name": "Sprint8",
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

        cls.chroma_client = get_chroma_client()

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
        self.original_api_key = settings.google_api_key
        settings.google_api_key = "mock-google-key"

    def tearDown(self):
        settings.google_api_key = self.original_api_key

    def test_unauthorized_request(self):
        """Test unauthorized request returns 401."""
        resp = client.post("/api/v1/documents/some-uuid/index")
        self.assertEqual(resp.status_code, 401)

    def test_forbidden_role(self):
        """Test forbidden role (e.g. Customer) returns 403."""
        resp = client.post("/api/v1/documents/some-uuid/index", headers=self.customer_headers)
        self.assertEqual(resp.status_code, 403)

    def test_document_with_no_chunks(self):
        """Test document with no chunks returns 400."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Temp doc content")
            f_name = f.name
        
        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("no_chunks.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            self.assertEqual(upload_resp.status_code, 201)
            doc_id = upload_resp.json()["id"]

            # Index it immediately (without chunks)
            resp = client.post(f"/api/v1/documents/{doc_id}/index", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Document has no chunks", resp.json()["detail"])
        finally:
            os.remove(f_name)

    def test_chunks_without_embeddings(self):
        """Test chunks without embeddings return 400."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Content to chunk but not embed.")
            f_name = f.name

        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("no_embeddings.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]

            # Chunk the document to persist chunks in DB (status defaults to Pending)
            chunk_resp = client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)
            self.assertEqual(chunk_resp.status_code, 200)

            # Try to index without embeddings
            resp = client.post(f"/api/v1/documents/{doc_id}/index", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("do not have completed embeddings", resp.json()["detail"])
        finally:
            os.remove(f_name)

    def test_successful_indexing_and_idempotency(self):
        """Test successful mocked vector indexing and idempotency verification."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Line one of knowledge source.\n\nLine two has additional knowledge.")
            f_name = f.name

        try:
            # 1. Upload
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("knowledge.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]

            # 2. Chunk
            client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)

            # 3. Generate Embeddings
            client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)

            # 4. Index Chunks
            resp = client.post(f"/api/v1/documents/{doc_id}/index", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 200)

            data = resp.json()
            self.assertEqual(data["document_id"], doc_id)
            self.assertEqual(data["chunks_indexed"], 1)
            self.assertEqual(data["failed_chunks"], 0)
            self.assertEqual(data["collection_name"], settings.chroma_collection_name)
            self.assertEqual(data["status"], "Completed")

            # Verify PostgreSQL database status columns
            db = get_db_session()
            chunks_in_db = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
            self.assertEqual(len(chunks_in_db), 1)
            for chunk in chunks_in_db:
                self.assertEqual(chunk.indexed_status, "Completed")
                self.assertEqual(chunk.vector_id, chunk.id)
                self.assertIsNotNone(chunk.indexed_at)
            db.close()

            # Verify ChromaDB contains the collection and records
            collection = self.chroma_client.get_collection(name=settings.chroma_collection_name)
            self.assertIsNotNone(collection)
            
            # Fetch by ID to confirm records exist
            results = collection.get(ids=[chunks_in_db[0].id])
            self.assertEqual(len(results["ids"]), 1)
            self.assertEqual(results["ids"][0], chunks_in_db[0].id)
            self.assertEqual(results["documents"][0], chunks_in_db[0].chunk_text)
            self.assertEqual(results["metadatas"][0]["document_id"], doc_id)

            # --- IDEMPOTENCY CHECK ---
            # Call indexing endpoint again
            resp_dup = client.post(f"/api/v1/documents/{doc_id}/index", headers=self.admin_headers)
            self.assertEqual(resp_dup.status_code, 200)

            # Confirm counts remain correct and records are replaced, not duplicated
            results_dup = collection.get(ids=[chunks_in_db[0].id])
            self.assertEqual(len(results_dup["ids"]), 1)
            
            # Count the total matching document_id in collection
            doc_results = collection.get(where={"document_id": doc_id})
            self.assertEqual(len(doc_results["ids"]), 1)

        finally:
            os.remove(f_name)

    def test_chromadb_failure_handling(self):
        """Test ChromaDB failure is handled cleanly (statuses marked Failed, returns 500)."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Failure test knowledge content.")
            f_name = f.name

        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("fail_index.txt", file_bytes, "text/plain")},
                    headers=self.admin_headers
                )
            doc_id = upload_resp.json()["id"]

            client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.admin_headers)
            client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.admin_headers)

            # Mock VectorIndexingService.index_chunks to raise a VectorIndexingError
            from app.services.vector_indexing_service import VectorIndexingService, VectorIndexingError
            with patch.object(
                VectorIndexingService,
                'index_chunks',
                side_effect=VectorIndexingError("Simulated ChromaDB outage")
            ):
                resp = client.post(f"/api/v1/documents/{doc_id}/index", headers=self.admin_headers)
                self.assertEqual(resp.status_code, 500)
                self.assertIn("Vector indexing failed", resp.json()["detail"])

            # Verify PostgreSQL statuses are updated to Failed
            db = get_db_session()
            chunks_in_db = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
            for chunk in chunks_in_db:
                self.assertEqual(chunk.indexed_status, "Failed")
            db.close()
        finally:
            os.remove(f_name)

if __name__ == "__main__":
    unittest.main()
