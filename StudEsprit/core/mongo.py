from __future__ import annotations

import os
from typing import Optional
from datetime import datetime

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from django.conf import settings

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = getattr(settings, "MONGO_URI", os.getenv("MONGO_URI", "mongodb://localhost:27017"))
        _client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    return _client


def get_db():
    client = get_client()
    name = getattr(settings, "MONGO_DB_NAME", os.getenv("MONGO_DB_NAME", "studesprit"))
    return client[name]


def health_check() -> bool:
    try:
        client = get_client()
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False


def ensure_indexes() -> None:
    db = get_db()
    # Users unique indexes
    db.users.create_index("email", unique=True)
    db.users.create_index("username", unique=True)
    db.users.create_index("google_id")
    db.users.create_index("created_at")
    db.users.create_index("last_login_at")
    db.audit_auth.create_index("created_at")
