from __future__ import annotations

from django.conf import settings


def global_context(request):
    theme = request.COOKIES.get("theme", "light")
    return {
        "current_user": getattr(request, "user", None),
        "dark_mode": theme == "dark",
        "app_version": getattr(settings, "APP_VERSION", "0.0.0"),
    }

