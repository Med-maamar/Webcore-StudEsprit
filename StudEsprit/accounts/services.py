from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

from argon2 import PasswordHasher
import secrets
from bson import ObjectId

from core.mongo import get_db

ph = PasswordHasher()


def create_user(email: str, username: str, password: str, role: str = "Student") -> Dict[str, Any]:
    db = get_db()
    now = datetime.utcnow()
    doc = {
        "email": email.lower().strip(),
        "username": username,
        "password_hash": ph.hash(password),
        "role": role,
        "avatar_url": None,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    res = db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


def find_user_by_email(email: str):
    return get_db().users.find_one({"email": email.lower().strip()})


def find_user_by_id(user_id: str):
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    return get_db().users.find_one({"_id": oid})


def change_password(user_id: str, new_password: str) -> None:
    get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": ph.hash(new_password), "updated_at": datetime.utcnow()}},
    )


def update_user_profile(user_id: str, username: Optional[str], avatar_url: Optional[str]) -> None:
    updates = {"updated_at": datetime.utcnow()}
    if username is not None:
        updates["username"] = username
    if avatar_url is not None:
        updates["avatar_url"] = avatar_url
    get_db().users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})


def record_login_audit(user_id: str, ip: str, user_agent: str) -> None:
    get_db().audit_auth.insert_one(
        {
            "user_id": ObjectId(user_id),
            "ip": ip,
            "user_agent": user_agent,
            "created_at": datetime.utcnow(),
        }
    )


def query_users(q: Optional[str] = None, role: Optional[str] = None, page: int = 1, page_size: int = 10) -> Tuple[List[Dict], int]:
    db = get_db()
    filt: Dict[str, Any] = {}
    if q:
        # Simple case-insensitive regex on email or username
        filt["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"username": {"$regex": q, "$options": "i"}},
        ]
    if role and role in {"Student", "Admin"}:
        filt["role"] = role
    total = db.users.count_documents(filt)
    cursor = (
        db.users.find(filt).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    )
    return list(cursor), total


def generate_unique_username(base: str) -> str:
    db = get_db()
    base = (base or "user").lower().strip().replace(" ", "_")
    cand = base
    i = 0
    while db.users.find_one({"username": cand}):
        i += 1
        cand = f"{base}{i}"
    return cand


def get_or_create_user_from_google(*, email: str, full_name: Optional[str], avatar_url: Optional[str], google_sub: str) -> Dict[str, Any]:
    db = get_db()
    now = datetime.utcnow()
    email = email.lower().strip()
    user = db.users.find_one({"email": email})
    if user:
        # ensure link
        updates: Dict[str, Any] = {"updated_at": now}
        if not user.get("google_id"):
            updates["google_id"] = google_sub
        if avatar_url and not user.get("avatar_url"):
            updates["avatar_url"] = avatar_url
        if updates:
            db.users.update_one({"_id": user["_id"]}, {"$set": updates})
        return db.users.find_one({"_id": user["_id"]})

    # create with random password
    username_base = (full_name or email.split("@")[0])
    username = generate_unique_username(username_base)
    random_pw = secrets.token_urlsafe(32)
    doc = {
        "email": email,
        "username": username,
        "password_hash": ph.hash(random_pw),
        "role": "Student",
        "avatar_url": avatar_url,
        "google_id": google_sub,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    res = db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc
