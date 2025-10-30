# ml_service/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import random
import os
import tempfile
import traceback

# Import your PDF generator
try:
    from .generator import generate_questions_from_text
except Exception:
    from generator import generate_questions_from_text

app = Flask(__name__)

# Allow your frontend
CORS(
    app,
    supports_credentials=True,
    resources={r"/*": {"origins": ["https://webcore-studesprit.onrender.com"]}}
)

# === MATIERES: CSV DATA ===
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, 'Data', 'mateire.csv')

def load_dataset(path=DATA_PATH):
    rows = []
    if not os.path.exists(path):
        print(f"Warning: mateire.csv not found at {path}")
        return rows
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                'nom': r.get('nom', '').strip(),
                'description': r.get('description', '').strip(),
                'coefficient': float(r.get('coefficient') or 0),
                'niveau_education': r.get('niveau_education', '').strip(),
            })
    return rows

# === ENDPOINT 1: Generate Matieres ===
@app.route('/generate_matieres', methods=['POST'])
def generate_matieres():
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

    if len(filtered) >= count:
        sample = random.sample(filtered, count)
    else:
        sample = filtered[:]
        remaining = [r for r in data if r not in filtered]
        need = max(0, count - len(sample))
        if need > 0 and remaining:
            sample += random.sample(remaining, min(need, len(remaining)))

    for s in sample:
        if niveau:
            s['suggested_for_niveau'] = niveau

    return jsonify({'count': len(sample), 'matieres': sample})

# === ENDPOINT 2: Generate from PDF ===
@app.route('/api/generate-from-pdf', methods=['POST'])
def generate_from_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'File must be PDF'}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            questions = generate_questions_from_text(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        return jsonify({'questions': questions})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

# === Health Check ===
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "OK", "service": "StudEsprit AI"})

# NO app.run() in production
