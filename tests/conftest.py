import os
import tempfile
from pathlib import Path

# Must happen before any `app.*` module is imported anywhere in the test
# session — app.config.settings is a singleton built at import time, and the
# storage repos bind to its file paths at import time too. Redirecting DATA_DIR
# here keeps tests from ever touching the real data/ directory.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="procurement_test_data_"))
os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["UPLOAD_DIR"] = str(_TEST_DATA_DIR / "uploads")
os.environ["GEMINI_API_KEY"] = "test-gemini-key-placeholder"
os.environ["JWT_SECRET"] = "test-secret-for-pytest-only-not-for-real-use"

import pytest  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seed_test_users():
    import json

    users = [
        {
            "user_id": "usr_req_test", "username": "test_requester", "password_hash": hash_password("pw"),
            "role": "requester", "domain": "internal", "vendor_id": None, "approval_level": None, "is_active": True,
        },
        {
            "user_id": "usr_req_test2", "username": "test_requester2", "password_hash": hash_password("pw"),
            "role": "requester", "domain": "internal", "vendor_id": None, "approval_level": None, "is_active": True,
        },
        {
            "user_id": "usr_apr_test", "username": "test_approver", "password_hash": hash_password("pw"),
            "role": "approver", "domain": "internal", "vendor_id": None, "approval_level": 1, "is_active": True,
        },
        {
            "user_id": "usr_vnd_test", "username": "test_vendor", "password_hash": hash_password("pw"),
            "role": "vendor", "domain": "vendor", "vendor_id": "vnd_test_001", "approval_level": None, "is_active": True,
        },
        {
            "user_id": "usr_vnd_test2", "username": "test_vendor2", "password_hash": hash_password("pw"),
            "role": "vendor", "domain": "vendor", "vendor_id": "vnd_test_002", "approval_level": None, "is_active": True,
        },
        {
            "user_id": "usr_admin_test", "username": "test_admin", "password_hash": hash_password("pw"),
            "role": "super_admin", "domain": "internal", "vendor_id": None, "approval_level": None, "is_active": True,
        },
    ]
    settings.users_file.write_text(json.dumps({"users": users}, indent=2))
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)


@pytest.fixture
def tokens(client):
    def _login(username: str) -> str:
        resp = client.post("/auth/login", json={"username": username, "password": "pw"})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return {
        "requester": _login("test_requester"),
        "requester2": _login("test_requester2"),
        "approver": _login("test_approver"),
        "vendor": _login("test_vendor"),
        "vendor2": _login("test_vendor2"),
        "admin": _login("test_admin"),
    }


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
