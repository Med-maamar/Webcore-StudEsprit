from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bson import ObjectId
from django.utils.deprecation import MiddlewareMixin

from core.mongo import get_db


@dataclass
class AnonymousUser:
    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def is_anonymous(self) -> bool:
        return True

    id: Optional[str] = None
    email: str = ""
    username: str = ""
    role: str = "Student"


class SessionUserMiddleware(MiddlewareMixin):
    """Attach request.user based on session['user_id'] sourced from MongoDB."""

    def process_request(self, request):
        user_id = request.session.get("user_id")
        if not user_id:
            request.user = AnonymousUser()
            return
        try:
            doc = get_db().users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            doc = None
        if not doc:
            request.user = AnonymousUser()
            return

        class _User:
            def __init__(self, d):
                self.id = str(d["_id"])  # str(ObjectId)
                self.email = d.get("email", "")
                self.username = d.get("username", "")
                self.role = d.get("role", "Student")

            @property
            def is_authenticated(self):
                return True

            @property
            def is_anonymous(self):
                return False

        request.user = _User(doc)

