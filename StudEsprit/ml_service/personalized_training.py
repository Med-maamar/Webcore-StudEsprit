"""Dataset builder and simple training pipeline for Personalized Study Path.

This module builds a training dataset from the MongoDB `study_profiles` and
`documents` collections and trains a basic scikit-learn model to predict topic
mastery buckets or recommend topics. It's intentionally simple and defensive —
it will raise a clear error when required dependencies are missing.

Functions:
 - build_dataset(db=None, save_csv_path=None) -> pandas.DataFrame
 - train_model(df=None, save_model_path=None) -> dict(metrics)
 - load_model(path) -> model
 - recommend_for_user(user_id, model_path, db=None, top_k=5) -> list

Note: This is a starting point. For production use, move training to a job
queue (Celery), add proper preprocessing, hyperparameter tuning, CV, and
monitoring.
"""
from __future__ import annotations

import os
import pickle
import logging
from typing import Optional, Tuple, List, Dict

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import numpy as np
except Exception as e:
    raise RuntimeError("pandas and numpy are required for personalized_training. Install them: pip install pandas numpy")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
except Exception:
    raise RuntimeError("scikit-learn is required for personalized_training. Install it: pip install scikit-learn")

from core.mongo import get_db


def _safe_get(d, key, default=0):
    v = d.get(key, default)
    try:
        return float(v)
    except Exception:
        return default


def build_dataset(db=None, save_csv_path: Optional[str] = None) -> pd.DataFrame:
    """Build a dataset DataFrame from `study_profiles` and `documents`.

    Returns a DataFrame with one row per (user, topic) and features such as:
      - user_id
      - topic_id
      - topic_title
      - topic_embedding_0..N (if available; truncated/averaged otherwise)
      - doc_count (number of documents contributing)
      - user_mastery (0..1)
      - avg_quiz_score (0..1)
      - target_mastery_bucket (0=low,1=medium,2=high)

    The function is defensive: if embeddings are missing it uses zeros. Save
    CSV if save_csv_path is provided.
    """
    db = db or get_db()
    profiles = list(db.study_profiles.find({}))

    rows = []
    for p in profiles:
        user_id = str(p.get('user_id'))
        topics = p.get('topics', []) or []
        for t in topics:
            topic_id = str(t.get('id') or t.get('topic_id') or t.get('_id', ''))
            title = t.get('title') or t.get('name') or 'topic'
            embedding = t.get('embedding') or t.get('vector') or []
            # Flatten embedding to some fixed size (truncate or pad)
            max_emb = 32
            emb = list(embedding[:max_emb]) + [0.0] * max(0, max_emb - len(embedding))

            doc_count = len(t.get('sources', []) or [])
            user_mastery = _safe_get(t, 'mastery', 0.0)
            avg_quiz = _safe_get(t, 'avg_quiz_score', t.get('quiz_score', 0.0))

            # Target: bucketize mastery
            if user_mastery >= 0.8:
                target = 2
            elif user_mastery >= 0.4:
                target = 1
            else:
                target = 0

            row = {
                'user_id': user_id,
                'topic_id': topic_id,
                'topic_title': title,
                'doc_count': doc_count,
                'user_mastery': user_mastery,
                'avg_quiz_score': avg_quiz,
                'target_mastery_bucket': target,
            }
            # add embedding cols
            for i, val in enumerate(emb):
                row[f'emb_{i}'] = float(val or 0.0)

            rows.append(row)

    if not rows:
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(rows)

    if save_csv_path and not df.empty:
        os.makedirs(os.path.dirname(save_csv_path), exist_ok=True)
        df.to_csv(save_csv_path, index=False)
        logger.info(f"Saved training dataset to {save_csv_path}")

    return df


def train_model(df: Optional[pd.DataFrame] = None, save_model_path: Optional[str] = None) -> Dict[str, float]:
    """Train a RandomForest model on the dataset and optionally save the model.

    Returns dict with metrics (accuracy on holdout).
    """
    if df is None:
        df = build_dataset()

    if df.empty:
        raise RuntimeError('No training data available')

    # Features: all emb_* plus doc_count, avg_quiz_score
    feature_cols = [c for c in df.columns if c.startswith('emb_')] + ['doc_count', 'avg_quiz_score']
    X = df[feature_cols].fillna(0.0).astype(float).values
    y = df['target_mastery_bucket'].astype(int).values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = float(accuracy_score(y_test, preds))

    if save_model_path:
        os.makedirs(os.path.dirname(save_model_path), exist_ok=True)
        with open(save_model_path, 'wb') as fh:
            pickle.dump({'model': model, 'feature_cols': feature_cols}, fh)
        logger.info(f"Model saved to {save_model_path}")

    return {'accuracy': acc, 'n_samples': len(df)}


def load_model(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, 'rb') as fh:
        meta = pickle.load(fh)
    return meta


def recommend_for_user(user_id: str, model_path: str, db=None, top_k: int = 5) -> List[Dict]:
    """Given a user_id and a trained model, return top_k recommended topics.

    Strategy:
     - Load the user's study_profile topics
     - Compute features for each topic matching the model's feature_cols
     - Use model.predict_proba to score classes; recommend topics with lowest
       predicted mastery bucket (i.e., topics likely to need attention)
    """
    db = db or get_db()
    profile = db.study_profiles.find_one({'user_id': user_id})
    if not profile:
        return []

    meta = load_model(model_path)
    model = meta['model']
    feature_cols = meta['feature_cols']

    topics = profile.get('topics', []) or []
    rows = []
    for t in topics:
        embedding = t.get('embedding') or []
        max_emb = 32
        emb = list(embedding[:max_emb]) + [0.0] * max(0, max_emb - len(embedding))
        row = {}
        for i in range(max_emb):
            row[f'emb_{i}'] = float(emb[i])
        row['doc_count'] = float(len(t.get('sources', []) or []))
        row['avg_quiz_score'] = float(t.get('avg_quiz_score', t.get('quiz_score', 0.0)))
        row['topic_id'] = str(t.get('id') or t.get('topic_id') or '')
        row['title'] = t.get('title') or t.get('name') or ''
        rows.append(row)

    if not rows:
        return []

    import numpy as np
    X = []
    for r in rows:
        X.append([r.get(c, 0.0) for c in feature_cols])
    X = np.array(X)

    probs = model.predict_proba(X)
    # probs shape: (n_samples, n_classes) – classes ordered by label (0,1,2)
    # We want to recommend topics with highest probability of low mastery (class 0)
    low_mastery_prob = probs[:, 0]

    scored = []
    for r, p in zip(rows, low_mastery_prob):
        scored.append({'topic_id': r['topic_id'], 'title': r['title'], 'score': float(p)})

    scored_sorted = sorted(scored, key=lambda x: x['score'], reverse=True)
    return scored_sorted[:top_k]
