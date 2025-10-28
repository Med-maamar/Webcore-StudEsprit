from django.urls import include, path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from core.views import coming_soon, home
from django.views.generic import RedirectView
from accounts.urls import account_urlpatterns


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("auth/", include("accounts.urls")),
    path("account/", include((account_urlpatterns, "accounts"), namespace="account")),
    path("dashboard/", include("dashboard.urls")),
    path("library/", include("library.urls")),
    path("", include("careers.urls")),
    # Careers entrypoint under historic Services URL
    path("services/", RedirectView.as_view(pattern_name="careers:opportunity-list", permanent=False), name="services"),
    # Other stubs (coming soon pages)
    path("courses/", coming_soon, name="courses"),
    path("events/", include("evenement.urls")),
    path("shop/", coming_soon, name="shop"),
]

# Serve static assets explicitly in DEBUG (helps when runserver static handler is bypassed)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
