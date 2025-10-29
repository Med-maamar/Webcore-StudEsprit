from flask import Flask, request, jsonify
from flask_cors import CORS

# Support running as a package (python -m ml_service.app) and as a script
try:
    # preferred when running as a package
    from .generator import generate_questions_from_text
except Exception:
    # fallback when running python app.py directly from the ml_service folder
    from generator import generate_questions_from_text
import tempfile
import os
import traceback

app = Flask(__name__)
CORS(app)


@app.route('/api/generate-from-pdf', methods=['POST'])
def generate_from_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        f = request.files['file']
        # save to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            f.save(tmp.name)
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
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
