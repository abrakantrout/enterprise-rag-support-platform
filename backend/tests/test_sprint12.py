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
from app.services.context_optimizer_service import ContextOptimizerService

client = TestClient(app)

def get_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
    if "db:5432" in db_url and not os.path.exists("/workspace"):
         db_url = db_url.replace("db:5432", "localhost:5432")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

class TestSprint12ContextOptimizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.password = "SecurePassword123"
        cls.user_email = "admin_s12@enterprise.com"
        cls.org_name = "Org S12"

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
            "first_name": "S12",
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
        self.optimizer = ContextOptimizerService()
        self.original_max_chars = settings.max_context_characters

    def tearDown(self):
        settings.max_context_characters = self.original_max_chars

    def test_duplicate_chunks_removed(self):
        """Test 1: Exact duplicate chunks are removed, keeping the one with higher similarity score."""
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.85,
                "chunk_text": "The quick brown fox jumps over the lazy dog.", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc1", "page_number": 1, "chunk_index": 1, "similarity_score": 0.95,
                "chunk_text": "The quick brown fox jumps over the lazy dog.", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            }
        ]
        optimized, summary = self.optimizer.optimize_context(chunks)
        self.assertEqual(len(optimized), 1)
        self.assertEqual(optimized[0]["chunk_id"], "c2")  # higher similarity score kept
        self.assertEqual(summary["duplicates_removed"], 1)

    def test_near_duplicates_removed(self):
        """Test 2: Near duplicate chunks (>90% similarity) are removed, keeping the highest similarity."""
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.80,
                "chunk_text": "The quick brown fox jumps over the lazy dog.", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc1", "page_number": 1, "chunk_index": 1, "similarity_score": 0.90,
                "chunk_text": "The quick brown fox jumps over the lazy dog!", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            }
        ]
        optimized, summary = self.optimizer.optimize_context(chunks)
        self.assertEqual(len(optimized), 1)
        self.assertEqual(optimized[0]["chunk_id"], "c2")  # higher similarity score kept
        self.assertEqual(summary["near_duplicates_removed"], 1)

    def test_ordering_preserved_and_similarity_ordering_correct(self):
        """Test 3 & 4: Output is sorted by similarity score descending."""
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.50,
                "chunk_text": "First low score.", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc2", "page_number": 1, "chunk_index": 0, "similarity_score": 0.90,
                "chunk_text": "Second high score.", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c3", "document_id": "doc3", "page_number": 1, "chunk_index": 0, "similarity_score": 0.70,
                "chunk_text": "Third medium score.", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            }
        ]
        optimized, _ = self.optimizer.optimize_context(chunks)
        self.assertEqual(len(optimized), 3)
        self.assertEqual(optimized[0]["chunk_id"], "c2")
        self.assertEqual(optimized[1]["chunk_id"], "c3")
        self.assertEqual(optimized[2]["chunk_id"], "c1")

    def test_token_budget_respected(self):
        """Test 5: Context length respects max character limits."""
        self.optimizer.max_characters = 100
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.90,
                "chunk_text": "This is a chunk that is somewhat long and should take up some space in the budget.",
                "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc2", "page_number": 1, "chunk_index": 0, "similarity_score": 0.80,
                "chunk_text": "This is another chunk that should be completely skipped because we are out of character budget.",
                "metadata": {"filename": "f.txt", "organization_id": "org1"}
            }
        ]
        optimized, summary = self.optimizer.optimize_context(chunks)
        self.assertEqual(len(optimized), 1)
        self.assertEqual(optimized[0]["chunk_id"], "c1")
        self.assertTrue(summary["estimated_characters"] > 0)

    def test_document_diversity_improved(self):
        """Test 6: Broader document coverage is prioritized when multiple documents have similar chunks."""
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.95,
                "chunk_text": "Doc 1 text A", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc1", "page_number": 1, "chunk_index": 1, "similarity_score": 0.90,
                "chunk_text": "Doc 1 text B", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c3", "document_id": "doc2", "page_number": 1, "chunk_index": 0, "similarity_score": 0.85,
                "chunk_text": "Doc 2 text A", "metadata": {"filename": "doc2.txt", "organization_id": "org1"}
            }
        ]
        # Under budget limit of 2 chunks, we should select c1 (Doc 1) and c3 (Doc 2) instead of c1 and c2 (both Doc 1)
        self.optimizer.max_characters = 180
        optimized, _ = self.optimizer.optimize_context(chunks)
        chunk_ids = [c["chunk_id"] for c in optimized]
        self.assertIn("c1", chunk_ids)
        self.assertIn("c3", chunk_ids)
        self.assertNotIn("c2", chunk_ids)

    def test_page_diversity_improved(self):
        """Test 7: Diverse page selection is preferred over same-page blocks."""
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.95,
                "chunk_text": "This is some unique page 1 content.", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc1", "page_number": 1, "chunk_index": 1, "similarity_score": 0.90,
                "chunk_text": "This is some other page 1 content.", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c3", "document_id": "doc1", "page_number": 2, "chunk_index": 0, "similarity_score": 0.85,
                "chunk_text": "Completely different page 2 content text about security and protocols.", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            }
        ]
        # Under limit of 2 chunks, we should get page 1 (c1) and page 2 (c3) rather than page 1 only (c1, c2)
        self.optimizer.max_characters = 300
        optimized, _ = self.optimizer.optimize_context(chunks)
        chunk_ids = [c["chunk_id"] for c in optimized]
        self.assertIn("c1", chunk_ids)
        self.assertIn("c3", chunk_ids)
        self.assertNotIn("c2", chunk_ids)

    def test_empty_chunks_removed(self):
        """Test 8: Discards empty, whitespace, and invalid chunks."""
        chunks = [
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.90,
                "chunk_text": "   ", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "c2", "document_id": "doc1", "page_number": 1, "chunk_index": 1, "similarity_score": 0.95,
                "chunk_text": "Valid chunk content.", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            },
            {
                "chunk_id": "", "document_id": "doc1", "page_number": 1, "chunk_index": 2, "similarity_score": 0.99,
                "chunk_text": "Missing chunk ID.", "metadata": {"filename": "doc1.txt", "organization_id": "org1"}
            }
        ]
        optimized, summary = self.optimizer.optimize_context(chunks)
        self.assertEqual(len(optimized), 1)
        self.assertEqual(optimized[0]["chunk_id"], "c2")
        self.assertEqual(summary["discarded_empty"], 2)

    def test_no_valid_chunks_handled_safely(self):
        """Test 9: Passing empty lists or invalid data handles gracefully without raising errors."""
        chunks = []
        optimized, summary = self.optimizer.optimize_context(chunks)
        self.assertEqual(len(optimized), 0)
        self.assertEqual(summary["original_chunks"], 0)

    def test_optimization_summary_accurate(self):
        """Test 10: Summary parameters correctly counts all removed elements."""
        chunks = [
            # valid 1
            {
                "chunk_id": "c1", "document_id": "doc1", "page_number": 1, "chunk_index": 0, "similarity_score": 0.95,
                "chunk_text": "Original text A", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            # exact duplicate
            {
                "chunk_id": "c2", "document_id": "doc1", "page_number": 1, "chunk_index": 1, "similarity_score": 0.90,
                "chunk_text": "Original text A", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            # near duplicate (>90%)
            {
                "chunk_id": "c3", "document_id": "doc1", "page_number": 1, "chunk_index": 2, "similarity_score": 0.85,
                "chunk_text": "Original text A!", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            },
            # empty text
            {
                "chunk_id": "c4", "document_id": "doc1", "page_number": 1, "chunk_index": 3, "similarity_score": 0.80,
                "chunk_text": "", "metadata": {"filename": "f.txt", "organization_id": "org1"}
            }
        ]
        _, summary = self.optimizer.optimize_context(chunks)
        self.assertEqual(summary["original_chunks"], 4)
        self.assertEqual(summary["optimized_chunks"], 1)
        self.assertEqual(summary["duplicates_removed"], 1)
        self.assertEqual(summary["near_duplicates_removed"], 1)
        self.assertEqual(summary["discarded_empty"], 1)

    def test_api_optimize_endpoint(self):
        """Test endpoint POST /api/v1/retrieval/optimize."""
        payload = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.95,
                "chunk_text": "The quick brown fox jumps over the lazy dog.",
                "metadata": {
                    "filename": "f.txt",
                    "organization_id": "org1"
                }
            },
            {
                "chunk_id": "c2",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 1,
                "similarity_score": 0.90,
                "chunk_text": "The quick brown fox jumps over the lazy dog.",
                "metadata": {
                    "filename": "f.txt",
                    "organization_id": "org1"
                }
            }
        ]
        resp = client.post("/api/v1/retrieval/optimize", json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("optimized_chunks", data)
        self.assertIn("optimization_summary", data)
        self.assertEqual(len(data["optimized_chunks"]), 1)
        self.assertEqual(data["optimization_summary"]["duplicates_removed"], 1)

if __name__ == "__main__":
    unittest.main()
