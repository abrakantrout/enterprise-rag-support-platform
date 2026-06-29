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
from app.database.models import User, Organization, ChatSession, Message, Feedback
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

class TestSprint17FeedbackSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db_session()
        cls.password = "SecurePassword123"
        
        # User 1 & Org 1
        cls.user_email_1 = "admin_s17_1@enterprise.com"
        cls.org_name_1 = "Org S17-1"
        
        # User 2 & Org 2
        cls.user_email_2 = "admin_s17_2@enterprise.com"
        cls.org_name_2 = "Org S17-2"

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

        # Create a persistent session and user/assistant messages for testing under Org 1
        cls.session1 = ChatSession(organization_id=cls.org1.id, user_id=cls.u1.id)
        cls.db.add(cls.session1)
        cls.db.commit()

        cls.user_msg = Message(session_id=cls.session1.id, sender="user", role="user", content="Question?")
        cls.assistant_msg = Message(session_id=cls.session1.id, sender="assistant", role="assistant", content="Answer.")
        cls.db.add_all([cls.user_msg, cls.assistant_msg])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(Feedback).delete()
        cls.db.query(Message).delete()
        cls.db.query(ChatSession).delete()
        cls.db.query(User).filter(User.email.in_([cls.user_email_1, cls.user_email_2])).delete(synchronize_session=False)
        cls.db.query(Organization).filter(Organization.name.in_([cls.org_name_1, cls.org_name_2])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def test_submit_thumbs_up_feedback(self):
        """Test 1: Submit thumbs up feedback successfully."""
        resp = client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.assistant_msg.id,
                "rating": "thumbs_up"
            },
            headers=self.headers1
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["rating"], "thumbs_up")
        self.assertEqual(data["user_id"], self.u1.id)
        self.assertEqual(data["organization_id"], self.org1.id)

    def test_submit_thumbs_down_feedback_with_comment(self):
        """Test 2: Submit thumbs down feedback with a comment successfully."""
        # Using a fresh session/message to avoid duplicate updates during this specific test step
        session = ChatSession(organization_id=self.org1.id, user_id=self.u1.id)
        self.db.add(session)
        self.db.commit()
        msg = Message(session_id=session.id, sender="assistant", role="assistant", content="Answer context.")
        self.db.add(msg)
        self.db.commit()

        resp = client.post(
            "/api/v1/feedback",
            json={
                "message_id": msg.id,
                "rating": "thumbs_down",
                "comment": "Needs page numbers."
            },
            headers=self.headers1
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["rating"], "thumbs_down")
        self.assertEqual(data["comment"], "Needs page numbers.")

    def test_feedback_on_user_message_rejected(self):
        """Test 3: Feedback on user message is rejected with HTTP 400."""
        resp = client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.user_msg.id,
                "rating": "thumbs_up"
            },
            headers=self.headers1
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Cannot submit feedback on a user message.")

    def test_duplicate_feedback_behavior_overrides(self):
        """Test 4: Submitting duplicate feedback from same user overrides the rating and comment."""
        # Submit thumbs up
        client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.assistant_msg.id,
                "rating": "thumbs_up",
                "comment": "Original comments."
            },
            headers=self.headers1
        )

        # Overwrite with thumbs down
        resp2 = client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.assistant_msg.id,
                "rating": "thumbs_down",
                "comment": "Overwritten comment."
            },
            headers=self.headers1
        )
        self.assertEqual(resp2.status_code, 201)
        data = resp2.json()
        self.assertEqual(data["rating"], "thumbs_down")
        self.assertEqual(data["comment"], "Overwritten comment.")

    def test_list_and_retrieve_feedback_detail(self):
        """Test 5 & 6: List organization feedback and retrieve feedback detail."""
        # Create a feedback first
        resp_f = client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.assistant_msg.id,
                "rating": "thumbs_up",
                "comment": "Retrieve test."
            },
            headers=self.headers1
        )
        feedback_id = resp_f.json()["id"]

        # List
        resp_list = client.get("/api/v1/feedback", headers=self.headers1)
        self.assertEqual(resp_list.status_code, 200)
        lst = resp_list.json()
        self.assertTrue(len(lst) > 0)
        self.assertTrue(any(f["id"] == feedback_id for f in lst))

        # Retrieve detail
        resp_det = client.get(f"/api/v1/feedback/{feedback_id}", headers=self.headers1)
        self.assertEqual(resp_det.status_code, 200)
        det = resp_det.json()
        self.assertEqual(det["id"], feedback_id)
        self.assertEqual(det["comment"], "Retrieve test.")

    def test_cross_organization_access_blocked(self):
        """Test 7: Access to another organization's feedback is strictly blocked with HTTP 403."""
        # Create a feedback under Org 1
        resp_f = client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.assistant_msg.id,
                "rating": "thumbs_up"
            },
            headers=self.headers1
        )
        feedback_id = resp_f.json()["id"]

        # Attempt to retrieve Org 1 feedback using User 2 (Org 2)
        resp_get = client.get(f"/api/v1/feedback/{feedback_id}", headers=self.headers2)
        self.assertEqual(resp_get.status_code, 403)

        # Attempt to submit feedback on Org 1 message using User 2 (Org 2)
        resp_post = client.post(
            "/api/v1/feedback",
            json={
                "message_id": self.assistant_msg.id,
                "rating": "thumbs_up"
            },
            headers=self.headers2
        )
        self.assertEqual(resp_post.status_code, 403)

    def test_unauthorized_request(self):
        """Test 8: Anonymous/unauthorized requests return HTTP 401."""
        resp = client.post("/api/v1/feedback", json={"message_id": "some", "rating": "thumbs_up"})
        self.assertEqual(resp.status_code, 401)
        resp2 = client.get("/api/v1/feedback")
        self.assertEqual(resp2.status_code, 401)

if __name__ == "__main__":
    unittest.main()
