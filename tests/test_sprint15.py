import os
import sys
import unittest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend to path to allow importing app and models
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app
from app.core.config import settings
from app.database.models import User, Organization
from app.database.connection import get_db

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

class TestSprint15StreamingAnswer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        cls.user_email = "admin_s15@enterprise.com"
        cls.org_name = "Org S15"

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
            "first_name": "S15",
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

    def parse_sse_events(self, content_str: str):
        """Helper to parse raw text/event-stream into a list of (event_name, data_dict) tuples."""
        events = []
        current_event = None
        
        lines = content_str.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.replace("event:", "").strip()
            elif line.startswith("data:") and current_event:
                data_val = line.replace("data:", "").strip()
                events.append((current_event, json.loads(data_val)))
                current_event = None
        return events

    def test_sse_endpoint_exists(self):
        """Test 1: Streaming SSE endpoint exists at /api/v1/chat/answer/stream."""
        # Using a dummy post that succeeds auth checks
        mock_chunks = [{"chunk_id": "c1", "document_id": "doc1", "similarity_score": 0.9, "chunk_text": "Text", "metadata": {"filename": "doc.pdf"}}]
        
        from app.services.retrieval_service import RetrievalService
        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            resp = client.post(
                "/api/v1/chat/answer/stream",
                json={"question": "What is the policy?"},
                headers=self.headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("content-type"), "text/event-stream; charset=utf-8")

    def test_unauthorized_request(self):
        """Test 2: Request without credentials returns HTTP 401."""
        resp = client.post("/api/v1/chat/answer/stream", json={"question": "What is the policy?"})
        self.assertEqual(resp.status_code, 401)

    def test_stream_emits_expected_event_order(self):
        """Test 3: Streaming session emits events in the correct requested sequence."""
        mock_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.95,
                "chunk_text": "Refund details here.",
                "metadata": {"filename": "RefundPolicy.pdf", "organization_id": "org1"}
            }
        ]
        
        from app.services.retrieval_service import RetrievalService
        from app.services.gemini_service import GeminiService

        def mock_gen(*args, **kwargs):
            yield "Based on the provided documents, the refund policy allows you to request a full refund."

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer_stream', side_effect=mock_gen):
                resp = client.post(
                    "/api/v1/chat/answer/stream",
                    json={"question": "What is the policy?"},
                    headers=self.headers
                )
                self.assertEqual(resp.status_code, 200)
                events = self.parse_sse_events(resp.text)
                
                event_names = [e[0] for e in events]
                
                # Check expected events are present in sequence:
                self.assertIn("retrieval_started", event_names)
                self.assertIn("retrieval_completed", event_names)
                self.assertIn("context_optimized", event_names)
                self.assertIn("prompt_built", event_names)
                self.assertIn("answer_started", event_names)
                self.assertIn("answer_delta", event_names)
                self.assertIn("answer_completed", event_names)
                self.assertIn("citations_ready", event_names)
                self.assertIn("verification_ready", event_names)
                self.assertIn("done", event_names)

                # Check that answer_delta has actual content
                deltas = [e[1] for e in events if e[0] == "answer_delta"]
                self.assertTrue(len(deltas) > 0)
                self.assertTrue(any("text" in d for d in deltas))

    def test_no_retrieval_results_streams_safe_refusal(self):
        """Test 4: Empty context yields no-context path events and safe refusal answer_delta."""
        from app.services.retrieval_service import RetrievalService
        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=[]):
            resp = client.post(
                "/api/v1/chat/answer/stream",
                json={"question": "Nonexistent policy?"},
                headers=self.headers
            )
            self.assertEqual(resp.status_code, 200)
            events = self.parse_sse_events(resp.text)
            event_names = [e[0] for e in events]

            # Verify no-context sequence
            self.assertIn("retrieval_started", event_names)
            self.assertIn("retrieval_completed", event_names)
            self.assertIn("answer_started", event_names)
            self.assertIn("answer_delta", event_names)
            self.assertIn("answer_completed", event_names)
            self.assertIn("done", event_names)

            # Prompt built is NOT emitted on empty context bypass
            self.assertNotIn("prompt_built", event_names)

            # Reconstruct answer from deltas to verify safe refusal message
            deltas = [e[1]["text"] for e in events if e[0] == "answer_delta"]
            full_refusal = "".join(deltas).strip()
            self.assertEqual(full_refusal, "I could not find relevant information in the uploaded documents.")

    def test_error_event_emitted_on_provider_failure(self):
        """Test 5: Provider failure emits 'error' SSE event and interrupts stream."""
        from app.services.retrieval_service import RetrievalService
        
        with patch.object(RetrievalService, 'retrieve_relevant_chunks', side_effect=Exception("DB Down")):
            resp = client.post(
                "/api/v1/chat/answer/stream",
                json={"question": "Will fail?"},
                headers=self.headers
            )
            self.assertEqual(resp.status_code, 200)
            events = self.parse_sse_events(resp.text)
            event_names = [e[0] for e in events]
            
            self.assertIn("retrieval_started", event_names)
            self.assertIn("error", event_names)
            self.assertNotIn("done", event_names)
            
            err_data = [e[1] for e in events if e[0] == "error"][0]
            self.assertIn("Failed to retrieve context documents", err_data["detail"])

    def test_existing_non_stream_endpoint_works(self):
        """Test 6: Existing non-streaming /api/v1/chat/answer endpoint continues working correctly."""
        mock_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.98,
                "chunk_text": "Normal text context.",
                "metadata": {"filename": "Policy.pdf", "organization_id": "org1"}
            }
        ]
        
        from app.services.retrieval_service import RetrievalService
        from app.services.gemini_service import GeminiService
        
        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', return_value="The policy is clear."):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the policy?"},
                    headers=self.headers
                )
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertEqual(data["answer"], "The policy is clear.")
                self.assertIn("verification", data)
                self.assertIn("sources", data)

if __name__ == "__main__":
    unittest.main()
