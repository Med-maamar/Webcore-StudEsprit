# StudEsprit (Accounts + Dashboard)

This is a Django 5 project configured for MongoDB (PyMongo) with a custom Accounts system (Users/Auth/Roles) and a custom Admin-like Dashboard. No Django ORM users; no Django Admin.

- Python 3.11
- Django 5.x
- MongoDB via PyMongo
- Sessions via signed cookies
- Argon2 password hashing
- Templates with Tailwind CSS (CLI), Flowbite, and HTMX
- Vector Search stubs against MongoDB Atlas or Python fallback

## Quickstart (macOS, Python 3.11)

```
# 1) Python venv
python3.11 -m venv .venv
source .venv/bin/activate

# 2) Install Python deps
pip install -r requirements.txt

# 3) Environment
cp .env.example .env
# edit .env as needed (MONGODB_URI, MONGODB_DB_NAME, SECRET_KEY, DEBUG, OPENAI_API_KEY)

# 4) Node + Tailwind
npm init -y
npm install -D tailwindcss postcss autoprefixer flowbite
npx tailwindcss -i ./assets/styles/input.css -o ./static/build/tailwind.css --minify
# or run in watch mode (new terminal)
npm run tailwind:watch

# 5) Run server
python manage.py runserver 127.0.0.1:8000
```

No Django migrations are required (no ORM models). Users are stored in MongoDB.

## Quickstart (Windows, Python 3.11)

```
# 1) Open PowerShell in the studEsprit folder

# 2) Create and activate a virtual environment
py -3.11 -m venv .venv
.venv\Scripts\Activate

# 3) Install Python dependencies
pip install -r requirements.txt

# 4) Environment
copy .env.example .env
# Edit .env as needed (MONGODB_URI, MONGODB_DB_NAME, SECRET_KEY, DEBUG, OPENAI_API_KEY)

# 5) Node + Tailwind (requires Node.js installed)
npm install
npm run tailwind:build
# or watch during development
npm run tailwind:watch

# 6) Run the server
python manage.py runserver 127.0.0.1:8000
```

Windows notes:
- If `py` is not found, use `python` instead: `python -m venv .venv` then `.venv\Scripts\Activate`.
- If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- Verify Tailwind build exists: `static\build\tailwind.css` after `npm run tailwind:build`.
- App URL: http://127.0.0.1:8000/

## Environment

- `MONGODB_URI` e.g., `mongodb://localhost:27017/studhub`
- `MONGODB_DB_NAME` e.g., `studhub`
- `MONGO_URI` / `MONGO_DB_NAME` are still read if present (for legacy modules)
- `SECRET_KEY` set a strong value for production
- `DEBUG` true/false
- `ALLOWED_HOSTS` comma-separated
- Google OAuth2 (optional, for Google Login)
- `OPENAI_API_KEY` (optional, enables LLM mode for the careers AI helpers)
 
## Mongo + Vector Search

- Vector collection: `profiles_embeddings` with field `embedding` (float vector length 384)
- Index helper: `ai/embeddings.ensure_vector_index()` (creates standard indexes)
- Atlas Search: Create a vector index named `vector_index` on `embedding` via Atlas UI/API (if using Atlas)
- Query: `ai/embeddings.vector_search(text, k)` tries `$vectorSearch` then falls back to cosine in Python
- Embeddings: `ai/embeddings.compute_embedding(text)` returns a deterministic pseudo-vector




## Routes

- Auth: `/auth/register`, `/auth/register/submit`, `/auth/login`, `/auth/login/submit`, `/auth/logout`
- Google OAuth: `/auth/google/login` → redirect to Google, `/auth/google/callback` → exchange code
- Account: `/account/profile`, `/account/profile/update`, `/account/change-password`
- Dashboard: `/dashboard/`
- Users table: `/dashboard/users` (with HTMX partial at `/dashboard/users/partial`)
- Inline role update (Admin only): POST `/dashboard/users/update-role`
- Stubs: `/courses/`, `/services/`, `/events/`, `/shop/`
- Careers API: `/api/opportunities/`, `/api/applications/`, `/api/profile/`, `/api/ai/*`
- Careers pages: `/careers/opportunities/`, `/careers/opportunities/<id>/`, `/careers/profile/`

## Careers Module

- MongoEngine documents for opportunities, applications, and CV profiles (no SQL tables)
- REST API via Django REST Framework + `rest_framework_mongoengine`
- Permissions: students manage their own applications/profile; staff manage all opportunities
- AI helpers (rules-based by default, optional OpenAI LLM when `OPENAI_API_KEY` is set)
- HTMX-powered pages for browsing/applying to opportunities and editing the CV profile
- Seed demo data: `python manage.py seed_careers`

Sample calls (with an authenticated session or token):

```
curl -X GET http://127.0.0.1:8000/api/opportunities/ -b sessionid=...

curl -X POST http://127.0.0.1:8000/api/ai/cv-gap-analysis/ \
  -H "Content-Type: application/json" \
  -d '{"jobDesc": "We need Python/Django + MongoDB"}' \
  -b sessionid=...
```

## Notes

- Session engine: signed cookies (no server-side table)
- Middleware injects `request.user` via Mongo session user_id
- Security: CSRF enabled, secure cookies in production; TODO: add CSP and HSTS
- UI: Tailwind + Flowbite + HTMX, green/white theme, dark mode toggle
