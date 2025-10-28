Niveaux (program app)

This app provides a simple Mongo-backed "Niveau" entity with fields:
- nom (string)
- description (text)

Files:
- services.py: CRUD helpers using `core.mongo.get_db()` and the `niveaux` collection.
- views.py / urls.py / templates: basic list and create views at /program/niveaux/ and /program/niveaux/create/.

Notes:
- The project uses MongoDB via PyMongo (see `main/settings.py` for `MONGO_URI`/`MONGO_DB_NAME`).
- This app does NOT use Django ORM models, so no migrations are required.

To enable routes, ensure `program` is in `INSTALLED_APPS` in `main/settings.py`:

INSTALLED_APPS = [
    # ... other apps ...
    "program",
]

Then run the development server and visit http://localhost:8000/program/niveaux/ to view and create niveaux.
