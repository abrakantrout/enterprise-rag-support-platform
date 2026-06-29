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
from app.services.gemini_service import GeminiService, GeminiServiceError, GeminiTimeoutError
from app.services.retrieval_service import RetrievalService, RetrievalError
from app.services.prompt_builder_service import PromptBuilderService

client = TestClient(app)

def get_db_session():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
    if "db:5432" in db_url and not os.path.exists("/workspace"):
        db_url = db_url.replace("db:5432", "localhost:5432")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

class TestSprint11GroundedAnswers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.bootstrap_email = "admin@enterprise.com"
        cls.user_a_email = "user_a_s11@orga.com"
        cls.user_b_email = "user_b_s11@orgb.com"

        # 1. Clean ChromaDB collection first
        cls.chroma_client = get_chroma_client()
        try:
            cls.chroma_client.delete_collection(name=settings.chroma_collection_name)
        except Exception:
            pass

        # 2. Clean existing database records
        cls.db.query(User).filter(User.email.in_([cls.user_a_email, cls.user_b_email])).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name.in_(["Org S11 A", "Org S11 B"])).delete(synchronize_session=False)
        cls.db.commit()

        # 3. Create bootstrap admin
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

        # 4. Register User A and User B
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
            "role": "Support Agent"
        }, headers=bootstrap_headers)

        # 5. Create Organizations
        import uuid
        cls.org_a = Organization(id=str(uuid.uuid4()), name="Org S11 A")
        cls.org_b = Organization(id=str(uuid.uuid4()), name="Org S11 B")
        cls.db.add_all([cls.org_a, cls.org_b])
        cls.db.commit()

        # 6. Link users
        cls.user_a_rec = cls.db.query(User).filter(User.email == cls.user_a_email).first()
        cls.user_a_rec.organization_id = cls.org_a.id

        cls.user_b_rec = cls.db.query(User).filter(User.email == cls.user_b_email).first()
        cls.user_b_rec.organization_id = cls.org_b.id

        cls.db.commit()

        # 7. Authenticate users
        resp_a = client.post("/api/v1/auth/login", data={"username": cls.user_a_email, "password": cls.password})
        cls.token_a = resp_a.json()["access_token"]
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        resp_b = client.post("/api/v1/auth/login", data={"username": cls.user_b_email, "password": cls.password})
        cls.token_b = resp_b.json()["access_token"]
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    @classmethod
    def tearDownClass(cls):
        admin_u = cls.db.query(User).filter(User.email == cls.user_a_email).first()
        agent_u = cls.db.query(User).filter(User.email == cls.user_b_email).first()

        user_ids = []
        if admin_u: user_ids.append(admin_u.id)
        if agent_u: user_ids.append(agent_u.id)

        if user_ids:
            cls.db.query(Document).filter(Document.uploader_id.in_(user_ids)).delete(synchronize_session=False)
            cls.db.commit()

        if admin_u:
            cls.db.delete(admin_u)
        if agent_u:
            cls.db.delete(agent_u)
        cls.db.commit()
        cls.db.query(Organization).filter(Organization.name.in_(["Org S11 A", "Org S11 B"])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        self.original_api_key = settings.google_api_key
        self.original_gemini_key = settings.gemini_api_key
        self.original_min_similarity = settings.min_similarity_score
        settings.google_api_key = "mock-google-key"
        settings.gemini_api_key = "mock-gemini-key"
        settings.min_similarity_score = -2.0

    def tearDown(self):
        settings.google_api_key = self.original_api_key
        settings.gemini_api_key = self.original_gemini_key
        settings.min_similarity_score = self.original_min_similarity

    def test_unauthorized_request(self):
        """Test chat answer query without auth headers returns 401."""
        resp = client.post("/api/v1/chat/answer", json={"question": "What is the refund policy?"})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_jwt_token(self):
        """Test chat answer query with invalid JWT returns 401."""
        resp = client.post(
            "/api/v1/chat/answer",
            json={"question": "What is the refund policy?"},
            headers={"Authorization": "Bearer invalid_token"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_successful_grounded_answer_and_sources_included(self):
        """Test successful grounded answer pipeline and check sources are mapped correctly."""
        # 1. Upload a document for Org A (User A)
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"The refund policy allows you to request a full refund within 30 days of purchase.")
            f_name = f.name

        try:
            with open(f_name, "rb") as file_bytes:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("RefundPolicy.txt", file_bytes, "text/plain")},
                    headers=self.headers_a
                )
            doc_id = upload_resp.json()["id"]
            
            # Extract, chunk, embed, and index
            client.post(f"/api/v1/documents/{doc_id}/chunks", headers=self.headers_a)
            client.post(f"/api/v1/documents/{doc_id}/embeddings", headers=self.headers_a)
            client.post(f"/api/v1/documents/{doc_id}/index", headers=self.headers_a)

            # 2. Query grounded answer
            resp = client.post(
                "/api/v1/chat/answer",
                json={"question": "What is the refund policy?"},
                headers=self.headers_a
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("refund", data["answer"].lower())
            self.assertEqual(data["retrieval_count"], 1)
            
            # 3. Sources included check
            self.assertTrue(len(data["sources"]) > 0)
            self.assertEqual(data["sources"][0]["document"], "RefundPolicy.txt")
            self.assertIsNotNone(data["sources"][0]["chunk_id"])
            self.assertEqual(data["sources"][0]["page"], 1)

        finally:
            os.remove(f_name)

    def test_no_retrieval_results_bypass_gemini(self):
        """Test that empty retrieval results bypasses Gemini entirely and returns refusal answer."""
        # Querying on User B (Org B) which has no uploaded files
        with patch.object(GeminiService, 'generate_answer') as mock_gemini:
            resp = client.post(
                "/api/v1/chat/answer",
                json={"question": "What is the refund policy?"},
                headers=self.headers_b
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["answer"], "I could not find relevant information in the uploaded documents.")
            self.assertEqual(data["retrieval_count"], 0)
            self.assertEqual(data["sources"], [])
            # Confirm Gemini Service was never called
            mock_gemini.assert_not_called()

    def test_gemini_timeout(self):
        """Test that Gemini timeout raises 500 error and is handled gracefully."""
        # We need retrieval results to trigger Gemini call, so we mock retrieval to return a chunk
        mock_chunks = [{
            "chunk_id": "c1",
            "document_id": "d1",
            "page_number": 1,
            "chunk_index": 0,
            "similarity_score": 0.9,
            "chunk_text": "Sample text",
            "metadata": {"filename": "Sample.pdf", "organization_id": "org1"}
        }]

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', side_effect=GeminiTimeoutError("Request timeout")):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the refund policy?"},
                    headers=self.headers_a
                )
                self.assertEqual(resp.status_code, 500)
                self.assertIn("timeout", resp.json()["detail"].lower())

    def test_gemini_provider_error(self):
        """Test that Gemini provider errors return 500."""
        mock_chunks = [{
            "chunk_id": "c1",
            "document_id": "d1",
            "page_number": 1,
            "chunk_index": 0,
            "similarity_score": 0.9,
            "chunk_text": "Sample text",
            "metadata": {"filename": "Sample.pdf", "organization_id": "org1"}
        }]

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', side_effect=GeminiServiceError("API quota exceeded")):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the refund policy?"},
                    headers=self.headers_a
                )
                self.assertEqual(resp.status_code, 500)
                self.assertIn("provider", resp.json()["detail"].lower())

    def test_missing_api_key(self):
        """Test that missing Gemini API key returns 500."""
        settings.google_api_key = ""
        settings.gemini_api_key = ""

        mock_chunks = [{
            "chunk_id": "c1",
            "document_id": "d1",
            "page_number": 1,
            "chunk_index": 0,
            "similarity_score": 0.9,
            "chunk_text": "Sample text",
            "metadata": {"filename": "Sample.pdf", "organization_id": "org1"}
        }]

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            resp = client.post(
                "/api/v1/chat/answer",
                json={"question": "What is the refund policy?"},
                headers=self.headers_a
            )
            self.assertEqual(resp.status_code, 500)
            self.assertIn("API key is missing", resp.json()["detail"])

    def test_retrieval_failure_graceful_handling(self):
        """Test that retrieval failures during orchestration return 500."""
        with patch.object(RetrievalService, 'retrieve_relevant_chunks', side_effect=RetrievalError("Connection failed")):
            resp = client.post(
                "/api/v1/chat/answer",
                json={"question": "What is the refund policy?"},
                headers=self.headers_a
            )
            self.assertEqual(resp.status_code, 500)
            self.assertIn("retrieve context", resp.json()["detail"].lower())

    def test_prompt_builder_failure_graceful_handling(self):
        """Test that prompt builder failures return 500."""
        mock_chunks = [{
            "chunk_id": "c1",
            "document_id": "d1",
            "page_number": 1,
            "chunk_index": 0,
            "similarity_score": 0.9,
            "chunk_text": "Sample text",
            "metadata": {"filename": "Sample.pdf", "organization_id": "org1"}
        }]

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(PromptBuilderService, 'build_prompt', side_effect=ValueError("Invalid context configuration")):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the refund policy?"},
                    headers=self.headers_a
                )
                self.assertEqual(resp.status_code, 500)
                self.assertIn("construct prompt context", resp.json()["detail"].lower())

    def test_manual_real_gemini_integration(self):
        """
        [OPTIONAL MANUAL TEST] Verifies real Gemini API answer generation.
        Will be skipped automatically unless a valid GOOGLE_API_KEY environment
        variable is set that does not start with 'mock-'.
        """
        real_key = os.getenv("REAL_GOOGLE_API_KEY")
        if not real_key:
            self.skipTest("REAL_GOOGLE_API_KEY environment variable not set. Skipping manual integration test.")

        settings.google_api_key = real_key
        gemini_service = GeminiService()
        prompt = (
            "You are a test agent. "
            "Please respond to the query exactly with the word: 'GroundedSuccess'."
        )
        try:
            answer = gemini_service.generate_answer(prompt)
            self.assertEqual(answer.strip(), "GroundedSuccess")
        except Exception as e:
            self.fail(f"Real Gemini API verification failed: {str(e)}")

if __name__ == "__main__":
    unittest.main()
