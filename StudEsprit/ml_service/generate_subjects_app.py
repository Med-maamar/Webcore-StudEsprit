from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import random
import os

app = Flask(__name__)
# Allow cross-origin requests from the local Django dev server and allow cookies/credentials
# Credentials mode is 'include' on the client, so we must set supports_credentials=True
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["http://127.0.0.1:8000", "http://localhost:8000"]}})

# Path to the sample dataset (relative to this file)
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, 'Data', 'mateire.csv')


def load_dataset(path=DATA_PATH):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            # normalize fields
            rows.append({
                'nom': r.get('nom', '').strip(),
                'description': r.get('description', '').strip(),
                'coefficient': float(r.get('coefficient') or 0),
                'niveau_education': r.get('niveau_education', '').strip(),
            })
    return rows


@app.route('/generate_matieres', methods=['POST'])
def generate_matieres():
    """Generate candidate matieres for a given niveau.

    Expected JSON body:
      {"niveau": "L3", "count": 6, "shuffle_seed": 123}

    Response: JSON list of matieres with fields: nom, description, coefficient, niveau_education
    """
    payload = request.get_json(force=True, silent=True) or {}
    niveau = (payload.get('niveau') or '').strip()
    try:
        count = int(payload.get('count') or 6)
    except Exception:
        count = 6
    seed = payload.get('shuffle_seed')

    data = load_dataset()
    if niveau:
        filtered = [r for r in data if r.get('niveau_education', '').lower() == niveau.lower()]
    else:
        filtered = data

    if seed is not None:
        try:
            random.seed(int(seed))
        except Exception:
            pass

    # if not enough matches, fall back to sampling from full set but keep niveau tag
    if len(filtered) >= count:
        sample = random.sample(filtered, count)
    else:
        sample = filtered[:]  # copy
        remaining = [r for r in data if r not in filtered]
        need = max(0, count - len(sample))
        if need > 0 and remaining:
            sample += random.sample(remaining, min(need, len(remaining)))

    # ensure 'niveau_education' matches requested niveau when possible
    for s in sample:
        if niveau:
            s['suggested_for_niveau'] = niveau

    return jsonify({'count': len(sample), 'matieres': sample})


if __name__ == '__main__':
    # default port 5002 to avoid clashing with other services
    app.run(port=5002, debug=True)
