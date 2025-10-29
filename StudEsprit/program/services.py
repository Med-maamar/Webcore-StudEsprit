from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime

from core.mongo import get_db
from bson.objectid import ObjectId
import logging
from django.conf import settings
from django.core.files.storage import default_storage
import os

logger = logging.getLogger(__name__)


COLLECTION_NAME = "niveaux"


def create_niveau(nom: str, description: str) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "nom": nom,
        "description": description,
        "created_at": datetime.utcnow(),
    }
    result = db[COLLECTION_NAME].insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["id"] = str(result.inserted_id)
    return doc


def get_niveau(niveau_id) -> Optional[Dict[str, Any]]:
    db = get_db()
    # Be tolerant with id shapes: try ObjectId, string _id, or 'id' field
    candidates = []
    try:
        oid = ObjectId(niveau_id)
        candidates.append({"_id": oid})
    except Exception:
        pass
    candidates.append({"_id": niveau_id})
    candidates.append({"id": niveau_id})
    try:
        return db[COLLECTION_NAME].find_one({"$or": candidates})
    except Exception:
        # fallback to original behavior
        try:
            return db[COLLECTION_NAME].find_one({"_id": niveau_id})
        except Exception:
            return None


def list_niveaux(q: Optional[str] = None, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
    db = get_db()
    query: Dict[str, Any] = {}
    if q:
        # case-insensitive substring search on nom
        query["nom"] = {"$regex": q, "$options": "i"}
    cursor = db[COLLECTION_NAME].find(query).skip(skip).limit(limit)
    docs = list(cursor)
    # expose safe id string for templates (avoid accessing _id in templates)
    for d in docs:
        d["id"] = str(d.get("_id"))
    return docs


def count_niveaux(q: Optional[str] = None) -> int:
    db = get_db()
    query: Dict[str, Any] = {}
    if q:
        query["nom"] = {"$regex": q, "$options": "i"}
    try:
        return int(db[COLLECTION_NAME].count_documents(query))
    except Exception:
        # fallback for older drivers or errors
        try:
            return len(list(db[COLLECTION_NAME].find(query)))
        except Exception:
            return 0


def update_niveau(niveau_id, data: Dict[str, Any]) -> bool:
    db = get_db()
    try:
        oid = ObjectId(niveau_id)
    except Exception:
        oid = niveau_id
    res = db[COLLECTION_NAME].update_one({"_id": oid}, {"$set": data})
    try:
        logger.info("update_niveau oid=%s matched=%s modified=%s", oid, getattr(res, 'matched_count', None), getattr(res, 'modified_count', None))
    except Exception:
        pass
    return res.modified_count > 0


def delete_niveau(niveau_id) -> bool:
    db = get_db()
    # Accept string id or ObjectId
    try:
        oid = ObjectId(niveau_id)
    except Exception:
        oid = niveau_id
    # Delete the niveau
    res = db[COLLECTION_NAME].delete_one({"_id": oid})
    deleted = res.deleted_count > 0
    if deleted:
        # Cascade: delete matieres that reference this niveau
        try:
            db[MATIERE_COLLECTION].delete_many({"niveau_id": niveau_id})
        except Exception:
            pass
        try:
            db[MATIERE_COLLECTION].delete_many({"niveau_id": oid})
        except Exception:
            pass

        # Now delete any cours that reference matieres of this niveau; remove files first
        try:
            matieres = list(db[MATIERE_COLLECTION].find({"niveau_id": {"$in": [niveau_id, oid]}}, {"_id": 1}))
            mat_ids = [str(m.get("_id")) for m in matieres]
            if mat_ids:
                # find cours to delete and remove their files
                cours_to_remove = list(db[COURS_COLLECTION].find({"matiere_id": {"$in": mat_ids}}, {"courpdf": 1}))
                for c in cours_to_remove:
                    try:
                        _delete_course_file(c.get("courpdf"))
                    except Exception:
                        pass
                db[COURS_COLLECTION].delete_many({"matiere_id": {"$in": mat_ids}})
        except Exception:
            # fallback: try matching by niveau_id directly
            try:
                cours_to_remove = list(db[COURS_COLLECTION].find({"matiere_id": niveau_id}, {"courpdf": 1}))
                for c in cours_to_remove:
                    try:
                        _delete_course_file(c.get("courpdf"))
                    except Exception:
                        pass
                db[COURS_COLLECTION].delete_many({"matiere_id": niveau_id})
            except Exception:
                pass
    return deleted


# Matiere helpers (many-to-one to niveaux)
MATIERE_COLLECTION = "matieres"


def create_matiere(nom: str, description: str, niveau_id, coefficient: float = None) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "nom": nom,
        "description": description,
        "niveau_id": niveau_id,
        "created_at": datetime.utcnow(),
    }
    # store coefficient on matiere when provided (backwards compatible)
    if coefficient is not None:
        try:
            doc['coefficient'] = float(coefficient)
        except Exception:
            doc['coefficient'] = coefficient
    result = db[MATIERE_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["id"] = str(result.inserted_id)
    return doc


def get_matiere(matiere_id) -> Optional[Dict[str, Any]]:
    db = get_db()
    # Accept several id shapes: ObjectId, string _id, or stored `id` field
    candidates = []
    try:
        oid = ObjectId(matiere_id)
        candidates.append({"_id": oid})
    except Exception:
        pass
    candidates.append({"_id": matiere_id})
    candidates.append({"id": matiere_id})
    try:
        return db[MATIERE_COLLECTION].find_one({"$or": candidates})
    except Exception:
        # fallback: try simplest lookup
        try:
            return db[MATIERE_COLLECTION].find_one({"_id": matiere_id})
        except Exception:
            return None


def list_matieres(q: Optional[str] = None, niveau_id=None, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
    db = get_db()
    query: Dict[str, Any] = {}
    if q:
        query["nom"] = {"$regex": q, "$options": "i"}
    if niveau_id:
        query["niveau_id"] = niveau_id
    cursor = db[MATIERE_COLLECTION].find(query).skip(skip).limit(limit)
    docs = list(cursor)
    for d in docs:
        d["id"] = str(d.get("_id"))
    return docs


def count_matieres(q: Optional[str] = None, niveau_id=None) -> int:
    db = get_db()
    query: Dict[str, Any] = {}
    if q:
        query["nom"] = {"$regex": q, "$options": "i"}
    if niveau_id:
        query["niveau_id"] = niveau_id
    try:
        return int(db[MATIERE_COLLECTION].count_documents(query))
    except Exception:
        try:
            return len(list(db[MATIERE_COLLECTION].find(query)))
        except Exception:
            return 0


def update_matiere(matiere_id, data: Dict[str, Any]) -> bool:
    db = get_db()
    try:
        oid = ObjectId(matiere_id)
    except Exception:
        oid = matiere_id
    res = db[MATIERE_COLLECTION].update_one({"_id": oid}, {"$set": data})
    try:
        logger.info("update_matiere oid=%s matched=%s modified=%s", oid, getattr(res, 'matched_count', None), getattr(res, 'modified_count', None))
    except Exception:
        pass
    return res.modified_count > 0


def delete_matiere(matiere_id) -> bool:
    db = get_db()
    try:
        oid = ObjectId(matiere_id)
    except Exception:
        oid = matiere_id
    res = db[MATIERE_COLLECTION].delete_one({"_id": oid})
    deleted = res.deleted_count > 0
    if deleted:
        # Cascade: delete cours referencing this matiere and remove files
        try:
            cours_docs = list(db[COURS_COLLECTION].find({"matiere_id": matiere_id}, {"courpdf": 1}))
            for c in cours_docs:
                try:
                    _delete_course_file(c.get("courpdf"))
                except Exception:
                    pass
            db[COURS_COLLECTION].delete_many({"matiere_id": matiere_id})
        except Exception:
            pass
        try:
            cours_docs = list(db[COURS_COLLECTION].find({"matiere_id": oid}, {"courpdf": 1}))
            for c in cours_docs:
                try:
                    _delete_course_file(c.get("courpdf"))
                except Exception:
                    pass
            db[COURS_COLLECTION].delete_many({"matiere_id": oid})
        except Exception:
            pass
    return deleted


# Cours helpers (many-to-one to matieres)
COURS_COLLECTION = "cours"


def create_cour(nom: str, description: str, coefficient: float, matiere_id, courpdf: str = None) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "nom": nom,
        "description": description,
        "coefficient": coefficient,
        "matiere_id": matiere_id,
        "courpdf": courpdf,
        "created_at": datetime.utcnow(),
    }
    result = db[COURS_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["id"] = str(result.inserted_id)
    return doc


def get_cour(cour_id) -> Optional[Dict[str, Any]]:
    db = get_db()
    # Accept ObjectId or string id forms
    candidates = []
    try:
        oid = ObjectId(cour_id)
        candidates.append({"_id": oid})
    except Exception:
        pass
    candidates.append({"_id": cour_id})
    candidates.append({"id": cour_id})
    try:
        return db[COURS_COLLECTION].find_one({"$or": candidates})
    except Exception:
        try:
            return db[COURS_COLLECTION].find_one({"_id": cour_id})
        except Exception:
            return None


def list_cours(q: Optional[str] = None, matiere_id=None, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
    db = get_db()
    query: Dict[str, Any] = {}
    if q:
        query["nom"] = {"$regex": q, "$options": "i"}
    if matiere_id:
        query["matiere_id"] = matiere_id
    cursor = db[COURS_COLLECTION].find(query).skip(skip).limit(limit)
    docs = list(cursor)
    for d in docs:
        d["id"] = str(d.get("_id"))
    return docs


def count_cours(q: Optional[str] = None, matiere_id=None) -> int:
    db = get_db()
    query: Dict[str, Any] = {}
    if q:
        query["nom"] = {"$regex": q, "$options": "i"}
    if matiere_id:
        query["matiere_id"] = matiere_id
    try:
        return int(db[COURS_COLLECTION].count_documents(query))
    except Exception:
        try:
            return len(list(db[COURS_COLLECTION].find(query)))
        except Exception:
            return 0


def update_cour(cour_id, data: Dict[str, Any]) -> bool:
    db = get_db()
    try:
        oid = ObjectId(cour_id)
    except Exception:
        oid = cour_id
    # allow updating courpdf if present in data
    res = db[COURS_COLLECTION].update_one({"_id": oid}, {"$set": data})
    try:
        logger.info("update_cour oid=%s matched=%s modified=%s", oid, getattr(res, 'matched_count', None), getattr(res, 'modified_count', None))
    except Exception:
        pass
    return res.modified_count > 0


def delete_cour(cour_id) -> bool:
    db = get_db()
    try:
        oid = ObjectId(cour_id)
    except Exception:
        oid = cour_id
    # delete associated file first (if any)
    try:
        c = db[COURS_COLLECTION].find_one({"_id": oid}, {"courpdf": 1})
    except Exception:
        c = None
    if c:
        try:
            _delete_course_file(c.get("courpdf"))
        except Exception:
            pass
    res = db[COURS_COLLECTION].delete_one({"_id": oid})
    return res.deleted_count > 0


def _delete_course_file(courpdf):
    """Try to remove a stored course PDF via Django's default_storage.

    The stored `courpdf` may be a storage path, a MEDIA_URL-prefixed path, or a full URL.
    Try several candidate paths and delete the first that exists.
    """
    if not courpdf:
        return
    try:
        media_url = settings.MEDIA_URL or '/media/'
    except Exception:
        media_url = '/media/'

    candidates = []
    if isinstance(courpdf, str):
        candidates.append(courpdf)
        # if it starts with MEDIA_URL
        if courpdf.startswith(media_url):
            candidates.append(courpdf[len(media_url):].lstrip('/'))
        # if full URL contains MEDIA_URL
        if media_url in courpdf:
            idx = courpdf.find(media_url)
            candidates.append(courpdf[idx + len(media_url):].lstrip('/'))
        # basename
        candidates.append(os.path.basename(courpdf))

    for p in candidates:
        if not p:
            continue
        try:
            if default_storage.exists(p):
                default_storage.delete(p)
                return
        except Exception:
            pass
