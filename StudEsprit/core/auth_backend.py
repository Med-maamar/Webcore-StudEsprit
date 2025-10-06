from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from argon2 import PasswordHasher
from bson import ObjectId

from core.mongo import get_db


@dataclass
class MongoUser:
    id: str
    email: str
    username: str
    role: str

    @property
    def is_authenticated(self) -> bool:  # Django-like API
        return True

    @property
    def is_anonymous(self) -> bool:
        return False


class MongoAuthBackend:
    """Custom auth backend that validates credentials against MongoDB."""

    ph = PasswordHasher()

    def authenticate(self, request, email: Optional[str] = None, password: Optional[str] = None, **kwargs):
        if not email or not password:
            return None
        db = get_db()
        user = db.users.find_one({"email": email.lower().strip()})
        if not user:
            return None
        try:
            self.ph.verify(user.get("password_hash", ""), password)
        except Exception:
            return None
        # Optionally check other flags later (e.g., is_active)
        return MongoUser(
            id=str(user["_id"]),
            email=user["email"],
            username=user.get("username", ""),
            role=user.get("role", "Student"),
        )

    def get_user(self, user_id: str):
        if not user_id:
            return None
        db = get_db()
        try:
            doc = db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        if not doc:
            return None
        return MongoUser(
            id=str(doc["_id"]),
            email=doc["email"],
            username=doc.get("username", ""),
            role=doc.get("role", "Student"),
        )

