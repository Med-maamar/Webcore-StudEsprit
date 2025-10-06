from __future__ import annotations

from datetime import datetime, timedelta

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages

from core.decorators import rate_limit, rate_by_email_or_ip, login_required_mongo
from accounts.validators import validate_email, validate_password, validate_username
from accounts.services import (
    create_user,
    find_user_by_email,
    find_user_by_id,
    change_password as svc_change_password,
    update_user_profile,
    record_login_audit,
    get_or_create_user_from_google,
)
from argon2 import PasswordHasher
from django.conf import settings
import secrets
import urllib.parse
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from slugify import slugify
from pathlib import Path

ph = PasswordHasher()


def _set_session_user(request: HttpRequest, user_id: str):
    request.session["user_id"] = user_id
    request.session.modified = True


@csrf_protect
def register_get(request: HttpRequest):
    return render(request, "auth/register.html")


@csrf_protect
@rate_limit(rate_by_email_or_ip, limit=5, window_seconds=300)
def register_post(request: HttpRequest):
    email = request.POST.get("email", "")
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    confirm = request.POST.get("confirm_password", "")
    try:
        email = validate_email(email)
        username = validate_username(username)
        validate_password(password)
        if password != confirm:
            raise ValueError("Passwords do not match")
        if find_user_by_email(email):
            raise ValueError("Email already registered")
        user = create_user(email, username, password, role="Student")
        _set_session_user(request, str(user["_id"]))
        messages.success(request, "Welcome to StudEsprit!")
        record_login_audit(
            str(user["_id"]), request.META.get("REMOTE_ADDR", ""), request.META.get("HTTP_USER_AGENT", "")
        )
        return redirect("/dashboard/")
    except Exception as e:
        messages.error(request, str(e))
        return render(request, "auth/register.html", {"email": email, "username": username})


@csrf_protect
def login_get(request: HttpRequest):
    return render(request, "auth/login.html")


@csrf_protect
@rate_limit(rate_by_email_or_ip, limit=8, window_seconds=300)
def login_post(request: HttpRequest):
    email = request.POST.get("email", "").strip().lower()
    password = request.POST.get("password", "")
    try:
        user = find_user_by_email(email)
        if not user:
            raise ValueError("Invalid credentials")
        ph.verify(user.get("password_hash", ""), password)
        # Success
        _set_session_user(request, str(user["_id"]))
        from core.mongo import get_db

        get_db().users.update_one(
            {"_id": user["_id"]}, {"$set": {"last_login_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        record_login_audit(
            str(user["_id"]), request.META.get("REMOTE_ADDR", ""), request.META.get("HTTP_USER_AGENT", "")
        )
        messages.success(request, "Logged in successfully")
        return redirect("/dashboard/")
    except Exception:
        messages.error(request, "Invalid email or password")
        return render(request, "auth/login.html", {"email": email})


@csrf_protect
def logout_post(request: HttpRequest):
    request.session.pop("user_id", None)
    messages.success(request, "Logged out")
    return redirect("/auth/login")


@csrf_protect
@login_required_mongo
def profile_get(request: HttpRequest):
    user = find_user_by_id(request.user.id)
    return render(request, "account/profile.html", {"user": user})


@csrf_protect
@login_required_mongo
def profile_post(request: HttpRequest):
    username = request.POST.get("username")
    avatar_url = request.POST.get("avatar_url")
    try:
        if username:
            username = validate_username(username)
        update_user_profile(request.user.id, username, avatar_url)
        messages.success(request, "Profile updated")
    except Exception as e:
        messages.error(request, str(e))
    return redirect("/account/profile")


@csrf_protect
@login_required_mongo
def change_password_post(request: HttpRequest):
    new = request.POST.get("new_password", "")
    confirm = request.POST.get("confirm_password", "")
    try:
        user = find_user_by_id(request.user.id)
        if not user:
            messages.error(request, "User not found")
            return redirect("/account/profile")
        if new != confirm:
            raise ValueError("New passwords do not match")
        validate_password(new)
        svc_change_password(request.user.id, new)
        messages.success(request, "Password changed")
    except Exception as e:
        messages.error(request, str(e))
    return redirect("/account/profile")


# ===== Google OAuth2 =====

def _google_redirect_uri(request: HttpRequest) -> str:
    # Prefer explicit env; fallback to build_absolute_uri
    return settings.GOOGLE_REDIRECT_URI or request.build_absolute_uri("/auth/google/callback")


def google_login_start(request: HttpRequest):
    if not settings.GOOGLE_CLIENT_ID:
        messages.error(request, "Google login is not configured.")
        return redirect("/auth/login")
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return redirect(url)


def google_callback(request: HttpRequest):
    err = request.GET.get("error")
    if err:
        messages.error(request, f"Google auth error: {err}")
        return redirect("/auth/login")
    state = request.GET.get("state")
    code = request.GET.get("code")
    if not code or not state or state != request.session.get("oauth_state"):
        messages.error(request, "Invalid OAuth state.")
        return redirect("/auth/login")

    # Exchange code
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": _google_redirect_uri(request),
        "grant_type": "authorization_code",
    }
    token_resp = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
    if token_resp.status_code != 200:
        messages.error(request, "Failed to exchange code.")
        return redirect("/auth/login")
    tok = token_resp.json()
    idtok = tok.get("id_token")
    if not idtok:
        messages.error(request, "No ID token from Google.")
        return redirect("/auth/login")

    try:
        claims = id_token.verify_oauth2_token(idtok, grequests.Request(), settings.GOOGLE_CLIENT_ID)
        # Extract profile
        email = claims.get("email")
        sub = claims.get("sub")
        name = claims.get("name")
        picture = claims.get("picture")
    except Exception:
        messages.error(request, "Invalid Google token.")
        return redirect("/auth/login")

    if not email or not sub:
        messages.error(request, "Google account missing email.")
        return redirect("/auth/login")

    user = get_or_create_user_from_google(email=email, full_name=name, avatar_url=picture, google_sub=sub)
    _set_session_user(request, str(user["_id"]))
    record_login_audit(str(user["_id"]), request.META.get("REMOTE_ADDR", ""), request.META.get("HTTP_USER_AGENT", ""))
    messages.success(request, "Logged in with Google")
    return redirect("/dashboard/")


@csrf_protect
@login_required_mongo
def profile_upload_avatar_post(request: HttpRequest):
    f = request.FILES.get("avatar_file")
    if not f:
        messages.error(request, "No file uploaded")
        return redirect("/account/profile")
    # Basic validation
    allowed = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    ext = allowed.get(getattr(f, "content_type", ""))
    if not ext:
        messages.error(request, "Unsupported image type")
        return redirect("/account/profile")
    if f.size and f.size > 5 * 1024 * 1024:
        messages.error(request, "Image too large (max 5MB)")
        return redirect("/account/profile")
    # Save to MEDIA/avatars/<user_id>/filename
    filename = slugify(Path(f.name).stem) + ext
    user_dir = Path(settings.MEDIA_ROOT) / "avatars" / request.user.id
    user_dir.mkdir(parents=True, exist_ok=True)
    dst = user_dir / filename
    with dst.open("wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    # Update user avatar_url
    url = f"{settings.MEDIA_URL}avatars/{request.user.id}/{filename}"
    try:
        update_user_profile(request.user.id, None, url)
        messages.success(request, "Avatar updated")
    except Exception as e:
        messages.error(request, str(e))
    return redirect("/account/profile")
