import os
import requests
from typing import Dict, List, Any, Optional

class APIClient:
    def __init__(self):
        # Retrieve backend URL from environment or default to local development port
        self.base_url = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
        self.token: Optional[str] = None

    def set_token(self, token: Optional[str]):
        self.token = token

    def _get_headers(self) -> Dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def check_health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def login(self, email: str, password: str) -> Dict[str, Any]:
        data = {
            "username": email,
            "password": password
        }
        r = requests.post(f"{self.base_url}/api/v1/auth/login", data=data)
        r.raise_for_status()
        res = r.json()
        self.set_token(res.get("access_token"))
        return res

    def get_me(self) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/api/v1/auth/me", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    # --- Analytics Endpoints ---

    def get_overview(self) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/api/v1/analytics/overview", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def get_recent_questions(self, limit: int = 10) -> List[Dict[str, Any]]:
        r = requests.get(f"{self.base_url}/api/v1/analytics/recent-questions?limit={limit}", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def get_low_rated_answers(self, limit: int = 10) -> List[Dict[str, Any]]:
        r = requests.get(f"{self.base_url}/api/v1/analytics/low-rated-answers?limit={limit}", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def get_document_status(self) -> Dict[str, int]:
        r = requests.get(f"{self.base_url}/api/v1/analytics/document-status", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    # --- Documents Management ---

    def upload_document(self, file_name: str, file_bytes: bytes, content_type: str, category: Optional[str] = None, visibility: str = "public") -> Dict[str, Any]:
        files = {"file": (file_name, file_bytes, content_type)}
        data = {"visibility": visibility}
        if category:
            data["category"] = category
        r = requests.post(f"{self.base_url}/api/v1/documents/upload", files=files, data=data, headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def list_documents(self, page: int = 1, size: int = 20, status: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/documents?page={page}&size={size}"
        if status:
            url += f"&status={status}"
        r = requests.get(url, headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def get_document_details(self, document_id: str) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/api/v1/documents/{document_id}", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def run_extraction(self, document_id: str) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}/api/v1/documents/{document_id}/extract", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def run_chunking(self, document_id: str) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}/api/v1/documents/{document_id}/chunks", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def run_embeddings(self, document_id: str) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}/api/v1/documents/{document_id}/embeddings", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def run_indexing(self, document_id: str) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}/api/v1/documents/{document_id}/index", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    # --- Chat Sessions ---

    def create_chat_session(self) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}/api/v1/chat/sessions", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def list_chat_sessions(self) -> List[Dict[str, Any]]:
        r = requests.get(f"{self.base_url}/api/v1/chat/sessions", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def get_chat_session(self, session_id: str) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/api/v1/chat/sessions/{session_id}", headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    def ask_session_question(self, session_id: str, question: str) -> Dict[str, Any]:
        data = {"question": question}
        r = requests.post(f"{self.base_url}/api/v1/chat/sessions/{session_id}/answer", json=data, headers=self._get_headers())
        r.raise_for_status()
        return r.json()

    # --- Feedback ---

    def submit_feedback(self, message_id: str, rating: str, comment: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "message_id": message_id,
            "rating": rating
        }
        if comment:
            data["comment"] = comment
        r = requests.post(f"{self.base_url}/api/v1/feedback", json=data, headers=self._get_headers())
        r.raise_for_status()
        return r.json()
