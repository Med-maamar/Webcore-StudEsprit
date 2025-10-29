ML microservice to generate simple test questions from PDFs.

- Start: python ml_service/app.py
- POST /api/generate-from-pdf with form-data file field 'file'

Notes: uses PyPDF2 and nltk. Tests included in `ml_service/tests`.
