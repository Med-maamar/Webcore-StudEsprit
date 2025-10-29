"""Personalized study path service for StudEsprit.

This module provides the PersonalizedStudyPathAI service which analyses a user's
documents, builds topic/subtopic structures, tracks progress, and generates a
personalized study path. It persists progress to MongoDB and integrates with
existing AI and chat services.

Design goals:
- Use embeddings when available to find and group relevant paragraphs.
- Produce topic lists with difficulty estimation.
- Track progress and allow incremental updates.
- Provide an API to fetch/update the current study path.
- Integrate with AIService to generate exercises and chat responses in context.

"""
from __future__ import annotations

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from django.conf import settings

from core.mongo import get_db
from core.library_services import (
    PDFProcessor,
    EmbeddingProcessor,
    AIService,
    SemanticSearchService,
)
from library.models import DocumentService

logger = logging.getLogger(__name__)


class PersonalizedStudyPathAI:
    """Service that generates and maintains personalized study paths for users.

    Data persistence (MongoDB): collection `study_profiles` documents have shape:
    {
        "user_id": <user_id>,
        "topics": [
            {
                "topic_id": <uuid>,
                "title": str,
                "snippets": [ {"doc_id": str, "paragraph_index": int, "text": str} ],
                "difficulty": "easy"|"medium"|"hard",
                "embedding": [...],  # optional centroid
            }
        ],
        "progress": { topic_id: {"status":"not_started|in_progress|mastered","mastery_score":0-100,"last_practiced": datetime, "quizzes": [] } },
        "study_path": [ topic_id, ... ],
        "updated_at": datetime
    }

    """

    COLLECTION = "study_profiles"

    def __init__(self):
        self.db = get_db()

    # ------------------------- Document analysis -------------------------
    def analyze_user_documents(self, user_id: str) -> List[Dict[str, Any]]:
        """Analyze all processed documents for a user and extract topics.

        Returns a list of topic dicts with title, snippets and difficulty.
        """
        try:
            documents, _ = DocumentService.get_user_documents(user_id, page=1, page_size=1000)
            topics: List[Dict[str, Any]] = []

            for doc in documents:
                if not doc.get("is_processed") or not doc.get("content"):
                    continue

                doc_id = str(doc.get("_id"))
                paragraphs = PDFProcessor.split_text_into_paragraphs(doc.get("content", ""), min_length=60, max_length=1200)
                if not paragraphs:
                    continue

                # Generate embeddings (fallback safe)
                embeddings = EmbeddingProcessor.generate_embeddings(paragraphs)

                # For each paragraph, estimate difficulty via AIService.analyze_document_structure heuristics
                for idx, para in enumerate(paragraphs):
                    try:
                        analysis = AIService.analyze_document_structure(para)
                        complexity = analysis.get("complexity_score", 50)
                        if complexity < 20:
                            difficulty = "easy"
                        elif complexity < 50:
                            difficulty = "medium"
                        else:
                            difficulty = "hard"
                    except Exception:
                        difficulty = "medium"

                    topics.append({
                        "topic_id": str(uuid.uuid4()),
                        "title": (para[:80] + "...") if len(para) > 80 else para,
                        "snippets": [{"doc_id": doc_id, "paragraph_index": idx, "text": para}],
                        "difficulty": difficulty,
                        "embedding": embeddings[idx] if idx < len(embeddings) else None,
                    })

            # Optional: merge similar topics by semantic similarity of embeddings
            merged = self._merge_similar_topics(topics)

            # Persist initial profile if not exists
            profile = self.db[self.COLLECTION].find_one({"user_id": user_id})
            if not profile:
                study_path = [t["topic_id"] for t in merged]
                progress = {t["topic_id"]: {"status": "not_started", "mastery_score": 0, "last_practiced": None, "quizzes": []} for t in merged}
                doc = {
                    "user_id": user_id,
                    "topics": merged,
                    "progress": progress,
                    "study_path": study_path,
                    "updated_at": datetime.utcnow()
                }
                self.db[self.COLLECTION].insert_one(doc)
            else:
                # update topics but preserve progress where possible
                existing_progress = profile.get("progress", {})
                study_path = [t["topic_id"] for t in merged]
                progress = {}
                for t in merged:
                    pid = t["topic_id"]
                    progress[pid] = existing_progress.get(pid, {"status": "not_started", "mastery_score": 0, "last_practiced": None, "quizzes": []})

                self.db[self.COLLECTION].update_one({"user_id": user_id}, {"$set": {"topics": merged, "progress": progress, "study_path": study_path, "updated_at": datetime.utcnow()}})

            return merged

        except Exception as e:
            logger.exception("Error analyzing user documents for %s: %s", user_id, e)
            return []

    def _merge_similar_topics(self, topics: List[Dict[str, Any]], threshold: float = 0.85) -> List[Dict[str, Any]]:
        """Merge topics with similar embeddings into combined topics.

        Simple greedy merge using cosine similarity when embeddings available.
        """
        if not topics:
            return []

        try:
            from math import sqrt

            merged: List[Dict[str, Any]] = []

            def cos(a, b):
                try:
                    num = sum(x * y for x, y in zip(a, b))
                    sa = sum(x * x for x in a) ** 0.5
                    sb = sum(y * y for y in b) ** 0.5
                    if sa == 0 or sb == 0:
                        return 0.0
                    return num / (sa * sb)
                except Exception:
                    return 0.0

            for t in topics:
                if not t.get("embedding"):
                    merged.append(t)
                    continue

                placed = False
                for m in merged:
                    if not m.get("embedding"):
                        continue
                    similarity = cos(t["embedding"], m["embedding"])
                    if similarity >= threshold:
                        # merge snippets and average embedding
                        m.setdefault("snippets", []).extend(t.get("snippets", []))
                        # average embedding
                        try:
                            m_emb = m.get("embedding")
                            t_emb = t.get("embedding")
                            m["embedding"] = [(x + y) / 2 for x, y in zip(m_emb, t_emb)]
                        except Exception:
                            pass
                        placed = True
                        break

                if not placed:
                    merged.append(t)

            return merged
        except Exception as e:
            logger.warning("Topic merge failed: %s", e)
            return topics

    # ------------------------- Progress tracking -------------------------
    def fetch_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return the stored study profile for a user, if any."""
        try:
            return self.db[self.COLLECTION].find_one({"user_id": user_id})
        except Exception as e:
            logger.exception("fetch_profile error: %s", e)
            return None

    def update_progress(self, user_id: str, topic_id: str, mastery_score: Optional[float] = None, status: Optional[str] = None, quiz_result: Optional[Dict[str, Any]] = None) -> bool:
        """Update progress for a given topic.

        quiz_result (optional) is appended to the topic's quizzes list.
        """
        try:
            profile = self.fetch_profile(user_id)
            if not profile:
                logger.warning("No profile found for user %s", user_id)
                return False

            progress = profile.get("progress", {})
            if topic_id not in progress:
                # create entry
                progress[topic_id] = {"status": "not_started", "mastery_score": 0, "last_practiced": None, "quizzes": []}

            entry = progress[topic_id]
            if mastery_score is not None:
                entry["mastery_score"] = float(mastery_score)
                # auto-update status
                entry["status"] = "mastered" if entry["mastery_score"] >= 80 else ("in_progress" if entry["mastery_score"] > 0 else entry.get("status", "not_started"))

            if status:
                entry["status"] = status

            if quiz_result:
                entry.setdefault("quizzes", []).append({"result": quiz_result, "timestamp": datetime.utcnow()})
                entry["last_practiced"] = datetime.utcnow()

            # persist
            self.db[self.COLLECTION].update_one({"user_id": user_id}, {"$set": {"progress": progress, "updated_at": datetime.utcnow()}})
            return True
        except Exception as e:
            logger.exception("update_progress error: %s", e)
            return False

    # ------------------------- Study path generation -------------------------
    def generate_personalized_path(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Generate a personalized sequence of topics to study.

        Strategy:
        - Prioritize topics with status not_started and lower mastery_score.
        - Insert review/practice steps for topics with low mastery.
        - Limit to `limit` topics.
        """
        try:
            profile = self.fetch_profile(user_id)
            if not profile:
                # attempt to analyze documents and create a profile
                self.analyze_user_documents(user_id)
                profile = self.fetch_profile(user_id)
                if not profile:
                    return []

            topics = profile.get("topics", [])
            progress = profile.get("progress", {})

            # Score topics: lower mastery => higher priority; not_started high priority
            scored = []
            for t in topics:
                tid = t["topic_id"]
                p = progress.get(tid, {"status": "not_started", "mastery_score": 0})
                mastery = p.get("mastery_score", 0)
                status = p.get("status", "not_started")
                base = 100 - mastery
                if status == "not_started":
                    base += 20
                if status == "in_progress" and mastery < 50:
                    base += 10
                scored.append((base, t))

            scored.sort(key=lambda x: x[0], reverse=True)

            path: List[Dict[str, Any]] = []
            for score, t in scored[:limit]:
                tid = t["topic_id"]
                p = progress.get(tid, {"status": "not_started", "mastery_score": 0})

                # recommend exercises: small quiz generated from snippets
                exercises = []
                try:
                    # Use AIService to generate short quiz for topic snippets (1-3 questions)
                    combined_text = "\n\n".join([s["text"] for s in t.get("snippets", [])[:3]])
                    qa = AIService.generate_qa_pairs(combined_text, num_questions=3)
                    exercises = qa
                except Exception as e:
                    logger.debug("generate exercises failed for topic %s: %s", tid, e)

                path.append({
                    "topic_id": tid,
                    "title": t.get("title"),
                    "difficulty": t.get("difficulty"),
                    "progress": p,
                    "exercises": exercises,
                    "snippets": t.get("snippets", [])
                })

            # persist as current study_path
            study_path_ids = [p["topic_id"] for p in path]
            self.db[self.COLLECTION].update_one({"user_id": user_id}, {"$set": {"study_path": study_path_ids, "updated_at": datetime.utcnow()}})
            return path
        except Exception as e:
            logger.exception("generate_personalized_path error: %s", e)
            return []

    def fetch_study_path(self, user_id: str) -> Dict[str, Any]:
        """Return the user's current study path (detailed entries)."""
        try:
            profile = self.fetch_profile(user_id)
            if not profile:
                return {"study_path": [], "topics": [], "progress": {}}
            study_path_ids = profile.get("study_path", [])
            topics_map = {t["topic_id"]: t for t in profile.get("topics", [])}
            detailed = [ {**topics_map[tid], "progress": profile.get("progress", {}).get(tid, {})} for tid in study_path_ids if tid in topics_map ]
            return {"study_path": study_path_ids, "topics": detailed, "progress": profile.get("progress", {})}
        except Exception as e:
            logger.exception("fetch_study_path error: %s", e)
            return {"study_path": [], "topics": [], "progress": {}}

    # ------------------------- Career recommendation -------------------------
    def recommend_careers(self, user_id: str, k: int = 3) -> List[Dict[str, Any]]:
        """Suggest likely career paths from extracted topics/keywords.

        Heuristic mapping: uses top keywords across topics to infer domains
        (e.g., data, web, mobile, security, cloud, embedded, ai/ml, devops).
        """
        try:
            profile = self.fetch_profile(user_id)
            if not profile:
                return []

            # Aggregate keywords from topics titles/snippets
            keywords: Dict[str, int] = {}
            for t in profile.get("topics", []):
                title = (t.get("title") or "").lower()
                for w in re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ]{4,}", title):
                    keywords[w] = keywords.get(w, 0) + 1
                for s in t.get("snippets", [])[:2]:
                    txt = (s.get("text") or "").lower()
                    for w in re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ]{4,}", txt):
                        keywords[w] = keywords.get(w, 0) + 1

            # Simple domain keyword sets
            domains = {
                "Data Science": {"data", "pandas", "numpy", "statistics", "regression", "analysis", "sql"},
                "AI/ML Engineer": {"machine", "learning", "model", "neural", "classification", "nlp", "vision"},
                "Web Developer": {"javascript", "react", "django", "flask", "frontend", "backend", "api"},
                "Mobile Developer": {"android", "ios", "flutter", "reactnative", "kotlin", "swift"},
                "Cybersecurity": {"security", "cipher", "encryption", "vulnerability", "attack", "threat"},
                "Cloud/DevOps": {"docker", "kubernetes", "aws", "azure", "gcp", "pipeline", "ci"},
                "Embedded/IoT": {"embedded", "microcontroller", "arduino", "sensor", "rtos"},
                "Data Engineer": {"spark", "hadoop", "etl", "warehouse", "airflow"},
            }

            def score_domain(words: Dict[str, int], vocab: set) -> int:
                return sum(count for w, count in words.items() if any(w.startswith(v) for v in vocab))

            scored = []
            for name, vocab in domains.items():
                scored.append((score_domain(keywords, vocab), name))
            scored.sort(reverse=True)

            suggestions = []
            for score, name in scored[:k]:
                if score <= 0:
                    continue
                suggestions.append({"career": name, "score": score})
            return suggestions
        except Exception:
            return []

    # ------------------------- Chat integration -------------------------
    def answer_with_path_context(self, user_id: str, question: str) -> Dict[str, Any]:
        """Answer a student's question using context from their current study path.

        Returns a dict with keys: response (str), sources (list)
        """
        try:
            profile = self.fetch_profile(user_id)
            if not profile:
                return {"response": "I don't have a study profile for you yet. Upload documents or create a study path.", "sources": []}

            # gather top 3 relevant paragraphs from study_path topics
            snippets = []
            for tid in profile.get("study_path", [])[:5]:
                topic = next((t for t in profile.get("topics", []) if t["topic_id"] == tid), None)
                if not topic:
                    continue
                for s in topic.get("snippets", [])[:2]:
                    snippets.append({"document_title": s.get("doc_id"), "paragraph": s.get("text")})

            # call AIService.generate_response which expects relevant_paragraphs
            resp = AIService.generate_response(question, snippets, conversation_history=None)
            sources = [s.get("document_title") for s in snippets[:3]]
            return {"response": resp, "sources": sources}
        except Exception as e:
            logger.exception("answer_with_path_context error: %s", e)
            return {"response": "An error occurred while answering. Please try again.", "sources": []}


__all__ = ["PersonalizedStudyPathAI"]
