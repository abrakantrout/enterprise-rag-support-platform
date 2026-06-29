import os
import sys
import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend to path to allow importing app and models
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app
from app.core.config import settings
from app.database.models import User, Organization, ChatSession, Message
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

class TestSprint16ChatSessions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        
        # User 1 & Org 1
        cls.user_email_1 = "admin_s16_1@enterprise.com"
        cls.org_name_1 = "Org S16-1"
        
        # User 2 & Org 2
        cls.user_email_2 = "admin_s16_2@enterprise.com"
        cls.org_name_2 = "Org S16-2"

        # 1. Clean existing records
        cls.db.query(User).filter(User.email.in_([cls.user_email_1, cls.user_email_2])).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name.in_([cls.org_name_1, cls.org_name_2])).delete(synchronize_session=False)
        cls.db.commit()

        # Get system bootstrap token for registration
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

        # Register User 1 & User 2
        client.post("/api/v1/auth/register", json={
            "email": cls.user_email_1,
            "password": cls.password,
            "first_name": "User1",
            "last_name": "Admin",
            "role": "Administrator"
        }, headers=bootstrap_headers)

        client.post("/api/v1/auth/register", json={
            "email": cls.user_email_2,
            "password": cls.password,
            "first_name": "User2",
            "last_name": "Admin",
            "role": "Administrator"
        }, headers=bootstrap_headers)

        # Create Orgs
        cls.org1 = Organization(id=str(uuid.uuid4()), name=cls.org_name_1)
        cls.org2 = Organization(id=str(uuid.uuid4()), name=cls.org_name_2)
        cls.db.add_all([cls.org1, cls.org2])
        cls.db.commit()

        # Update User orgs
        cls.u1 = cls.db.query(User).filter(User.email == cls.user_email_1).first()
        cls.u2 = cls.db.query(User).filter(User.email == cls.user_email_2).first()
        cls.u1.organization_id = cls.org1.id
        cls.u2.organization_id = cls.org2.id
        cls.db.commit()

        # Login User 1
        resp1 = client.post("/api/v1/auth/login", data={"username": cls.user_email_1, "password": cls.password})
        cls.token1 = resp1.json()["access_token"]
        cls.headers1 = {"Authorization": f"Bearer {cls.token1}"}

        # Login User 2
        resp2 = client.post("/api/v1/auth/login", data={"username": cls.user_email_2, "password": cls.password})
        cls.token2 = resp2.json()["access_token"]
        cls.headers2 = {"Authorization": f"Bearer {cls.token2}"}

    @classmethod
    def tearDownClass(cls):
        # Delete ChatSessions / Messages
        # SQLite cascade or direct delete
        cls.db.query(Message).delete()
        cls.db.query(ChatSession).delete()
        cls.db.query(User).filter(User.email.in_([cls.user_email_1, cls.user_email_2])).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name.in_([cls.org_name_1, cls.org_name_2])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def test_create_and_list_chat_session(self):
        """Test 1 & 2: Create chat session and list chat sessions."""
        # Create
        resp = client.post("/api/v1/chat/sessions", json={}, headers=self.headers1)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("session_id", data)
        self.assertEqual(data["organization_id"], self.org1.id)
        
        session_id = data["session_id"]

        # List
        resp_list = client.get("/api/v1/chat/sessions", headers=self.headers1)
        self.assertEqual(resp_list.status_code, 200)
        sessions = resp_list.json()
        self.assertTrue(len(sessions) > 0)
        self.assertTrue(any(s["session_id"] == session_id for s in sessions))

    def test_retrieve_empty_session_messages(self):
        """Test 3: Retrieve empty session messages."""
        resp = client.post("/api/v1/chat/sessions", json={}, headers=self.headers1)
        session_id = resp.json()["session_id"]

        resp_detail = client.get(f"/api/v1/chat/sessions/{session_id}", headers=self.headers1)
        self.assertEqual(resp_detail.status_code, 200)
        data = resp_detail.json()
        self.assertEqual(data["session_id"], session_id)
        self.assertEqual(data["messages"], [])

    def test_save_question_and_answer_with_citations_and_verification(self):
        """Test 4, 5 & 6: Run answer pipeline on session, verifying saved messages, citations, and verification metadata."""
        resp_sess = client.post("/api/v1/chat/sessions", json={}, headers=self.headers1)
        session_id = resp_sess.json()["session_id"]

        mock_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 2,
                "chunk_index": 4,
                "similarity_score": 0.95,
                "chunk_text": "Important policy context.",
                "metadata": {"filename": "RefundPolicy.pdf", "organization_id": self.org1.id}
            }
        ]

        from app.services.retrieval_service import RetrievalService
        from app.services.gemini_service import GeminiService

        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', return_value="The policy details state 30 days."):
                resp_ans = client.post(
                    f"/api/v1/chat/sessions/{session_id}/answer",
                    json={"question": "What is the refund policy?"},
                    headers=self.headers1
                )
                self.assertEqual(resp_ans.status_code, 200)
                ans_data = resp_ans.json()
                self.assertIn("verification", ans_data)
                self.assertEqual(ans_data["answer"], "The policy details state 30 days.")

        # Query messages via GET session
        resp_detail = client.get(f"/api/v1/chat/sessions/{session_id}", headers=self.headers1)
        self.assertEqual(resp_detail.status_code, 200)
        detail_data = resp_detail.json()
        messages = detail_data["messages"]
        
        self.assertEqual(len(messages), 2)
        
        # User message
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "What is the refund policy?")
        
        # Assistant message
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "The policy details state 30 days.")
        
        # Citations saved correctly
        citations = messages[1]["citations"]
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["citation_id"], "S1")
        self.assertEqual(citations[0]["document_name"], "RefundPolicy.pdf")
        
        # Verification saved correctly
        verification = messages[1]["verification"]
        self.assertIsNotNone(verification)
        self.assertEqual(verification["verification_status"], "moderate")
        self.assertTrue(verification["confidence"] > 0.0)

    def test_unauthorized_request(self):
        """Test 7: Accessing session endpoints without auth tokens returns HTTP 401."""
        resp = client.post("/api/v1/chat/sessions", json={})
        self.assertEqual(resp.status_code, 401)
        resp2 = client.get("/api/v1/chat/sessions")
        self.assertEqual(resp2.status_code, 401)

    def test_cross_organization_session_access_blocked(self):
        """Test 8: Users cannot access or interact with sessions belonging to another organization."""
        # Create session under Org 1
        resp_sess = client.post("/api/v1/chat/sessions", json={}, headers=self.headers1)
        session_id = resp_sess.json()["session_id"]

        # Attempt to retrieve session using User 2 (Org 2)
        resp_get = client.get(f"/api/v1/chat/sessions/{session_id}", headers=self.headers2)
        self.assertEqual(resp_get.status_code, 403)

        # Attempt to post answer using User 2 (Org 2)
        resp_post = client.post(
            f"/api/v1/chat/sessions/{session_id}/answer",
            json={"question": "Policy?"},
            headers=self.headers2
        )
        self.assertEqual(resp_post.status_code, 403)

        # Attempt to delete using User 2 (Org 2)
        resp_del = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=self.headers2)
        self.assertEqual(resp_del.status_code, 403)

    def test_deleted_session_blocked(self):
        """Test 9: Soft-deleted sessions cannot be retrieved, deleted again, or answered."""
        # Create
        resp_sess = client.post("/api/v1/chat/sessions", json={}, headers=self.headers1)
        session_id = resp_sess.json()["session_id"]

        # Delete
        resp_del = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=self.headers1)
        self.assertEqual(resp_del.status_code, 200)

        # Retrieval fails with 404
        resp_get = client.get(f"/api/v1/chat/sessions/{session_id}", headers=self.headers1)
        self.assertEqual(resp_get.status_code, 404)

        # Answer generation fails with 404
        resp_ans = client.post(
            f"/api/v1/chat/sessions/{session_id}/answer",
            json={"question": "What is the policy?"},
            headers=self.headers1
        )
        self.assertEqual(resp_ans.status_code, 404)

        # Repeating delete fails with 404
        resp_del_again = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=self.headers1)
        self.assertEqual(resp_del_again.status_code, 404)

    def test_existing_non_session_answer_endpoints_still_work(self):
        """Test 10: Legacy non-session chat endpoints continue working correctly without regression."""
        mock_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "page_number": 1,
                "chunk_index": 0,
                "similarity_score": 0.95,
                "chunk_text": "Non-session text.",
                "metadata": {"filename": "Policy.pdf", "organization_id": self.org1.id}
            }
        ]
        
        from app.services.retrieval_service import RetrievalService
        from app.services.gemini_service import GeminiService
        
        with patch.object(RetrievalService, 'retrieve_relevant_chunks', return_value=mock_chunks):
            with patch.object(GeminiService, 'generate_answer', return_value="Verified non-session answer."):
                resp = client.post(
                    "/api/v1/chat/answer",
                    json={"question": "What is the policy?"},
                    headers=self.headers1
                )
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertEqual(data["answer"], "Verified non-session answer.")
                self.assertIn("verification", data)

if __name__ == "__main__":
    unittest.main()
