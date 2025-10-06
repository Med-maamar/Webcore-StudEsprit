from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
from typing import Dict, Any

from bson import ObjectId
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages

from core.decorators import login_required_mongo, role_required
from core.mongo import get_db, health_check
from accounts.services import query_users
from ai.embeddings import vector_search


@login_required_mongo
def index(request: HttpRequest):
    # Student dashboard: show an empty/placeholder page
    if getattr(request.user, "role", "Student") != "Admin":
        return render(request, "dashboard/index.html", {"student_empty": True})

    # Admin dashboard KPIs
    db = get_db()
    now = datetime.utcnow()
    last7 = now - timedelta(days=7)
    last24 = now - timedelta(hours=24)

    total_users = db.users.estimated_document_count()
    new_last_7 = db.users.count_documents({"created_at": {"$gte": last7}})
    logins_24h = db.audit_auth.count_documents({"created_at": {"$gte": last24}})

    role_counts = {r: db.users.count_documents({"role": r}) for r in ["Student", "Admin"]}

    # Personalization demo: run a query for the current user
    try:
        q = f"profile of {request.user.username}"
        recs = vector_search(q, k=5)
    except Exception:
        recs = []

    system = {
        "mongo_ok": health_check(),
        "tailwind_built": (request.build_absolute_uri("/static/build/tailwind.css")),
    }

    ctx: Dict[str, Any] = {
        "total_users": total_users,
        "new_last_7": new_last_7,
        "logins_24h": logins_24h,
        "role_counts": role_counts,
        "recs": recs,
        "system": system,
    }
    return render(request, "dashboard/index.html", ctx)


@login_required_mongo
@role_required(["Admin"])  # Only admins can view users page
def users_page(request: HttpRequest):
    # Render page that hosts the users table and filters
    q = request.GET.get("q")
    role = request.GET.get("role")
    page = int(request.GET.get("page", 1) or 1)
    page_size = int(request.GET.get("page_size", 10) or 10)
    rows, total = query_users(q=q, role=role, page=page, page_size=page_size)
    for r in rows:
        try:
            r["id"] = str(r.get("_id"))
        except Exception:
            r["id"] = ""
    pages = ceil(total / page_size) if page_size else 1
    ctx = {"rows": rows, "total": total, "page": page, "pages": pages, "q": q or "", "role": role or "", "page_size": page_size}
    return render(request, "dashboard/users.html", ctx)


@login_required_mongo
@role_required(["Admin"])  # Only admins can fetch the users table
def users_partial(request: HttpRequest):
    # HTMX partial for table only
    q = request.GET.get("q")
    role = request.GET.get("role")
    page = int(request.GET.get("page", 1) or 1)
    page_size = int(request.GET.get("page_size", 10) or 10)
    rows, total = query_users(q=q, role=role, page=page, page_size=page_size)
    for r in rows:
        try:
            r["id"] = str(r.get("_id"))
        except Exception:
            r["id"] = ""
    pages = ceil(total / page_size) if page_size else 1
    ctx = {"rows": rows, "total": total, "page": page, "pages": pages, "q": q or "", "role": role or "", "page_size": page_size}
    return render(request, "dashboard/partials/users_table.html", ctx)


@csrf_protect
@login_required_mongo
@role_required(["Admin"])  # Admin only
def users_update_role(request: HttpRequest):
    user_id = request.POST.get("user_id")
    new_role = request.POST.get("role")
    if new_role not in {"Student", "Admin"}:
        return JsonResponse({"ok": False, "error": "Invalid role"}, status=400)
    try:
        get_db().users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": new_role}})
        # Return updated row partial
        row = get_db().users.find_one({"_id": ObjectId(user_id)})
        return render(request, "dashboard/partials/user_row.html", {"row": row})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
