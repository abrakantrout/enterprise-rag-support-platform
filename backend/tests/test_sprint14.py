import os
import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend to path to allow importing app and models
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app
from app.core.config import settings
from app.database.models import User, Organization
from app.database.connection import get_db
from app.services.answer_verification_service import AnswerVerificationService

client = TestClient(app)

def get_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
    if "db:5432" in db_url and not os.path.exists("/workspace"):
         db_url = db_url.replace("db:5432", "localhost:5432")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

class TestSprint14VerificationEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.user_email = "admin_s14@enterprise.com"
        cls.org_name = "Org S14"

        # 1. Clean existing records
        cls.db.query(User).filter(User.email == cls.user_email).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name == cls.org_name).delete(synchronize_session=False)
        cls.db.commit()

        # 2. Register user & org
        login_resp = client.post("/api/v1/auth/login", data={"username": "admin@enterprise.com", "password": cls.password})
        if login_resp.status_code == 401:
            client.post("/api/v1/auth/register", json={
                "email": "admin@enterprise.com",
                "password": cls.password,
                "first_name": "System",
                "last_name": "Admin",
                "role": "Administrator"
            })
            login_resp = client.post("/api/v1/auth/login", data={"username": "admin@enterprise.com", "password": cls.password})
        
        bootstrap_token = login_resp.json()["access_token"]
        bootstrap_headers = {"Authorization": f"Bearer {bootstrap_token}"}

        client.post("/api/v1/auth/register", json={
            "email": cls.user_email,
            "password": cls.password,
            "first_name": "S14",
            "last_name": "Admin",
            "role": "Administrator"
        }, headers=bootstrap_headers)

        import uuid
        cls.org = Organization(id=str(uuid.uuid4()), name=cls.org_name)
        cls.db.add(cls.org)
        cls.db.commit()

        cls.user_rec = cls.db.query(User).filter(User.email == cls.user_email).first()
        cls.user_rec.organization_id = cls.org.id
        cls.db.commit()

        # Login to get authorization header
        resp = client.post("/api/v1/auth/login", data={"username": cls.user_email, "password": cls.password})
        cls.token = resp.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        user_u = cls.db.query(User).filter(User.email == cls.user_email).first()
        if user_u:
            cls.db.delete(user_u)
            cls.db.commit()
        org_u = cls.db.query(Organization).filter(Organization.name == cls.org_name).first()
        if org_u:
            cls.db.delete(org_u)
            cls.db.commit()
        cls.db.close()

    def setUp(self):
        self.service = AnswerVerificationService()

    def test_high_confidence_supported(self):
        """Test 1: Verification yields high confidence and 'supported' status for robust contexts."""
        chunks = [{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}, {"chunk_id": "c4"}]
        citations = [
            {"similarity_score": 0.95},
            {"similarity_score": 0.90},
            {"similarity_score": 0.92},
            {"similarity_score": 0.88}
        ]
        res = self.service.verify_answer("A grounded answer.", chunks, {}, citations)
        self.assertEqual(res["verification_status"], "supported")
        self.assertTrue(res["confidence"] >= 0.80)

    def test_medium_confidence_moderate(self):
        """Test 2: Verification yields medium confidence and 'moderate' status."""
        chunks = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
        citations = [
            {"similarity_score": 0.70},
            {"similarity_score": 0.65}
        ]
        res = self.service.verify_answer("A grounded answer.", chunks, {}, citations)
        self.assertEqual(res["verification_status"], "moderate")
        self.assertTrue(0.50 <= res["confidence"] < 0.80)

    def test_low_confidence_supported(self):
        """Test 3: Verification yields low confidence status."""
        chunks = [{"chunk_id": "c1"}]
        citations = [
            {"similarity_score": 0.35}
        ]
        res = self.service.verify_answer("A grounded answer.", chunks, {}, citations)
        self.assertEqual(res["verification_status"], "low_confidence")
        self.assertTrue(0.15 <= res["confidence"] < 0.50)

    def test_empty_retrieval(self):
        """Test 4: Empty retrieval produces 0.0 confidence and unsupported status."""
        res = self.service.verify_answer(
            "I could not find relevant information in the uploaded documents.",
            [], {}, []
        )
        self.assertEqual(res["confidence"], 0.0)
        self.assertEqual(res["verification_status"], "unsupported")

    def test_missing_citations(self):
        """Test 5: Empty citation list results in 0.0 confidence and unsupported status."""
        chunks = [{"chunk_id": "c1"}]
        res = self.service.verify_answer("An answer.", chunks, {}, [])
        self.assertEqual(res["confidence"], 0.0)
        self.assertEqual(res["verification_status"], "unsupported")

    def test_deterministic_output(self):
        """Test 6: Repeated verification runs yield identical scores and outputs."""
        chunks = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
        citations = [{"similarity_score": 0.85}, {"similarity_score": 0.75}]
        res1 = self.service.verify_answer("Answer text.", chunks, {}, citations)
        res2 = self.service.verify_answer("Answer text.", chunks, {}, citations)
        self.assertEqual(res1["confidence"], res2["confidence"])
        self.assertEqual(res1["verification_status"], res2["verification_status"])

    def test_integration_answer_endpoint_includes_verification(self):
        """Test 7: RAG answer pipeline endpoint returns structured verification fields."""
        mock_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.95,
                "chunk_text": "Refund policy content.",
                "metadata": {"filename": "RefundPolicy.pdf", "organization_id": "org1"}
            }
        ]

        from app.services.retrieval_service import RetrievalService
        from app.services.gemini_service import GeminiService

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', return_value="We offer refunds within 30 days."):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the policy?"},
                    headers=self.headers
                )
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("verification", data)
                v = data["verification"]
                self.assertIn("confidence", v)
                self.assertIn("verification_status", v)
                self.assertIn("reason", v)
                self.assertEqual(v["retrieval_count"], 1)

    def test_unauthorized_request(self):
        """Test 8: Unauthorized calls return HTTP 401."""
        resp = client.post("/api/v1/chat/answer", json={"question": "Refund policy?"})
        self.assertEqual(resp.status_code, 401)

if __name__ == "__main__":
    unittest.main()
