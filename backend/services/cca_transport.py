import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

class CCATransportError(Exception):
    def __init__(self, error_id, message, status_code=None):
        super().__init__(message)
        self.error_id = error_id
        self.message = message
        self.status_code = status_code

class CCATransport:
    def __init__(self):
        self.base_url = os.getenv("CCA_API_URL", "").rstrip("/")
        self.username = os.getenv("CCA_USERNAME", "")
        self.password = os.getenv("CCA_PASSWORD", "")
        self.timeout = int(os.getenv("CCA_TIMEOUT", "30"))
        self.max_attempts = int(os.getenv("CCA_MAX_ATTEMPTS", "3"))
        self.backoffs = (1, 2, 4)
        self.session = requests.Session()

    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def acquire_session(self) -> dict:
        if not self.is_configured():
            return {"sessionId": "mock-session-id", "mock": True}
        
        url = f"{self.base_url}/api/session"
        res = self.session.post(url, json={"username": self.username, "password": self.password}, timeout=self.timeout)
        if res.status_code == 200:
            return res.json()
        raise CCATransportError(error_id="1", message="Failed to acquire CCA session", status_code=res.status_code)

    def submit_with_retry(self, session_id: str, payload: dict) -> dict:
        if not self.is_configured():
            return {"success": True, "attempts": 1, "response": {"status": "mock_saved"}}

        current_session = session_id
        url = f"{self.base_url}/api/assessment/save/answers"

        for attempt in range(1, self.max_attempts + 1):
            try:
                headers = {"Authorization": f"Bearer {current_session}"}
                res = self.session.post(url, json=payload, headers=headers, timeout=self.timeout)
                
                if res.status_code == 200 and "<ERROR" not in res.text:
                    return {"success": True, "attempts": attempt, "response": res.json() if res.headers.get("content-type") == "application/json" else res.text}

                # Catch Invalid Session (id=1) -> refresh session once
                if 'id="1"' in res.text or res.status_code == 401:
                    logger.warning("Session invalid. Re-acquiring session...")
                    new_session = self.acquire_session()
                    current_session = new_session.get("sessionId")
                    continue

                # Catch DBTimeout (id=1000)
                if 'id="1000"' in res.text or res.status_code == 504:
                    if attempt < self.max_attempts:
                        sleep_time = self.backoffs[attempt - 1]
                        logger.warning(f"DB timeout encountered. Retrying in {sleep_time}s (attempt {attempt}/{self.max_attempts})...")
                        time.sleep(sleep_time)
                        continue

                return {"success": False, "attempts": attempt, "error_id": "CCA_ERROR", "error_message": res.text}

            except requests.exceptions.RequestException as e:
                if attempt < self.max_attempts:
                    time.sleep(self.backoffs[attempt - 1])
                    continue
                return {"success": False, "attempts": attempt, "error_id": "1000", "error_message": str(e)}

        return {"success": False, "attempts": self.max_attempts, "error_id": "1000", "error_message": "Max retry attempts exceeded"}