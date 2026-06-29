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
from app.services.citation_service import CitationService

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

class TestSprint13CitationEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.user_email = "admin_s13@enterprise.com"
        cls.org_name = "Org S13"

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
            "first_name": "S13",
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
        self.service = CitationService()

    def test_builds_citation_from_valid_results(self):
        """Test 1: Builds citation list from valid retrieval results."""
        results = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 2,
                "similarity_score": 0.85,
                "chunk_text": "Normal text",
                "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            }
        ]
        citations = self.service.build_citations(results)
        self.assertEqual(len(citations), 1)
        c = citations[0]
        self.assertEqual(c["citation_id"], "S1")
        self.assertEqual(c["document_id"], "doc1")
        self.assertEqual(c["document_name"], "doc1.txt")
        self.assertEqual(c["page_number"], 1)
        self.assertEqual(c["chunk_id"], "c1")
        self.assertEqual(c["chunk_index"], 2)
        self.assertEqual(c["similarity_score"], 0.85)
        self.assertEqual(c["source_label"], "doc1.txt, page 1")
        self.assertEqual(c["text_preview"], "Normal text")
        self.assertEqual(c["document"], "doc1.txt")
        self.assertEqual(c["page"], 1)

    def test_removes_duplicate_citations(self):
        """Test 2: Removes duplicate citations by chunk_id."""
        results = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 2,
                "similarity_score": 0.90,
                "chunk_text": "Sample text",
                "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 2,
                "similarity_score": 0.80,
                "chunk_text": "Sample text",
                "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            }
        ]
        citations = self.service.build_citations(results)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["similarity_score"], 0.90)  # highest score kept

    def test_preserves_relevance_ordering(self):
        """Test 3: Preserves relevance ordering (highest similarity score first)."""
        results = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.50,
                "chunk_text": "Text 1",
                "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 1,
                "similarity_score": 0.90,
                "chunk_text": "Text 2",
                "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            }
        ]
        citations = self.service.build_citations(results)
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0]["citation_id"], "S1")
        self.assertEqual(citations[0]["chunk_id"], "c2")  # 0.90 similarity score first
        self.assertEqual(citations[1]["citation_id"], "S2")
        self.assertEqual(citations[1]["chunk_id"], "c1")

    def test_handles_missing_metadata_safely(self):
        """Test 4: Handles missing metadata elements safely with fallbacks."""
        results = [
            {
                "chunk_id": "",
                "document_id": "",
                "page_number": None,
                "chunk_index": None,
                "similarity_score": None,
                "chunk_text": "No metadata content",
                "metadata": {}
            }
        ]
        citations = self.service.build_citations(results)
        self.assertEqual(len(citations), 1)
        c = citations[0]
        self.assertEqual(c["citation_id"], "S1")
        self.assertEqual(c["document_id"], "Unknown")
        self.assertEqual(c["document_name"], "Unknown Document")
        self.assertIsNone(c["page_number"])
        self.assertEqual(c["chunk_id"], "N/A")
        self.assertEqual(c["chunk_index"], 0)
        self.assertEqual(c["similarity_score"], 0.0)
        self.assertEqual(c["source_label"], "Unknown Document")

    def test_limits_text_preview_to_200_characters(self):
        """Test 5: Limits text_preview to 200 characters exactly."""
        long_text = "a" * 300
        results = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.90,
                "chunk_text": long_text,
                "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            }
        ]
        citations = self.service.build_citations(results)
        self.assertEqual(len(citations), 1)
        self.assertEqual(len(citations[0]["text_preview"]), 200)

    def test_empty_retrieval_returns_empty_citations(self):
        """Test 6: Empty retrieval list returns empty citations."""
        citations = self.service.build_citations([])
        self.assertEqual(citations, [])

    def test_answer_endpoint_returns_improved_citations(self):
        """Test 7: Chat answer endpoint includes improved citations."""
        mock_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.95,
                "chunk_text": "Refund policy info.",
                "metadata": {"filename": "RefundPolicy.pdf", "organization_id": "org1"}
            }
        ]

        from app.services.retrieval_service import RetrievalService
        from app.services.gemini_service import GeminiService

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', return_value="The policy is 30 days."):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the policy?"},
                    headers=self.headers
                )
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("sources", data)
                self.assertTrue(len(data["sources"]) > 0)
                c = data["sources"][0]
                self.assertEqual(c["citation_id"], "S1")
                self.assertEqual(c["document_name"], "RefundPolicy.pdf")
                self.assertEqual(c["text_preview"], "Refund policy info.")
                self.assertEqual(c["document"], "RefundPolicy.pdf")
                self.assertEqual(c["page"], 1)

    def test_unauthorized_request(self):
        """Test 8: Unauthorized request to citation build and answer returns 401."""
        resp1 = client.post("/api/v1/citations/build", json=[])
        self.assertEqual(resp1.status_code, 401)
        resp2 = client.post("/api/v1/chat/answer", json={"question": "Policy?"})
        self.assertEqual(resp2.status_code, 401)

if __name__ == "__main__":
    unittest.main()
