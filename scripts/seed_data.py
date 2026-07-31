"""Run once to populate data/users.json with local test accounts.
Usage: .venv/bin/python scripts/seed_data.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.security import hash_password  # noqa: E402
from app.config import settings  # noqa: E402

USERS = [
    {
        "user_id": "usr_req_001", "username": "alice", "password": "alicepw123",
        "full_name": "Alice Requester", "role": "requester", "domain": "internal",
        "vendor_id": None, "approval_level": None, "is_active": True,
    },
    {
        "user_id": "usr_req_002", "username": "carol", "password": "carolpw123",
        "full_name": "Carol Requester", "role": "requester", "domain": "internal",
        "vendor_id": None, "approval_level": None, "is_active": True,
    },
    {
        "user_id": "usr_apr_001", "username": "bob", "password": "bobpw123",
        "full_name": "Bob Approver", "role": "approver", "domain": "internal",
        "vendor_id": None, "approval_level": 1, "is_active": True,
    },
    {
        "user_id": "usr_vnd_acme", "username": "acme_sales", "password": "acmepw123",
        "full_name": "Acme Sales", "role": "vendor", "domain": "vendor",
        "vendor_id": "vnd_acme_001", "approval_level": None, "is_active": True,
    },
    {
        "user_id": "usr_vnd_globex", "username": "globex_sales", "password": "globexpw123",
        "full_name": "Globex Sales", "role": "vendor", "domain": "vendor",
        "vendor_id": "vnd_globex_001", "approval_level": None, "is_active": True,
    },
    {
        "user_id": "usr_admin_001", "username": "admin", "password": "adminpw123",
        "full_name": "System Admin", "role": "super_admin", "domain": "internal",
        "vendor_id": None, "approval_level": None, "is_active": True,
    },
]


def main() -> None:
    users = []
    for u in USERS:
        record = {k: v for k, v in u.items() if k != "password"}
        record["password_hash"] = hash_password(u["password"])
        users.append(record)

    settings.users_file.write_text(json.dumps({"users": users}, indent=2))
    print(f"Wrote {len(users)} users to {settings.users_file}")
    for u in USERS:
        print(f"  {u['username']} / {u['password']}  ({u['role']})")


if __name__ == "__main__":
    main()
