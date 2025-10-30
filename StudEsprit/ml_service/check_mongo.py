from __future__ import annotations
import os, json
from core.mongo import get_db

def main():
    db = get_db()
    collections = ['study_profiles','documents','chat_sessions','community_posts']
    out = {}
    for c in collections:
        try:
            out[c] = db[c].count_documents({})
        except Exception as e:
            out[c] = str(e)
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()
