from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import List, Dict, Any

from bson import ObjectId
from pymongo.errors import PyMongoError

from core.mongo import get_db


DIM = 384


def compute_embedding(text: str) -> List[float]:
    """Deterministic, pseudo-random vector for demo purposes.

    Uses SHA256 hashes to seed values and normalizes to unit length.
    """
    t = (text or "").encode("utf-8")
    v: List[float] = []
    # Derive 384 floats from repeated sha256 hashes
    seed = t
    while len(v) < DIM:
        h = hashlib.sha256(seed).digest()
        # take pairs of bytes as signed ints
        for i in range(0, len(h), 2):
            if len(v) >= DIM:
                break
            val = int.from_bytes(h[i : i + 2], "big", signed=False)
            # map to [-1, 1]
            v.append(((val % 1000) / 500.0) - 1.0)
        seed = h
    # normalize
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def upsert_profile_embedding(user_id: str, text: str) -> None:
    db = get_db()
    emb = compute_embedding(text)
    db.profiles_embeddings.update_one(
        {"user_id": ObjectId(user_id)},
        {"$set": {"embedding": emb, "updated_at": datetime.utcnow()}},
        upsert=True,
    )


def ensure_vector_index() -> None:
    """Create an Atlas Search vector index if running on MongoDB Atlas.

    This is a helper stub; on local dev, this may be a no-op.
    """
    # For Atlas, index creation is via Atlas UI/HTTP API; here we note intent.
    # We still create standard indexes for convenience.
    db = get_db()
    try:
        db.profiles_embeddings.create_index("user_id")
        db.profiles_embeddings.create_index("updated_at")
    except PyMongoError:
        pass


def vector_search(query_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """Attempt $vectorSearch; fallback to Python cosine similarity.

    Returns a list of {user_id: str, score: float}.
    """
    db = get_db()
    qv = compute_embedding(query_text)

    # Try Atlas $vectorSearch
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": qv,
                    "numCandidates": max(100, k * 20),
                    "limit": k,
                }
            },
            {"$project": {"user_id": 1, "_id": 0, "score": {"$meta": "vectorSearchScore"}}},
        ]
        results = list(db.profiles_embeddings.aggregate(pipeline))
        # convert ObjectIds to str if present
        for r in results:
            if isinstance(r.get("user_id"), ObjectId):
                r["user_id"] = str(r["user_id"])
        if results:
            return results
    except Exception:
        pass

    # Fallback: cosine similarity in Python
    rows = list(db.profiles_embeddings.find({}, {"user_id": 1, "embedding": 1}))
    scored = []
    for r in rows:
        ev = r.get("embedding") or []
        # pad/truncate
        if len(ev) != DIM:
            continue
        dot = sum(a * b for a, b in zip(qv, ev))
        scored.append({"user_id": str(r.get("user_id")), "score": float(dot)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]

