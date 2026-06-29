import os
import sys
import unittest
import uuid
from fastapi.testclient import TestClient

# Add backend to path to allow importing app and models
sys.path.insert(0, "/workspace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app
from app.core.config import settings
from app.database.models import User, Organization, ChatSession, Message, Feedback, Document
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

class TestSprint18AdminAnalytics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        
        # User 1 & Org 1
        cls.user_email_1 = "admin_s18_1@enterprise.com"
        cls.org_name_1 = "Org S18-1"
        
        # User 2 & Org 2
        cls.user_email_2 = "admin_s18_2@enterprise.com"
        cls.org_name_2 = "Org S18-2"

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
        cls.db.query(Feedback).delete()
        cls.db.query(Message).delete()
        cls.db.query(ChatSession).delete()
        cls.db.query(Document).delete()
        cls.db.query(User).filter(User.email.in_([cls.user_email_1, cls.user_email_2])).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name.in_([cls.org_name_1, cls.org_name_2])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def test_overview_analytics(self):
        """Test 1: Overview analytics works and returns correct keys."""
        resp = client.get("/api/v1/analytics/overview", headers=self.headers1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_documents", data)
        self.assertIn("processed_documents", data)
        self.assertIn("failed_documents", data)
        self.assertIn("total_chunks", data)
        self.assertIn("total_chat_sessions", data)
        self.assertIn("total_messages", data)
        self.assertIn("total_feedback", data)
        self.assertIn("thumbs_up_count", data)
        self.assertIn("thumbs_down_count", data)

    def test_recent_questions(self):
        """Test 2: Recent questions returns only user messages."""
        # Create fresh session, user question, and assistant answer
        sess = ChatSession(organization_id=self.org1.id, user_id=self.u1.id)
        self.db.add(sess)
        self.db.commit()
        
        q_msg = Message(session_id=sess.id, sender="user", role="user", content="Where is my refund?")
        a_msg = Message(session_id=sess.id, sender="assistant", role="assistant", content="We process within 30 days.")
        self.db.add_all([q_msg, a_msg])
        self.db.commit()

        resp = client.get("/api/v1/analytics/recent-questions?limit=10", headers=self.headers1)
        self.assertEqual(resp.status_code, 200)
        lst = resp.json()
        self.assertTrue(len(lst) > 0)
        self.assertTrue(all(q["content"] == "Where is my refund?" for q in lst if q["message_id"] == q_msg.id))
        self.assertFalse(any(q["message_id"] == a_msg.id for q in lst))

    def test_low_rated_answers(self):
        """Test 3: Low-rated answers returns only thumbs_down assistant messages."""
        sess = ChatSession(organization_id=self.org1.id, user_id=self.u1.id)
        self.db.add(sess)
        self.db.commit()
        
        a_msg = Message(session_id=sess.id, sender="assistant", role="assistant", content="Poor quality answer.")
        self.db.add(a_msg)
        self.db.commit()

        # Submit thumbs down feedback
        feedback = Feedback(
            message_id=a_msg.id,
            user_id=self.u1.id,
            organization_id=self.org1.id,
            score=-1,
            rating="thumbs_down",
            comment="Incorrect info."
        )
        self.db.add(feedback)
        self.db.commit()

        resp = client.get("/api/v1/analytics/low-rated-answers", headers=self.headers1)
        self.assertEqual(resp.status_code, 200)
        lst = resp.json()
        self.assertTrue(len(lst) > 0)
        self.assertTrue(any(item["message_id"] == a_msg.id for item in lst))
        self.assertEqual(lst[0]["comment"], "Incorrect info.")

    def test_document_status_grouping(self):
        """Test 4: Grouped document processing statuses returns counts."""
        # Create documents with various statuses
        doc1 = Document(
            filename="d1.pdf", stored_path="/tmp/d1.pdf", file_type="pdf", file_size=100,
            status="Completed", uploader_id=self.u1.id, organization_id=self.org1.id
        )
        doc2 = Document(
            filename="d2.pdf", stored_path="/tmp/d2.pdf", file_type="pdf", file_size=100,
            status="Processing", uploader_id=self.u1.id, organization_id=self.org1.id
        )
        self.db.add_all([doc1, doc2])
        self.db.commit()

        resp = client.get("/api/v1/analytics/document-status", headers=self.headers1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["Completed"] >= 1)
        self.assertTrue(data["Processing"] >= 1)
        self.assertIn("Failed", data)

    def test_empty_dataset_handling(self):
        """Test 5: Organizations with zero records return safe zeros and empty sets."""
        resp = client.get("/api/v1/analytics/overview", headers=self.headers2)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_documents"], 0)
        self.assertEqual(data["total_chat_sessions"], 0)

        resp2 = client.get("/api/v1/analytics/recent-questions", headers=self.headers2)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json(), [])

    def test_limit_parameter_bounds(self):
        """Test 6 & 7: Limit parameter validation controls input constraints."""
        # Valid limit
        resp_ok = client.get("/api/v1/analytics/recent-questions?limit=5", headers=self.headers1)
        self.assertEqual(resp_ok.status_code, 200)

        # Invalid limit < 1
        resp_low = client.get("/api/v1/analytics/recent-questions?limit=0", headers=self.headers1)
        self.assertEqual(resp_low.status_code, 400)

        # Invalid limit > 50
        resp_high = client.get("/api/v1/analytics/recent-questions?limit=51", headers=self.headers1)
        self.assertEqual(resp_high.status_code, 400)

    def test_unauthorized_request(self):
        """Test 8: Unauthorized requests return HTTP 401."""
        resp = client.get("/api/v1/analytics/overview")
        self.assertEqual(resp.status_code, 401)

    def test_cross_organization_isolation(self):
        """Test 9: Organization data isolation is strictly preserved."""
        # Query overview for Org 2 - must show 0 documents even though Org 1 has documents
        resp = client.get("/api/v1/analytics/overview", headers=self.headers2)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total_documents"], 0)

if __name__ == "__main__":
    unittest.main()
