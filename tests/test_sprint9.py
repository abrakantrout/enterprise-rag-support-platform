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
from app.database.models import Document, DocumentChunk, User, Role, Organization
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

class TestSprint9Retrieval(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.bootstrap_email = "admin@enterprise.com"
        cls.user_a_email = "user_a@orga.com"
        cls.user_b_email = "user_b@orgb.com"

        # 1. Clean ChromaDB collection first
        cls.chroma_client = get_chroma_client()
        try:
            cls.chroma_client.delete_collection(name=settings.chroma_collection_name)
        except Exception:
            pass

        # 2. Clean existing database records
        # Delete old users and orgs to trigger cascades
        cls.db.query(User).filter(User.email.in_([cls.user_a_email, cls.user_b_email])).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name.in_(["Org A", "Org B"])).delete(synchronize_session=False)
        cls.db.commit()

        # 3. Login as bootstrap admin or register them if clean DB
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

        # 4. Register User A and User B via API (both register under default org first)
        client.post("/api/v1/auth/register", json={
            "email": cls.user_a_email,
            "password": cls.password,
            "first_name": "User",
            "last_name": "A",
            "role": "Administrator"
        }, headers=bootstrap_headers)

        client.post("/api/v1/auth/register", json={
            "email": cls.user_b_email,
            "password": cls.password,
            "first_name": "User",
            "last_name": "B",
            "role": "Administrator"
        }, headers=bootstrap_headers)

        # 5. Create separate Organizations: Org A and Org B in database
        import uuid
        cls.org_a = Organization(id=str(uuid.uuid4()), name="Org A")
        cls.org_b = Organization(id=str(uuid.uuid4()), name="Org B")
        cls.db.add_all([cls.org_a, cls.org_b])
        cls.db.commit()

        # 6. Link User A to Org A, and User B to Org B in DB
        cls.user_a_rec = cls.db.query(User).filter(User.email == cls.user_a_email).first()
        cls.user_a_rec.organization_id = cls.org_a.id

        cls.user_b_rec = cls.db.query(User).filter(User.email == cls.user_b_email).first()
        cls.user_b_rec.organization_id = cls.org_b.id

        cls.db.commit()

        # 7. Authenticate both users to get their specific org headers
        resp_a = client.post("/api/v1/auth/login", data={"username": cls.user_a_email, "password": cls.password})
        cls.token_a = resp_a.json()["access_token"]
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        resp_b = client.post("/api/v1/auth/login", data={"username": cls.user_b_email, "password": cls.password})
        cls.token_b = resp_b.json()["access_token"]
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    @classmethod
    def tearDownClass(cls):
        # Clean up documents uploaded by test users
        admin_u = cls.db.query(User).filter(User.email == cls.user_a_email).first()
        agent_u = cls.db.query(User).filter(User.email == cls.user_b_email).first()

        user_ids = []
        if admin_u: user_ids.append(admin_u.id)
        if agent_u: user_ids.append(agent_u.id)

        if user_ids:
            cls.db.query(Document).filter(Document.uploader_id.in_(user_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # Clean up test users and organizations
        if admin_u:
            cls.db.delete(admin_u)
        if agent_u:
            cls.db.delete(agent_u)
        cls.db.commit()
        cls.db.query(Organization).filter(Organization.name.in_(["Org A", "Org B"])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        self.original_api_key = settings.google_api_key
        settings.google_api_key = "mock-google-key"
        self.original_min_similarity = settings.min_similarity_score
        settings.min_similarity_score = 0.70

    def tearDown(self):
        settings.google_api_key = self.original_api_key
        settings.min_similarity_score = self.original_min_similarity

    def test_unauthorized_request(self):
        """Test unauthorized search query returns 401."""
        resp = client.post("/api/v1/retrieval/search", json={"query": "hello"})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_jwt_token(self):
        """Test search query with invalid JWT returns 401."""
        resp = client.post(
            "/api/v1/retrieval/search",
            json={"query": "hello"},
            headers={"Authorization": "Bearer invalid_token"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_empty_query(self):
        """Test empty query search parameters return 400 Bad Request."""
        resp = client.post("/api/v1/retrieval/search", json={"query": ""}, headers=self.headers_a)
        self.assertEqual(resp.status_code, 400)

        resp2 = client.post("/api/v1/retrieval/search", json={"query": "    "}, headers=self.headers_a)
        self.assertEqual(resp2.status_code, 400)

    def test_no_matching_chunks(self):
        """Test querying when no records match returning an empty list."""
        resp = client.post("/api/v1/retrieval/search", json={"query": "nonexistent random query"}, headers=self.headers_a)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"], [])

    def test_organization_isolation_and_retrieval(self):
        """Test strict multi-tenant organization isolation (Org A vs Org B)."""
        # Upload, chunk, embed, and index for Org A
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Apple juice is sweet and delicious.")
            f_name_a = f.name
        
        # Upload, chunk, embed, and index for Org B
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Banana bread is warm and soft.")
            f_name_b = f.name

        try:
            # 1. Upload for Org A
            with open(f_name_a, "rb") as file_bytes:
                upload_a = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("apple.txt", file_bytes, "text/plain")},
                    headers=self.headers_a
                )
            doc_a_id = upload_a.json()["id"]
            client.post(f"/api/v1/documents/{doc_a_id}/chunks", headers=self.headers_a)
            client.post(f"/api/v1/documents/{doc_a_id}/embeddings", headers=self.headers_a)
            client.post(f"/api/v1/documents/{doc_a_id}/index", headers=self.headers_a)

            # 2. Upload for Org B
            with open(f_name_b, "rb") as file_bytes:
                upload_b = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("banana.txt", file_bytes, "text/plain")},
                    headers=self.headers_b
                )
            doc_b_id = upload_b.json()["id"]
            client.post(f"/api/v1/documents/{doc_b_id}/chunks", headers=self.headers_b)
            client.post(f"/api/v1/documents/{doc_b_id}/embeddings", headers=self.headers_b)
            client.post(f"/api/v1/documents/{doc_b_id}/index", headers=self.headers_b)

            # 3. Query as User A (Org A)
            # Querying "Apple juice" should return apple.txt chunk and NEVER banana.txt chunk
            resp_a = client.post("/api/v1/retrieval/search", json={"query": "Apple juice"}, headers=self.headers_a)
            self.assertEqual(resp_a.status_code, 200)
            results_a = resp_a.json()["results"]
            self.assertTrue(len(results_a) > 0)
            
            # Verify they all belong to Org A
            for item in results_a:
                self.assertEqual(item["metadata"]["organization_id"], self.org_a.id)
                self.assertEqual(item["document_id"], doc_a_id)
                self.assertIn("Apple juice", item["chunk_text"])

            # 4. Query as User B (Org B)
            # Querying "Apple juice" should return NOTHING (empty list) for Org B
            resp_b = client.post("/api/v1/retrieval/search", json={"query": "Apple juice"}, headers=self.headers_b)
            self.assertEqual(resp_b.status_code, 200)
            self.assertEqual(resp_b.json()["results"], [])

            # Querying "Banana bread" as User B should return banana.txt
            resp_b_banana = client.post("/api/v1/retrieval/search", json={"query": "Banana bread"}, headers=self.headers_b)
            self.assertEqual(resp_b_banana.status_code, 200)
            results_b = resp_b_banana.json()["results"]
            self.assertTrue(len(results_b) > 0)
            for item in results_b:
                self.assertEqual(item["metadata"]["organization_id"], self.org_b.id)
                self.assertEqual(item["document_id"], doc_b_id)
                self.assertIn("Banana bread", item["chunk_text"])

        finally:
            os.remove(f_name_a)
            os.remove(f_name_b)

    def test_similarity_threshold_filtering(self):
        """Test that chunks below min_similarity_score are discarded."""
        # Querying with an extremely high threshold should yield empty results
        settings.min_similarity_score = 0.999
        resp = client.post("/api/v1/retrieval/search", json={"query": "Apple juice"}, headers=self.headers_a)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"], [])

    def test_query_embedding_failure(self):
        """Test query embedding service failures are handled gracefully."""
        from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
        with patch.object(
            EmbeddingService,
            'generate_embeddings',
            side_effect=EmbeddingServiceError("API call timeout")
        ):
            resp = client.post("/api/v1/retrieval/search", json={"query": "Apple juice"}, headers=self.headers_a)
            self.assertEqual(resp.status_code, 500)
            self.assertIn("Semantic retrieval failed", resp.json()["detail"])

    def test_chromadb_outage_handling(self):
        """Test ChromaDB connectivity outage returns 500."""
        from app.services.retrieval_service import RetrievalService, RetrievalError
        with patch.object(
            RetrievalService,
            '_init_client',
            side_effect=RetrievalError("Connection refused by ChromaDB host")
        ):
            resp = client.post("/api/v1/retrieval/search", json={"query": "Apple juice"}, headers=self.headers_a)
            self.assertEqual(resp.status_code, 500)
            self.assertIn("Semantic retrieval failed", resp.json()["detail"])

if __name__ == "__main__":
    unittest.main()
