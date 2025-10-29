"""
Library models for document storage, chat history, and metadata.
Uses MongoDB collections for data persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional
from bson import ObjectId
from pymongo.errors import PyMongoError

from core.mongo import get_db


class DocumentService:
    """Service class for managing documents in MongoDB."""
    
    @staticmethod
    def create_document(
        user_id: str,
        title: str,
        filename: str,
        file_path: str,
        file_size: int,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new document record."""
        db = get_db()
        now = datetime.utcnow()
        
        doc = {
            "user_id": ObjectId(user_id),
            "title": title,
            "filename": filename,
            "file_path": file_path,
            "file_size": file_size,
            "content": content,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
            "is_processed": False,
            "paragraphs": [],
            "paragraph_embeddings": []
        }
        
        result = db.documents.insert_one(doc)
        return str(result.inserted_id)
    
    @staticmethod
    def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            return None
        
        return get_db().documents.find_one({"_id": oid})
    
    @staticmethod
    def get_user_documents(user_id: str, page: int = 1, page_size: int = 10) -> tuple[List[Dict], int]:
        """Get documents for a specific user with pagination."""
        db = get_db()
        user_oid = ObjectId(user_id)
        
        total = db.documents.count_documents({"user_id": user_oid})
        cursor = (
            db.documents.find({"user_id": user_oid})
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        
        return list(cursor), total
    
    @staticmethod
    def update_document_processing(doc_id: str, paragraphs: List[str], embeddings: List[List[float]]) -> None:
        """Update document with processed paragraphs and embeddings."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            return
        
        get_db().documents.update_one(
            {"_id": oid},
            {
                "$set": {
                    "is_processed": True,
                    "paragraphs": paragraphs,
                    "paragraph_embeddings": embeddings,
                    "updated_at": datetime.utcnow()
                }
            }
        )

    @staticmethod
    def append_quiz_result(doc_id: str, quiz_result: Dict[str, Any]) -> bool:
        """Append a quiz result entry to a document record (stored in `quizzes` list)."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            return False

        res = get_db().documents.update_one(
            {"_id": oid},
            {
                "$push": {"quizzes": quiz_result},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return res.modified_count > 0
    
    @staticmethod
    def delete_document(doc_id: str, user_id: str) -> bool:
        """Delete a document (only if owned by user)."""
        try:
            doc_oid = ObjectId(doc_id)
            user_oid = ObjectId(user_id)
        except Exception:
            return False
        
        result = get_db().documents.delete_one({
            "_id": doc_oid,
            "user_id": user_oid
        })
        
        return result.deleted_count > 0


class ChatService:
    """Service class for managing chat sessions and messages."""
    
    @staticmethod
    def create_chat_session(user_id: str, document_id: Optional[str] = None) -> str:
        """Create a new chat session."""
        db = get_db()
        now = datetime.utcnow()
        
        session = {
            "user_id": ObjectId(user_id),
            "document_id": ObjectId(document_id) if document_id else None,
            "created_at": now,
            "updated_at": now,
            "messages": []
        }
        
        result = db.chat_sessions.insert_one(session)
        return str(result.inserted_id)
    
    @staticmethod
    def get_chat_session(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID (only if owned by user)."""
        try:
            session_oid = ObjectId(session_id)
            user_oid = ObjectId(user_id)
        except Exception:
            return None
        
        return get_db().chat_sessions.find_one({
            "_id": session_oid,
            "user_id": user_oid
        })
    
    @staticmethod
    def get_user_chat_sessions(user_id: str, page: int = 1, page_size: int = 10) -> tuple[List[Dict], int]:
        """Get chat sessions for a user with pagination."""
        db = get_db()
        user_oid = ObjectId(user_id)
        
        total = db.chat_sessions.count_documents({"user_id": user_oid})
        cursor = (
            db.chat_sessions.find({"user_id": user_oid})
            .sort("updated_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        
        return list(cursor), total
    
    @staticmethod
    def add_message_to_session(
        session_id: str,
        user_id: str,
        message_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a message to a chat session."""
        try:
            session_oid = ObjectId(session_id)
            user_oid = ObjectId(user_id)
        except Exception:
            return False
        
        message = {
            "type": message_type,  # 'user' or 'assistant'
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow()
        }
        
        result = get_db().chat_sessions.update_one(
            {
                "_id": session_oid,
                "user_id": user_oid
            },
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def delete_chat_session(session_id: str, user_id: str) -> bool:
        """Delete a chat session."""
        try:
            session_oid = ObjectId(session_id)
            user_oid = ObjectId(user_id)
        except Exception:
            return False
        
        result = get_db().chat_sessions.delete_one({
            "_id": session_oid,
            "user_id": user_oid
        })
        
        return result.deleted_count > 0


class EmbeddingService:
    """Service class for managing document embeddings and semantic search."""
    
    @staticmethod
    def get_document_embeddings(doc_id: str) -> tuple[List[str], List[List[float]]]:
        """Get paragraphs and embeddings for a document."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            return [], []
        
        doc = get_db().documents.find_one(
            {"_id": oid},
            {"paragraphs": 1, "paragraph_embeddings": 1}
        )
        
        if not doc:
            return [], []
        
        return doc.get("paragraphs", []), doc.get("paragraph_embeddings", [])
    
    @staticmethod
    def search_similar_paragraphs(
        query_embedding: List[float],
        user_doc_ids: List[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar paragraphs using cosine similarity."""
        db = get_db()
        results = []
        
        # Convert string IDs to ObjectIds
        doc_oids = []
        for doc_id in user_doc_ids:
            try:
                doc_oids.append(ObjectId(doc_id))
            except Exception:
                continue
        
        if not doc_oids:
            return results
        
        # Get all documents with embeddings
        docs = db.documents.find(
            {
                "_id": {"$in": doc_oids},
                "is_processed": True,
                "paragraph_embeddings": {"$exists": True, "$ne": []}
            },
            {"title": 1, "paragraphs": 1, "paragraph_embeddings": 1}
        )
        
        for doc in docs:
            doc_id = str(doc["_id"])
            title = doc.get("title", "Unknown")
            paragraphs = doc.get("paragraphs", [])
            embeddings = doc.get("paragraph_embeddings", [])
            
            # Calculate cosine similarity for each paragraph
            for i, (paragraph, embedding) in enumerate(zip(paragraphs, embeddings)):
                if len(embedding) != len(query_embedding):
                    continue
                
                # Cosine similarity
                dot_product = sum(a * b for a, b in zip(query_embedding, embedding))
                norm_a = sum(a * a for a in query_embedding) ** 0.5
                norm_b = sum(b * b for b in embedding) ** 0.5
                
                if norm_a == 0 or norm_b == 0:
                    continue
                
                similarity = dot_product / (norm_a * norm_b)
                
                results.append({
                    "document_id": doc_id,
                    "document_title": title,
                    "paragraph_index": i,
                    "paragraph": paragraph,
                    "similarity": similarity
                })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


def ensure_library_indexes() -> None:
    """Create indexes for library collections."""
    db = get_db()
    
    try:
        # Document indexes
        db.documents.create_index("user_id")
        db.documents.create_index("created_at")
        db.documents.create_index("is_processed")
        db.documents.create_index([("user_id", 1), ("created_at", -1)])
        
        # Chat session indexes
        db.chat_sessions.create_index("user_id")
        db.chat_sessions.create_index("document_id")
        db.chat_sessions.create_index("created_at")
        db.chat_sessions.create_index([("user_id", 1), ("updated_at", -1)])
        
    except PyMongoError:
        pass


class CommunityService:
    """Service for community features - posts, comments, and interactions."""
    
    @staticmethod
    def create_post(
        user_id: str,
        title: str,
        content: str,
        category: str = "general",
        tags: List[str] = None,
        attachments: List[Dict[str, Any]] = None,
        service_offer: bool = False,
        service_description: str = None,
        contact_pref: str = None,
    ) -> str:
        """Create a new community post. Attachments is a list of dicts with keys: name, url, size, content_type."""
        db = get_db()
        now = datetime.utcnow()
        post = {
            "user_id": ObjectId(user_id),
            "title": title,
            "content": content,
            "category": category,
            "tags": tags or [],
            "attachments": attachments or [],
            "service_offer": bool(service_offer),
            "service_description": service_description or "",
            "contact_pref": contact_pref or "",
            "likes": [],
            "comments": [],
            "views": 0,
            "is_pinned": False,
            "is_solved": False,
            "created_at": now,
            "updated_at": now,
        }
        result = db.community_posts.insert_one(post)
        return str(result.inserted_id)
    
    @staticmethod
    def get_post_by_id(post_id: str) -> Optional[Dict]:
        """Get a post by ID."""
        db = get_db()
        try:
            return db.community_posts.find_one({"_id": ObjectId(post_id)})
        except Exception:
            return None
    
    @staticmethod
    def get_posts(page: int = 1, page_size: int = 10, category: str = None, search: str = None) -> Tuple[List[Dict], int]:
        """Get community posts with pagination and filtering."""
        db = get_db()
        skip = (page - 1) * page_size
        
        # Build query
        query = {}
        if category and category != "all":
            query["category"] = category
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}},
                {"tags": {"$in": [{"$regex": search, "$options": "i"}]}}
            ]
        
        # Get posts (pinned first, then by updated_at)
        posts = list(db.community_posts.find(query)
                    .sort([("is_pinned", -1), ("updated_at", -1)])
                    .skip(skip)
                    .limit(page_size))
        
        total = db.community_posts.count_documents(query)
        return posts, total
    
    @staticmethod
    def add_comment(post_id: str, user_id: str, content: str) -> str:
        """Add a comment to a post."""
        db = get_db()
        now = datetime.utcnow()
        comment = {
            "user_id": ObjectId(user_id),
            "content": content,
            "likes": [],
            "created_at": now,
            "updated_at": now,
        }
        
        # Add comment to post
        result = db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$push": {"comments": comment},
                "$set": {"updated_at": now}
            }
        )
        
        if result.modified_count > 0:
            return "success"
        return "error"
    
    @staticmethod
    def toggle_like(post_id: str, user_id: str) -> Dict[str, Any]:
        """Toggle like on a post."""
        db = get_db()
        post = db.community_posts.find_one({"_id": ObjectId(post_id)})
        
        if not post:
            return {"success": False, "error": "Post not found"}
        
        user_obj_id = ObjectId(user_id)
        likes = post.get("likes", [])
        
        if user_obj_id in likes:
            # Remove like
            db.community_posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$pull": {"likes": user_obj_id}}
            )
            return {"success": True, "liked": False, "count": len(likes) - 1}
        else:
            # Add like
            db.community_posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$push": {"likes": user_obj_id}}
            )
            return {"success": True, "liked": True, "count": len(likes) + 1}
    
    @staticmethod
    def increment_views(post_id: str) -> None:
        """Increment view count for a post."""
        db = get_db()
        db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"views": 1}}
        )
    
    @staticmethod
    def get_user_posts(user_id: str, page: int = 1, page_size: int = 10) -> Tuple[List[Dict], int]:
        """Get posts by a specific user."""
        db = get_db()
        skip = (page - 1) * page_size
        posts = list(db.community_posts.find({"user_id": ObjectId(user_id)})
                    .sort("created_at", -1)
                    .skip(skip)
                    .limit(page_size))
        total = db.community_posts.count_documents({"user_id": ObjectId(user_id)})
        return posts, total
    
    @staticmethod
    def get_popular_posts(limit: int = 5) -> List[Dict]:
        """Get most popular posts (by likes and views)."""
        db = get_db()
        # Sort by combination of likes count and views
        pipeline = [
            {
                "$addFields": {
                    "popularity_score": {
                        "$add": [
                            {"$size": "$likes"},
                            {"$multiply": [{"$divide": ["$views", 10]}, 1]}
                        ]
                    }
                }
            },
            {"$sort": {"popularity_score": -1}},
            {"$limit": limit}
        ]
        return list(db.community_posts.aggregate(pipeline))
    
    @staticmethod
    def get_categories() -> List[str]:
        """Get all available categories."""
        db = get_db()
        categories = db.community_posts.distinct("category")
        return categories
    
    @staticmethod
    def delete_post(post_id: str, user_id: str) -> bool:
        """Delete a post (only by the author)."""
        db = get_db()
        try:
            result = db.community_posts.delete_one({
                "_id": ObjectId(post_id),
                "user_id": ObjectId(user_id)
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting post {post_id}: {e}")
            return False
