from __future__ import annotations

import time
from collections import defaultdict, deque
from functools import wraps
from typing import Callable, Iterable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages


def login_required_mongo(view_func: Callable):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            messages.error(request, "Please log in to continue.")
            return redirect("/auth/login")
        return view_func(request, *args, **kwargs)

    return _wrapped


def role_required(roles: Iterable[str]):
    roles = set(roles)

    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return redirect("/auth/login")
            if user.role not in roles:
                return HttpResponseForbidden("Insufficient permissions")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# Simple in-memory rate limit (per key)
_rate_state = defaultdict(deque)


def rate_limit(key_func: Callable[[HttpRequest], str], limit: int = 5, window_seconds: int = 300):
    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            now = time.time()
            key = key_func(request)
            dq = _rate_state[key]
            while dq and now - dq[0] > window_seconds:
                dq.popleft()
            if len(dq) >= limit:
                return HttpResponse("Too many requests, slow down.", status=429)
            dq.append(now)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def rate_by_ip(request: HttpRequest) -> str:
    ip = request.META.get("REMOTE_ADDR", "unknown")
    path = request.path
    return f"ip:{ip}:{path}"


def rate_by_email_or_ip(request: HttpRequest) -> str:
    # Useful for login/register forms
    email = request.POST.get("email") or request.GET.get("email") or ""
    ip = request.META.get("REMOTE_ADDR", "unknown")
    path = request.path
    return f"email:{email.lower()}|ip:{ip}:{path}"

